"""
Unit test cho Phase 0 / Phase 0.5 của Hermes.

Chạy: python -m pytest tests/test_phase0.py -v
Hoặc: python tests/test_phase0.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.workspace import Workspace
from core.validator import validate_task, validate_artifact, validate_rubric
from core.state_machine import transition, can_transition
from core.storage import save_artifact, get_artifact, update_verification, read_artifact_content
from core.task_index import save_task, get_task


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


def _make_temp_workspace() -> Workspace:
    tmpdir = tempfile.mkdtemp(prefix="hermes_test_")
    return Workspace(tmpdir)


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
    base_dir = Path(__file__).resolve().parent.parent
    rubric = json.loads((base_dir / "rubrics" / "R-lit-review-v2.json").read_text())
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
    ws = _make_temp_workspace()
    try:
        a1 = save_artifact(
            ws,
            artifact_id="A-9999",
            content="version 1",
            artifact_type="lit_review_md",
            produced_by_task="T-20260705-999",
        )
        a2 = save_artifact(
            ws,
            artifact_id="A-9999",
            content="version 2",
            artifact_type="lit_review_md",
            produced_by_task="T-20260705-999",
        )
        assert a1["version"] == 1
        assert a2["version"] == 2
        assert a2["content_ref"] == ".hermes/artifacts/A-9999_v2.md"
        latest = get_artifact(ws, "A-9999")
        assert latest["version"] == 2
        validate_artifact(a2)
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_update_verification():
    ws = _make_temp_workspace()
    try:
        save_artifact(
            ws,
            artifact_id="A-9999",
            content="version 1",
            artifact_type="lit_review_md",
            produced_by_task="T-20260705-999",
        )
        update_verification(ws, "A-9999", 1, "fail", "Thiếu trích dẫn")
        a = get_artifact(ws, "A-9999", version=1)
        assert a["verification_status"] == "fail"
        assert "Thiếu trích dẫn" in a["verification_notes"]
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def test_two_workspaces_isolated():
    ws1 = _make_temp_workspace()
    ws2 = _make_temp_workspace()
    try:
        save_artifact(ws1, "A-0001", "ws1 content", "lit_review_md", "T-20260705-001")
        save_artifact(ws2, "A-0001", "ws2 content", "lit_review_md", "T-20260705-002")

        a1 = get_artifact(ws1, "A-0001")
        a2 = get_artifact(ws2, "A-0001")

        assert read_artifact_content(ws1, a1) == "ws1 content"
        assert read_artifact_content(ws2, a2) == "ws2 content"
    finally:
        shutil.rmtree(ws1.root, ignore_errors=True)
        shutil.rmtree(ws2.root, ignore_errors=True)


def test_workspace_is_portable():
    """
    Copy workspace sang path khác và xác nhận get_artifact + read content vẫn đúng
    nhờ content_ref là path tương đối.
    """
    original = _make_temp_workspace()
    copied = None
    try:
        save_artifact(original, "A-PORTABLE", "portable content", "lit_review_md", "T-20260705-001")

        copied_root = original.root.with_name(original.root.name + "_copied")
        shutil.copytree(original.root, copied_root)
        copied = Workspace(copied_root)

        a = get_artifact(copied, "A-PORTABLE")
        assert a is not None
        assert read_artifact_content(copied, a) == "portable content"
    finally:
        shutil.rmtree(original.root, ignore_errors=True)
        if copied:
            shutil.rmtree(copied.root, ignore_errors=True)


def test_cli_init(capsys):
    """Kiểm tra CLI init tạo được workspace."""
    import subprocess
    import sys

    tmpdir = tempfile.mkdtemp(prefix="hermes_cli_test_")
    try:
        repo_root = str(Path(__file__).resolve().parent.parent.parent)
        result = subprocess.run(
            [sys.executable, "-m", "hermes", "init", "--workspace", tmpdir],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": repo_root},
        )
        assert result.returncode == 0, result.stderr
        assert "Initialized Hermes workspace" in result.stdout
        assert (Path(tmpdir) / ".hermes" / "config.json").exists()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_schema_valid_task()
    test_schema_invalid_task_missing_field()
    test_rubric_schema()
    test_state_machine_valid_transition()
    test_state_machine_invalid_transition()
    test_state_machine_verified_terminal()
    test_artifact_versioning()
    test_update_verification()
    test_two_workspaces_isolated()
    test_workspace_is_portable()

    # CLI test không chạy trong __main__ vì cần pytest fixture
    print("All Phase 0.5 tests passed (run pytest separately for CLI test).")
