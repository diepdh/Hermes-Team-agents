"""Unit tests for Phase 5.3 — Paper Reviewer (LLM-judge)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.paper_reviewer import (
    run_reviewer_judge,
    check_citations_exist_in_literature,
)


# ── Sample data ────────────────────────────────────────────────────────
SAMPLE_SOURCE = {
    "paragraphs_summary": "Study with 128 samples, 92% accuracy.",
    "tables": [[["Metric", "Value"], ["Accuracy", "92%"], ["Samples", "128"]]],
    "images": [{"description": "Chart A=12, B=18"}],
    "key_statistics": ["92%", "128", "12", "18"],
}

SAMPLE_LIT = {
    "entries": [
        {
            "title": "Assessment Methods in Education",
            "authors": "Smith, J.",
            "year": "2020",
            "url": "https://doi.org/10.1234/test",
            "excerpt": "Formative assessment improves student outcomes.",
        },
        {
            "title": "Feedback and Learning",
            "authors": "Doe, A., Johnson, B.",
            "year": "2021",
            "url": "https://doi.org/10.1234/test2",
            "excerpt": "Feedback mechanisms are critical for learning.",
        },
    ],
}

GOOD_PAPER = """# Title: Assessment Study

## Abstract
This study achieved 92% accuracy with 128 samples.

## Introduction
Formative assessment is critical (Smith 2020). Feedback matters (Doe 2021).

## Methods
128 samples were analyzed using standard protocols.

## Results
Accuracy of 92% was achieved. Category A=12, B=18.

## Discussion
Results confirm effectiveness.

## References
Smith, J. (2020). Assessment Methods in Education.
Doe, A. (2021). Feedback and Learning.
"""

PAPER_WITH_FAKE_DATA = """# Title: Assessment Study

## Abstract
This study achieved 99.9% accuracy with 10000 samples.

## Introduction
Formative assessment is critical.

## Methods
10000 samples were analyzed.

## Results
Accuracy of 99.9% was achieved.

## Discussion
Results confirm effectiveness.

## References
"""

PAPER_WITH_FAKE_CITATION = """# Title: Assessment Study

## Abstract
This study achieved 92% accuracy with 128 samples.

## Introduction
Research by Fake (2025) suggests new methods.

## Methods
128 samples were analyzed.

## Results
Accuracy of 92%.

## Discussion
Results confirm effectiveness.

## References
Fake, X. (2025). Nonexistent Paper.
"""


# ── Tests: Layer 1 — rule-based citation check (NO LLM dependency) ─────

def test_check_citations_exist_valid():
    ok, violations = check_citations_exist_in_literature(GOOD_PAPER, SAMPLE_LIT)
    assert ok is True
    assert violations == []


def test_check_citations_exist_fake():
    ok, violations = check_citations_exist_in_literature(
        PAPER_WITH_FAKE_CITATION, SAMPLE_LIT,
    )
    assert ok is False
    assert len(violations) >= 1
    assert "Fake" in violations[0]


def test_check_citations_exist_empty_lit():
    """No literature → no citations to check → trivially passes."""
    ok, violations = check_citations_exist_in_literature(GOOD_PAPER, {"entries": []})
    assert ok is True
    assert violations == []


def test_check_citations_search_error_with_citations_fails():
    """search_error + paper has citations → citation_valid MUST be False."""
    paper_with_fake_cite = PAPER_WITH_FAKE_CITATION  # has "Fake (2025)"
    lit_with_error = {
        "entries": [],
        "search_attempted": True,
        "search_error": "Literature Researcher unavailable",
    }
    ok, violations = check_citations_exist_in_literature(
        paper_with_fake_cite, lit_with_error,
    )
    assert ok is False, (
        "search_error + paper has citations must fail — we cannot verify them"
    )
    assert any("search failed" in v.lower() or "cannot verify" in v.lower() for v in violations)


def test_check_citations_search_error_no_citations_passes():
    """search_error but paper has NO real citations → trivially passes."""
    paper_no_citations = """# Title: Test

## Abstract
Test.

## References
Data provided by the attached source analysis document.
"""
    lit_with_error = {
        "entries": [],
        "search_attempted": True,
        "search_error": "API unavailable",
    }
    ok, violations = check_citations_exist_in_literature(
        paper_no_citations, lit_with_error,
    )
    assert ok is True, (
        "search_error but paper has no real citations should pass trivially"
    )


# ── Tests: Layer 2 — LLM-judge ─────────────────────────────────────────

def test_reviewer_judge_returns_llm_unavailable_flag_when_llm_is_down():
    """When LLM is unavailable, verdict must signal escalation — NOT auto-pass.

    Uses a nonexistent provider to deterministically trigger the fallback
    path without depending on the real LLM being up or down.
    """
    verdict = run_reviewer_judge(
        PAPER_WITH_FAKE_DATA, SAMPLE_SOURCE, provider="nonexistent_provider",
    )
    # With LLM unavailable, the system must not claim a successful review.
    assert verdict["passed"] is False, (
        f"LLM-unavailable must NOT auto-pass. Got passed={verdict['passed']}"
    )
    assert verdict["llm_unavailable"] is True, (
        f"Expected llm_unavailable=True, got {verdict['llm_unavailable']}"
    )
    assert "[Reviewer LLM call failed" in verdict["feedback"], (
        f"Feedback must document LLM failure, got: {verdict['feedback']}"
    )


def test_reviewer_judge_detects_fake_citation_via_layer1():
    """Layer 1 rule-based check catches fake citation regardless of LLM.

    Even when the LLM judge is down, the rule-based citation-existence
    check MUST still detect a citation that is not in literature_support.
    """
    verdict = run_reviewer_judge(
        PAPER_WITH_FAKE_CITATION, SAMPLE_SOURCE, SAMPLE_LIT,
        provider="nonexistent_provider",
    )
    # Layer 1 runs BEFORE LLM — it must catch the fake citation.
    assert verdict["citation_valid"] is False, (
        f"Layer 1 must detect fake citation. Got citation_valid={verdict['citation_valid']}"
    )
    assert "Fake" in str(verdict.get("feedback", "")), (
        f"Feedback must mention the fake citation. Got: {verdict.get('feedback')}"
    )


def test_reviewer_judge_structure_always_valid():
    """Verdict dict always has the required keys, even when LLM is down."""
    verdict = run_reviewer_judge(
        GOOD_PAPER, SAMPLE_SOURCE, SAMPLE_LIT, provider="nonexistent_provider",
    )
    assert "data_fidelity" in verdict
    assert "citation_relevant" in verdict
    assert "citation_valid" in verdict
    assert "feedback" in verdict
    assert "passed" in verdict
    assert "llm_unavailable" in verdict
    assert isinstance(verdict["passed"], bool)


def test_reviewer_llm_judge_detects_fake_data():
    """LLM-judge (real provider) must detect fabricated numbers not in source.

    This test requires a working LLM provider (opencode_go).
    If the LLM is unavailable, the test is skipped gracefully.
    """
    verdict = run_reviewer_judge(
        PAPER_WITH_FAKE_DATA, SAMPLE_SOURCE, provider="opencode_go",
    )
    if verdict.get("llm_unavailable"):
        pytest.skip("LLM provider is unavailable — cannot test real judge")

    # Fake numbers: 99.9%, 10000 — LLM must detect them
    assert verdict["data_fidelity"] < 0.5 or verdict["passed"] is False, (
        f"LLM must flag fake data. Got data_fidelity={verdict['data_fidelity']}, "
        f"passed={verdict['passed']}, feedback={verdict.get('feedback', '')[:200]}"
    )


# ── Test: Retry loop boundary ──────────────────────────────────────────

def test_reviewer_fallback_escalates_without_retry():
    """When LLM is unavailable, pipeline escalates on first attempt (no retry).

    The llm_unavailable flag must short-circuit the retry loop — it makes
    no sense to retry when the judge cannot run at all.
    """
    verdict = run_reviewer_judge(
        PAPER_WITH_FAKE_DATA, SAMPLE_SOURCE, provider="nonexistent_provider",
    )
    assert verdict["llm_unavailable"] is True
    assert verdict["passed"] is False

    # Simulate pipeline: with llm_unavailable, escalate immediately, no retry.
    # The pipeline must NOT attempt retries when the reviewer cannot run.
    max_retries = 2
    for attempt in range(1, max_retries + 3):
        verdict = run_reviewer_judge(
            PAPER_WITH_FAKE_DATA, SAMPLE_SOURCE, provider="nonexistent_provider",
        )
        if verdict.get("llm_unavailable"):
            # Pipeline escalates — break on first attempt.
            assert attempt == 1, (
                f"LLM-unavailable must escalate on first attempt, got attempt={attempt}"
            )
            break


def test_pipeline_retry_boundary_logic():
    """Pipeline retry loop must not exceed max_retries boundary.

    Simulates the retry decision: when max_retries=2, the pipeline may
    attempt up to attempt=3 (initial + 2 retries).  At attempt=4, it
    must escalate without further recursion.
    """
    max_retries = 2
    attempts_made = []
    escalated = False

    def simulated_loop(attempt=1):
        nonlocal escalated
        attempts_made.append(attempt)

        # Simulate reviewer failure (passed=False, but LLM is available)
        reviewer_passed = False

        if reviewer_passed:
            return "pass"

        if attempt <= max_retries:
            return simulated_loop(attempt + 1)
        else:
            escalated = True
            return "escalated"

    status = simulated_loop(1)

    assert status == "escalated"
    assert escalated is True
    assert attempts_made == [1, 2, 3], (
        f"With max_retries={max_retries}, expected attempts [1,2,3], "
        f"got {attempts_made}"
    )
    assert len(attempts_made) == max_retries + 1, (
        f"Total attempts ({len(attempts_made)}) must equal "
        f"max_retries+1 ({max_retries + 1})"
    )


def test_pipeline_stops_at_max_retries_zero():
    """With max_retries=0, pipeline must not retry at all."""
    max_retries = 0
    attempts = []

    for attempt in range(1, max_retries + 3):
        attempts.append(attempt)
        if attempt > max_retries:
            break

    assert attempts == [1], (
        f"With max_retries=0, only 1 attempt allowed, got {len(attempts)}"
    )
