"""Unit tests for Phase 5.7a — Existing paper pipeline."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.pipeline.existing_paper_pipeline import (
    assess_existing_paper,
    parse_chosen_option_from_notes,
)
from hermes.agents.ingest_paper import ingest_existing_paper_as_draft
from hermes.core.verifier import CHECKER_REGISTRY, verify_artifact
from hermes.rubrics import load_rubric
from hermes.core.risk import get_risk_level


# ── Sample paper ──────────────────────────────────────────────────────
SAMPLE_PAPER = """# Assessment Study

## Abstract
This study achieved 92% accuracy with 128 samples.

## Introduction
Formative assessment is critical for learning.

## Methods
128 samples were analyzed using standard protocols.

## Results
Accuracy of 92% was achieved. Chart shows A=12, B=18.

## Discussion
Results confirm effectiveness of the approach.

## References
Smith, J. (2020). Assessment Methods in Education.
"""

PARTIAL_PAPER = """# Quick Note

## Abstract
Short study with some results.

## Results
We found 85% accuracy.
"""


# ── Tests: Assessment ─────────────────────────────────────────────────

def test_assessment_detects_present_sections():
    assessment = assess_existing_paper(SAMPLE_PAPER, has_accompanying_data=False)
    present = assessment["imrad_sections_present"]
    assert "abstract" in present
    assert "methods" in present
    assert "results" in present
    assert "discussion" in present
    assert "references" in present


def test_assessment_detects_missing_sections():
    assessment = assess_existing_paper(PARTIAL_PAPER, has_accompanying_data=False)
    missing = assessment["imrad_sections_missing"]
    assert len(missing) > 0
    assert "methods" in missing or "method" in str(missing).lower()


def test_assessment_has_required_fields():
    assessment = assess_existing_paper(SAMPLE_PAPER, has_accompanying_data=True)
    assert "has_accompanying_data" in assessment
    assert assessment["has_accompanying_data"] is True
    assert len(assessment["option_2_suggestions"]) >= 1
    assert assessment["data_completeness_notes"]


def test_assessment_option_1_feasibility():
    with_data = assess_existing_paper(SAMPLE_PAPER, has_accompanying_data=True)
    assert with_data["option_1_feasible"] is True

    without_data = assess_existing_paper(SAMPLE_PAPER, has_accompanying_data=False)
    assert without_data["option_1_feasible"] is False


# ── Tests: Ingest ─────────────────────────────────────────────────────

def test_ingest_preserves_content():
    result = ingest_existing_paper_as_draft(SAMPLE_PAPER)
    assert "92%" in result
    assert "128 samples" in result


def test_ingest_adds_suggestions():
    result = ingest_existing_paper_as_draft(
        SAMPLE_PAPER,
        suggestions=["Add more samples", "Improve statistical tests"],
    )
    assert "## Suggested Future Work" in result
    assert "Add more samples" in result
    assert "Improve statistical tests" in result


def test_ingest_adds_meta_note():
    result = ingest_existing_paper_as_draft(SAMPLE_PAPER, has_source_data=False)
    assert "has_source_data=false" in result.lower()

    result2 = ingest_existing_paper_as_draft(SAMPLE_PAPER, has_source_data=True)
    assert "has_source_data=true" in result2.lower()


# ── Tests: Option parsing ─────────────────────────────────────────────

def test_parse_option_2():
    assert parse_chosen_option_from_notes("OPTION=2; Approved by human") == 2


def test_parse_option_1():
    assert parse_chosen_option_from_notes("OPTION=1; Approved") == 1


def test_parse_no_option():
    assert parse_chosen_option_from_notes("Approved by human") is None


# ── Tests: Registry + Risk ────────────────────────────────────────────

def test_existing_paper_assessment_in_checker():
    assert "existing_paper_assessment" in CHECKER_REGISTRY


def test_existing_paper_assessment_risk_medium():
    assert get_risk_level("existing_paper_assessment") == "medium"


def test_assessment_rubric_pass():
    rubric = load_rubric("existing_paper_assessment")
    assessment = assess_existing_paper(SAMPLE_PAPER)
    content = json.dumps(assessment)
    result = verify_artifact("existing_paper_assessment", content, rubric)
    assert result["passed"] is True, f"Score={result['score']}, detail={result['detail']}"


# ── Tests: Self-source ────────────────────────────────────────────────

def test_self_source_extracts_numbers():
    from hermes.agents.ingest_paper import _build_self_source
    s = _build_self_source(SAMPLE_PAPER)
    assert len(s["key_statistics"]) > 0
    assert "92" in s["key_statistics"] or "92%" in s["key_statistics"]
    assert "128" in s["key_statistics"]
    assert "NO EXTERNAL GROUND TRUTH" in s["_note"]


def test_self_source_excludes_years():
    from hermes.agents.ingest_paper import _build_self_source
    text_with_year = "Study in 2020 showed 85% accuracy. Smith (2021) confirmed."
    s = _build_self_source(text_with_year)
    # Years 2020, 2021 should be excluded
    assert "2020" not in s["key_statistics"]
    assert "2021" not in s["key_statistics"]
    assert "85" in s["key_statistics"] or "85%" in s["key_statistics"]


def test_get_or_build_source_no_data():
    from hermes.pipeline.existing_paper_pipeline import get_or_build_source
    s = get_or_build_source(SAMPLE_PAPER, has_accompanying_data=False)
    assert "_note" in s
    assert "NO EXTERNAL GROUND TRUTH" in s["_note"]


# ── Tests: Citation extraction ────────────────────────────────────────

def test_extract_citations_from_text():
    from hermes.pipeline.existing_paper_pipeline import _extract_citations_from_text
    text = "Research by Smith (2020) and Doe, J. (2021) shows results."
    cites = _extract_citations_from_text(text)
    assert len(cites) == 2
    authors = {c["author"] for c in cites}
    assert "Smith" in authors
    assert "Doe, J." in authors
