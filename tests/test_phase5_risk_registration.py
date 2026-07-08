"""Unit tests for Phase 5.4 — Risk Registration + Debate Auto-Trigger.

Verifies that paper_draft and final_paper are correctly registered in
the RISK_MATRIX with appropriate risk levels, effective thresholds
are applied, and debate review auto-triggers for high/critical types.
"""

import json
from pathlib import Path

from hermes.core.risk import (
    RISK_MATRIX,
    get_risk_level,
    get_effective_threshold,
    should_trigger_debate,
)


# ── Risk Registration ─────────────────────────────────────────────────

def test_paper_draft_registered_as_high():
    """paper_draft must be registered with risk=high."""
    assert "paper_draft" in RISK_MATRIX, (
        f"paper_draft missing from RISK_MATRIX. Keys: {sorted(RISK_MATRIX)}"
    )
    assert get_risk_level("paper_draft") == "high"


def test_final_paper_registered_as_critical():
    """final_paper must be registered with risk=critical."""
    assert "final_paper" in RISK_MATRIX, (
        f"final_paper missing from RISK_MATRIX. Keys: {sorted(RISK_MATRIX)}"
    )
    assert get_risk_level("final_paper") == "critical"


def test_paper_draft_in_artifact_schema():
    """Artifact schema must include paper_draft and final_paper."""
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_types = set(schema["properties"]["type"]["enum"])

    assert "paper_draft" in schema_types, (
        f"paper_draft missing from artifact schema enum. "
        f"Current: {sorted(schema_types)}"
    )
    assert "final_paper" in schema_types


def test_all_schema_types_in_risk_matrix():
    """Every artifact type in the schema must appear in RISK_MATRIX.

    Guards against forgetting to register risk levels for new types.
    """
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_types = set(schema["properties"]["type"]["enum"])

    # debate_verdict is handled separately (it's in the matrix but was
    # added to schema later — allow it)
    all_expected = schema_types | {"debate_verdict"}

    missing = all_expected - set(RISK_MATRIX.keys())
    assert not missing, (
        f"Artifact types in schema but missing from RISK_MATRIX: {sorted(missing)}. "
        f"Please register in hermes/core/risk.py."
    )


# ── Effective Thresholds ──────────────────────────────────────────────

def test_paper_draft_effective_threshold_floor():
    """paper_draft (risk=high) has floor=0.85 — never below it."""
    # Floor: 0.85; rubric base lower → floor kicks in
    assert get_effective_threshold("paper_draft", 0.70) == 0.85
    assert get_effective_threshold("paper_draft", 0.80) == 0.85
    # Rubric base higher → rubric base wins
    assert get_effective_threshold("paper_draft", 0.90) == 0.90
    assert get_effective_threshold("paper_draft", 0.95) == 0.95


def test_final_paper_effective_threshold_floor():
    """final_paper (risk=critical) has floor=0.90 — never below it."""
    assert get_effective_threshold("final_paper", 0.70) == 0.90
    assert get_effective_threshold("final_paper", 0.85) == 0.90
    assert get_effective_threshold("final_paper", 0.95) == 0.95


def test_paper_draft_threshold_never_below_rubric_base():
    """Risk-adjusted threshold must always be >= rubric base (general property)."""
    for base in [0.0, 0.5, 0.7, 0.75, 0.80, 0.85, 0.90, 1.0]:
        effective = get_effective_threshold("paper_draft", base)
        assert effective >= base, (
            f"paper_draft: effective ({effective}) < base ({base})"
        )


# ── Debate Auto-Trigger ───────────────────────────────────────────────

def test_paper_draft_triggers_debate():
    """paper_draft (risk=high) must auto-trigger debate review."""
    assert should_trigger_debate("paper_draft") is True


def test_final_paper_triggers_debate():
    """final_paper (risk=critical) must auto-trigger debate review."""
    assert should_trigger_debate("final_paper") is True


def test_low_risk_types_do_not_trigger_debate():
    """Low-risk types (source_analysis, lit_review_md) must NOT trigger debate."""
    assert should_trigger_debate("source_analysis") is False
    assert should_trigger_debate("lit_review_md") is False


def test_paper_draft_not_in_skip_debate_types():
    """paper_draft must NOT be in SKIP_DEBATE_TYPES (debate should run)."""
    from hermes.core.risk import SKIP_DEBATE_TYPES
    assert "paper_draft" not in SKIP_DEBATE_TYPES
    assert "final_paper" not in SKIP_DEBATE_TYPES
