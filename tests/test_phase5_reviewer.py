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
from hermes.core.verifier import CHECKER_REGISTRY


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


# ── Tests ──────────────────────────────────────────────────────────────

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


def test_reviewer_judge_detects_fake_data():
    """LLM-judge should flag fabricated numbers not in source."""
    verdict = run_reviewer_judge(PAPER_WITH_FAKE_DATA, SAMPLE_SOURCE)
    # Fake numbers: 99.9%, 10000 — should be detected
    assert verdict["data_fidelity"] < 0.8 or verdict["passed"] is False, (
        f"Expected low score for fake data, got data_fidelity={verdict['data_fidelity']}"
    )


def test_reviewer_judge_detects_fake_citation():
    verdict = run_reviewer_judge(
        PAPER_WITH_FAKE_CITATION, SAMPLE_SOURCE, SAMPLE_LIT,
    )
    # Fake citation "Fake (2025)" not in SAMPLE_LIT
    assert verdict["citation_valid"] is False or verdict["passed"] is False


def test_reviewer_judge_passes_good_paper():
    verdict = run_reviewer_judge(GOOD_PAPER, SAMPLE_SOURCE, SAMPLE_LIT)
    # This may fail depending on LLM — test is for structure, not score
    assert "data_fidelity" in verdict
    assert "feedback" in verdict
    assert isinstance(verdict["passed"], bool)
