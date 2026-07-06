"""Unit tests for Phase 3 — Risk Matrix.

Tests the risk-adjusted verification threshold system introduced in Phase 3.
"""

import json
from pathlib import Path

import pytest

from hermes.core.risk import (
    RISK_MATRIX,
    RISK_ADJUSTED_FLOOR,
    get_risk_level,
    get_effective_threshold,
)
from hermes.core.verifier import finalize_verification, HUMAN_GATE_TYPES
from hermes.core.workspace import Workspace


# ─────────────────────────────────────────────────────────────────────
# Test 1: All artifact types in schema must have a risk level
# ─────────────────────────────────────────────────────────────────────
def test_all_artifact_types_have_risk_level():
    """Every artifact type defined in artifact.schema.json must appear in RISK_MATRIX.

    This guards against forgetting to register risk levels for newly added
    artifact types.
    """
    # Read artifact types from the schema file (repo root schemas/)
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_types = set(schema["properties"]["type"]["enum"])

    # debate_verdict will be added to schema later; add it here as a known upcoming type
    # that should also be in the matrix
    all_expected = schema_types | {"debate_verdict"}

    missing = all_expected - set(RISK_MATRIX.keys())
    assert not missing, (
        f"Artifact types missing from RISK_MATRIX: {sorted(missing)}. "
        f"Please register them in hermes/core/risk.py."
    )


# ─────────────────────────────────────────────────────────────────────
# Test 2: Effective threshold never below rubric base
# ─────────────────────────────────────────────────────────────────────
def test_effective_threshold_never_below_rubric_base():
    """Risk-adjusted threshold must be >= rubric base for all artifact types."""
    for artifact_type in RISK_MATRIX:
        for base in [0.0, 0.5, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]:
            effective = get_effective_threshold(artifact_type, base)
            assert effective >= base, (
                f"effective_threshold ({effective}) < base ({base}) "
                f"for {artifact_type}"
            )


# ─────────────────────────────────────────────────────────────────────
# Test 3: High risk floor is applied when rubric base is lower
# ─────────────────────────────────────────────────────────────────────
def test_high_risk_floor_applied_when_rubric_base_lower():
    """For high-risk types, effective threshold = max(rubric_base, 0.85)."""
    assert get_effective_threshold("lecture_draft", 0.80) == 0.85
    assert get_effective_threshold("quiz_bank", 0.70) == 0.85

    # When rubric base is already higher than floor, base wins
    assert get_effective_threshold("lecture_draft", 0.90) == 0.90
    assert get_effective_threshold("quiz_bank", 0.90) == 0.90


def test_critical_risk_floor_applied():
    """For critical-risk types, effective threshold = max(rubric_base, 0.90)."""
    assert get_effective_threshold("debate_verdict", 0.80) == 0.90
    assert get_effective_threshold("debate_verdict", 0.85) == 0.90
    assert get_effective_threshold("debate_verdict", 0.95) == 0.95


def test_low_and_medium_risk_no_floor():
    """Low and medium risk types use the rubric base unchanged."""
    # low: floor = 0.0, medium: floor = 0.0
    assert get_effective_threshold("lit_review_md", 0.70) == 0.70
    assert get_effective_threshold("course_outline", 0.75) == 0.75
    assert get_effective_threshold("course_outline", 0.50) == 0.50


# ─────────────────────────────────────────────────────────────────────
# Test 4: Unknown artifact type defaults to "medium", not "low"
# ─────────────────────────────────────────────────────────────────────
def test_unknown_artifact_type_defaults_to_medium_not_low():
    """Unknown types must default to 'medium' to avoid missing risk registration."""
    assert get_risk_level("future_artifact_type") == "medium"
    assert get_risk_level("some_new_thing") == "medium"

    # Verify it's not "low" — "low" would be a dangerous default
    assert get_risk_level("future_artifact_type") != "low"


# ─────────────────────────────────────────────────────────────────────
# Integration: finalize_verification applies risk-adjusted threshold
# ─────────────────────────────────────────────────────────────────────
def test_finalize_verification_applies_risk_floor(tmp_path):
    """When rubric_pass_threshold is provided, effective_threshold is used."""
    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    # Create a fake artifact record so update_verification can find it
    from hermes.core.storage import save_artifact
    save_artifact(
        ws,
        artifact_id="risk-test",
        content="test content",
        artifact_type="lecture_draft",
        produced_by_task="T-20260706-001",
    )
    artifact = save_artifact(
        ws,
        artifact_id="risk-test",
        content="test content v2",
        artifact_type="lecture_draft",
        produced_by_task="T-20260706-001",
    )

    # rubric base threshold = 0.80, score = 0.82
    # Without risk: score 0.82 >= 0.80 → pass
    # With risk (high → floor 0.85): score 0.82 < 0.85 → fail
    rubric_result = {"passed": True, "score": 0.82, "detail": {}}

    status = finalize_verification(
        ws,
        artifact["artifact_id"],
        artifact["version"],
        "lecture_draft",
        rubric_result,
        notes="risk integration test",
        rubric_pass_threshold=0.80,
    )
    assert status == "fail", (
        f"Expected 'fail' because score 0.82 < risk floor 0.85 for high-risk lecture_draft, "
        f"got '{status}'"
    )


def test_finalize_verification_passes_when_score_above_floor(tmp_path):
    """When score exceeds risk floor, artifact passes (or escalates for human gate)."""
    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    from hermes.core.storage import save_artifact
    save_artifact(
        ws,
        artifact_id="risk-pass",
        content="test",
        artifact_type="course_outline",
        produced_by_task="T-20260706-001",
    )
    artifact = save_artifact(
        ws,
        artifact_id="risk-pass",
        content="test v2",
        artifact_type="course_outline",
        produced_by_task="T-20260706-001",
    )

    # course_outline is medium risk (floor 0.0), score 0.80 >= base 0.75 → pass
    rubric_result = {"passed": True, "score": 0.80, "detail": {}}

    status = finalize_verification(
        ws,
        artifact["artifact_id"],
        artifact["version"],
        "course_outline",
        rubric_result,
        notes="risk integration test",
        rubric_pass_threshold=0.75,
    )
    assert status == "pass", (
        f"Expected 'pass' for medium-risk course_outline with score 0.80 >= base 0.75, "
        f"got '{status}'"
    )


def test_risk_matrix_keys_match_risk_adjusted_floor_keys():
    """Every risk level in RISK_ADJUSTED_FLOOR must be valid."""
    for artifact_type in RISK_MATRIX:
        level = RISK_MATRIX[artifact_type]
        assert level in RISK_ADJUSTED_FLOOR, (
            f"Risk level '{level}' for {artifact_type} not found in RISK_ADJUSTED_FLOOR"
        )
