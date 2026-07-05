"""
Unit test cho Phase 0 của Hermes.
Chạy: python -m pytest tests/test_phase0.py -v
Hoặc: python tests/test_phase0.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.validator import validate_task, validate_artifact, validate_rubric
from core.state_machine import transition, can_transition
from core.storage import save_artifact, get_artifact, update_verification, list_artifacts


def _sample_task():
    return {
        "task_id": "T-20260705-001",
        "type": "literature_review",
        "assigned_subagent": "researcher",
        "input_refs": [],
        "instructions": "Test task giả lập Phase 0",
        "output_schema": {"artifact_type": "lit_review_md", "required_fields": ["summary"]},
        "verification": {"method": "rubric", "rubric_id": "R-lit-review-v2", "min_score": 0.8},
        "status": "pending",
        "retry_count": 0,
        "max_retries": 2,
    }


def test_schema_valid_task():
    validate_task(_sample_task())


def test_schema_invalid_task_missing_field():
    bad = _sample_task()
    del bad["assigned_subagent"]
    try:
        validate_task(bad)
    except Exception as e:
        assert "assigned_subagent" in str(e)
        return
    raise AssertionError("Expected validation to fail")


def test_rubric_schema():
    rubric = json.loads(Path("rubrics/R-lit-review-v2.json").read_text())
    validate_rubric(rubric)


def test_state_machine_valid_transition():
    task = _sample_task()
    transition(task, "in_progress")
    assert task["status"] == "in_progress"


def test_state_machine_invalid_transition():
    task = _sample_task()
    try:
        transition(task, "verified")
    except ValueError:
        return
    raise AssertionError("Expected ValueError for invalid transition")


def test_state_machine_verified_terminal():
    task = _sample_task()
    task["status"] = "verified"
    assert not can_transition(task, "in_progress")
    try:
        transition(task, "in_progress")
    except ValueError:
        return
    raise AssertionError("verified should be terminal")


def test_artifact_versioning():
    a1 = save_artifact(
        artifact_id="A-9999",
        content="version 1",
        artifact_type="lit_review_md",
        produced_by_task="T-20260705-999",
    )
    a2 = save_artifact(
        artifact_id="A-9999",
        content="version 2",
        artifact_type="lit_review_md",
        produced_by_task="T-20260705-999",
    )
    assert a1["version"] == 1
    assert a2["version"] == 2
    latest = get_artifact("A-9999")
    assert latest["version"] == 2
    validate_artifact(a2)


def test_update_verification():
    update_verification("A-9999", 1, "fail", "Thiếu trích dẫn")
    a = get_artifact("A-9999", version=1)
    assert a["verification_status"] == "fail"
    assert "Thiếu trích dẫn" in a["verification_notes"]


if __name__ == "__main__":
    import shutil

    # Dọn test artifacts trước khi chạy
    for p in Path("artifacts").glob("A-9999_*.md"):
        p.unlink(missing_ok=True)

    test_schema_valid_task()
    test_schema_invalid_task_missing_field()
    test_rubric_schema()
    test_state_machine_valid_transition()
    test_state_machine_invalid_transition()
    test_state_machine_verified_terminal()
    test_artifact_versioning()
    test_update_verification()

    print("All Phase 0 tests passed.")
