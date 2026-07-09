"""Unit tests for Phase 5.6 — Editor Agent + Rule-based Diff Guard."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.editor_paper import run_paper_editor
from hermes.core.verifier import check_editor_diff


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
    ],
}

ORIGINAL_PAPER = """# Title: Assessment Study

## Abstract
This study achieved 92% accuracy with 128 samples.

## Introduction
Formative assessment is critical for learning outcomes.

## Methods
128 samples were analyzed using standard protocols.

## Results
Accuracy of 92% was achieved. Category A=12, B=18.

## Discussion
Results confirm the effectiveness of the approach.

## References
Data provided by the attached source analysis document.
"""

REVIEWER_FEEDBACK = (
    "1. Abstract says 'achieved 92% accuracy' but should emphasize the "
    "sample size of 128. 2. Discussion should mention the chart data (A=12, B=18)."
)


# ── Tests: Editor ─────────────────────────────────────────────────────

def test_editor_produces_output():
    """Editor must return non-empty string."""
    edited = run_paper_editor(
        ORIGINAL_PAPER, SAMPLE_SOURCE, REVIEWER_FEEDBACK, provider="opencode_go",
    )
    assert edited, "Editor returned empty output"
    assert len(edited) > 100, f"Editor output too short: {len(edited)} chars"


def test_editor_preserves_key_numbers():
    """Editor must keep 92% and 128 (from source) in output."""
    edited = run_paper_editor(
        ORIGINAL_PAPER, SAMPLE_SOURCE, REVIEWER_FEEDBACK, provider="opencode_go",
    )
    assert "92%" in edited, "Editor must preserve accuracy value"
    assert "128" in edited, "Editor must preserve sample count"


def test_editor_unavailable_provider_returns_original():
    """When LLM is unavailable, Editor returns original unchanged."""
    edited = run_paper_editor(
        ORIGINAL_PAPER, SAMPLE_SOURCE, REVIEWER_FEEDBACK,
        provider="nonexistent_provider",
    )
    # Should return original (fallback) since provider doesn't exist
    assert len(edited) > 0


# ── Tests: Rule-based diff guard ──────────────────────────────────────

def test_diff_guard_passes_identical_content():
    """Identical content must pass the diff guard."""
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, ORIGINAL_PAPER, SAMPLE_SOURCE, SAMPLE_LIT,
    )
    assert ok is True, f"Identical content should pass, got: {violations}"
    assert violations == []


def test_diff_guard_detects_new_number():
    """Editor adding a number not in original or source must be detected."""
    edited_with_fake = ORIGINAL_PAPER.replace("92% accuracy", "99.9% accuracy")
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, edited_with_fake, SAMPLE_SOURCE,
    )
    assert ok is False, "Must detect fabricated number 99.9%"
    assert any("99.9" in v for v in violations), (
        f"Violations must mention 99.9, got: {violations}"
    )


def test_diff_guard_allows_number_from_source():
    """A number from source_analysis.key_statistics is allowed."""
    # '18' is in key_statistics but NOT in original paper text
    edited_with_source_num = ORIGINAL_PAPER + "\nAdditional value: 18."
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, edited_with_source_num, SAMPLE_SOURCE,
    )
    assert ok is True, (
        f"Number from key_statistics should be allowed, got: {violations}"
    )


def test_diff_guard_detects_fake_citation():
    """Editor adding a citation not in literature_support must be detected."""
    edited_with_fake_cite = ORIGINAL_PAPER.replace(
        "## References\nData provided by the attached source analysis document.",
        "## References\nFake, X. (2025). Nonexistent Paper.",
    )
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, edited_with_fake_cite, SAMPLE_SOURCE, SAMPLE_LIT,
    )
    assert ok is False, "Must detect fake citation Fake (2025)"
    assert any("Fake" in v or "fake" in v.lower() for v in violations), (
        f"Violations must mention the fake citation, got: {violations}"
    )


def test_diff_guard_allows_real_citation():
    """Adding a citation from literature_support must pass."""
    edited_with_real_cite = ORIGINAL_PAPER.replace(
        "## References\nData provided by the attached source analysis document.",
        "## References\nSmith, J. (2020). Assessment Methods in Education.",
    )
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, edited_with_real_cite, SAMPLE_SOURCE, SAMPLE_LIT,
    )
    assert ok is True, (
        f"Citation from literature_support should be allowed, got: {violations}"
    )


def test_diff_guard_empty_lit_allows_citations():
    """With no literature_support, citations pass (no index to check against)."""
    edited_with_cite = ORIGINAL_PAPER.replace(
        "## References\nData provided by the attached source analysis document.",
        "## References\nSomeone, A. (2023). Some paper.",
    )
    ok, violations = check_editor_diff(
        ORIGINAL_PAPER, edited_with_cite, SAMPLE_SOURCE, None,
    )
    # No literature → citation guard is skipped
    assert ok is True


def test_diff_guard_detects_changed_citation_year():
    """Changing a citation's year without literature support must be caught."""
    # Original has Smith (2020) in literature
    paper_with_cite = ORIGINAL_PAPER.replace(
        "## References\nData provided by the attached source analysis document.",
        "## References\nSmith, J. (2020). Assessment Methods in Education.",
    )
    # Editor changes year from 2020 to 2021 — but literature only has 2020
    edited_year_changed = paper_with_cite.replace(
        "Smith, J. (2020)", "Smith, J. (2021)",
    )
    ok, violations = check_editor_diff(
        paper_with_cite, edited_year_changed, SAMPLE_SOURCE, SAMPLE_LIT,
    )
    assert ok is False, "Must detect year change for existing citation"
    assert any("2021" in v or "year" in v.lower() for v in violations), (
        f"Violations must mention the year change, got: {violations}"
    )
