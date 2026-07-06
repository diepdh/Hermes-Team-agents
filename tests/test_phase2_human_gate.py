"""
Tests for Phase 2 human gate and CLI approve workflow.

All tests go through finalize_verification() — the single source of truth —
to ensure the human gate policy is enforced consistently everywhere
(pipeline, test, and CLI).
"""

import pytest
from pathlib import Path

from hermes.core.workspace import Workspace
from hermes.core.storage import save_artifact, update_verification, list_artifacts

# Content confirmed to pass R-lecture-draft-v1 (score=1.0, see forensics log)
# Verified via: check_lecture_draft(VALID_LECTURE_CONTENT, rubric) → passed=True
VALID_LECTURE_CONTENT = "# Lecture Draft\n\n" + (
    "This section explains the concept in depth. "
    "For example, consider a classroom scenario where students apply it directly. "
) * 80


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------
@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "workspace"))
    w.ensure_initialized()
    return w


# -------------------------------------------------------------------
# Human gate: types defined correctly
# -------------------------------------------------------------------
def test_human_gate_types_defined():
    from hermes.core.verifier import HUMAN_GATE_TYPES

    assert "lecture_draft" in HUMAN_GATE_TYPES
    assert "quiz_bank" in HUMAN_GATE_TYPES
    assert "course_outline" not in HUMAN_GATE_TYPES
    assert "lit_review_md" not in HUMAN_GATE_TYPES


# -------------------------------------------------------------------
# Test: finalize_verification sets escalated for lecture_draft
# -------------------------------------------------------------------
def test_escalated_to_pass_via_update_verification(ws):
    from hermes.core.verifier import finalize_verification
    from hermes.rubrics import load_rubric

    rubric = load_rubric("R-lecture-draft-v1")

    artifact = save_artifact(
        workspace=ws,
        artifact_id="lecture-lecture",
        content=VALID_LECTURE_CONTENT,
        artifact_type="lecture_draft",
        produced_by_task="lecture-lecture",
    )
    vid = artifact["version"]

    # Verify initial status is escalated (human gate policy via finalize_verification)
    from hermes.core.verifier import verify_artifact

    content = (ws.artifact_dir / f"lecture-lecture_v{vid}.md").read_text(encoding="utf-8")
    rubric_result = verify_artifact("lecture_draft", content, rubric)
    status = finalize_verification(
        ws, artifact["artifact_id"], vid, "lecture_draft", rubric_result
    )
    assert status == "escalated", "lecture_draft must be escalated by finalize_verification"

    # Approve: change to pass
    update_verification(ws, "lecture-lecture", vid, "pass", notes="Human approved")
    idx = list_artifacts(ws)
    entry = idx.get(f"lecture-lecture_v{vid}")
    assert entry is not None
    assert entry["verification_status"] == "pass"


# -------------------------------------------------------------------
# Test: non-escalated types (course_outline) stay pass after finalize
# -------------------------------------------------------------------
def test_non_human_gate_type_stays_pass(ws):
    from hermes.core.verifier import finalize_verification, verify_artifact
    from hermes.rubrics import load_rubric

    rubric = load_rubric("R-course-outline-v1")
    good_content = """# Course Outline

## Learning Objectives
Students will be able to explain formative assessment.

## Session Breakdown
- Week 1: Introduction
- Week 2: Deep Dive

## Assessment Hooks
Quiz after Week 1.
"""

    artifact = save_artifact(
        workspace=ws,
        artifact_id="test-outline",
        content=good_content,
        artifact_type="course_outline",
        produced_by_task="test-outline",
    )
    vid = artifact["version"]

    rubric_result = verify_artifact("course_outline", good_content, rubric)
    status = finalize_verification(ws, artifact["artifact_id"], vid, "course_outline", rubric_result)
    assert status == "pass", "course_outline must be pass, not escalated"


# -------------------------------------------------------------------
# Test: _find_verification_record CLI helper — escalated status visible
# -------------------------------------------------------------------
def test_find_verification_record(ws):
    from hermes.__main__ import _find_verification_record
    from hermes.core.verifier import finalize_verification, verify_artifact
    from hermes.rubrics import load_rubric

    rubric = load_rubric("R-lecture-draft-v1")

    artifact = save_artifact(
        workspace=ws,
        artifact_id="lecture-lecture",
        content=VALID_LECTURE_CONTENT,
        artifact_type="lecture_draft",
        produced_by_task="lecture-lecture",
    )
    vid = artifact["version"]

    content = (ws.artifact_dir / f"lecture-lecture_v{vid}.md").read_text(encoding="utf-8")
    rubric_result = verify_artifact("lecture_draft", content, rubric)
    finalize_verification(ws, "lecture-lecture", vid, "lecture_draft", rubric_result)

    rec = _find_verification_record(ws, "lecture-lecture", vid)
    assert rec is not None
    assert rec["artifact_id"] == "lecture-lecture"
    assert rec["verification_status"] == "escalated"


# -------------------------------------------------------------------
# Test: approve command transitions escalated → pass
# -------------------------------------------------------------------
def test_approve_command_updates_to_pass(ws):
    from hermes.__main__ import _find_verification_record
    from hermes.core.verifier import finalize_verification, verify_artifact
    from hermes.rubrics import load_rubric

    rubric = load_rubric("R-lecture-draft-v1")

    artifact = save_artifact(
        workspace=ws,
        artifact_id="lecture-lecture",
        content=VALID_LECTURE_CONTENT,
        artifact_type="lecture_draft",
        produced_by_task="lecture-lecture",
    )
    vid = artifact["version"]

    content = (ws.artifact_dir / f"lecture-lecture_v{vid}.md").read_text(encoding="utf-8")
    rubric_result = verify_artifact("lecture_draft", content, rubric)
    finalize_verification(ws, "lecture-lecture", vid, "lecture_draft", rubric_result)

    # Should start escalated
    rec = _find_verification_record(ws, "lecture-lecture", vid)
    assert rec["verification_status"] == "escalated"

    # Approve
    update_verification(ws, "lecture-lecture", vid, "pass", notes="Approved by human")

    # Should now be pass
    rec2 = _find_verification_record(ws, "lecture-lecture", vid)
    assert rec2["verification_status"] == "pass"


# -------------------------------------------------------------------
# Test: approve on already-pass artifact is a no-op (CLI handles warning)
# -------------------------------------------------------------------
def test_approve_warns_on_already_pass(ws):
    from hermes.__main__ import _find_verification_record
    from hermes.core.verifier import finalize_verification, verify_artifact
    from hermes.rubrics import load_rubric

    rubric = load_rubric("R-lecture-draft-v1")

    artifact = save_artifact(
        workspace=ws,
        artifact_id="lecture-lecture",
        content=VALID_LECTURE_CONTENT,
        artifact_type="lecture_draft",
        produced_by_task="lecture-lecture",
    )
    vid = artifact["version"]

    content = (ws.artifact_dir / f"lecture-lecture_v{vid}.md").read_text(encoding="utf-8")
    rubric_result = verify_artifact("lecture_draft", content, rubric)
    finalize_verification(ws, "lecture-lecture", vid, "lecture_draft", rubric_result)

    # Re-opening workspace to simulate CLI re-read
    ws2 = Workspace(str(ws.root))
    rec = _find_verification_record(ws2, "lecture-lecture", vid)
    assert rec["verification_status"] == "escalated"
