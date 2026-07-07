"""Tests for Phase 4 — Stale escalated artifact check."""

import json
import sys
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hermes.core.events import log_event
from hermes.core.storage import save_artifact, list_artifacts, update_verification
from hermes.core.workspace import Workspace
from hermes.__main__ import cmd_check_stale


# ── Fixture ───────────────────────────────────────────────────────────
@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "workspace"))
    w.ensure_initialized()
    return w


def _escalate_artifact(ws, artifact_id, artifact_type, hours_ago=0):
    """Helper: tạo artifact với status escalated và log timestamp escalate."""
    art = save_artifact(ws, artifact_id, "content", artifact_type, "T-test")

    # Ghi event verification_result escalated với timestamp custom
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    log_event(ws, "verification_result", {
        "artifact_id": artifact_id,
        "artifact_version": art["version"],
        "artifact_type": artifact_type,
        "status": "escalated",
        "risk_level": "high",
        "rubric_score": 0.90,
        "effective_threshold": 0.85,
        "timestamp": ts.isoformat(),  # fake timestamp
    })

    # Cập nhật status trong index thành escalated
    update_verification(ws, artifact_id, art["version"], "escalated", "test escalated")

    return art


# ─────────────────────────────────────────────────────────────────────
# Test 1: Flags artifact past threshold as stale
# ─────────────────────────────────────────────────────────────────────
def test_check_stale_flags_artifact_past_threshold(ws, capsys):
    _escalate_artifact(ws, "A-old", "lecture_draft", hours_ago=48)

    args = Namespace(workspace=str(ws.root), threshold_hours=24.0)

    with pytest.raises(SystemExit) as exc_info:
        cmd_check_stale(args)

    captured = capsys.readouterr().out
    assert exc_info.value.code == 1  # exit code 1 vì có stale
    assert "QUÁ HẠN" in captured
    assert "A-old" in captured


# ─────────────────────────────────────────────────────────────────────
# Test 2: Ignores non-escalated artifacts
# ─────────────────────────────────────────────────────────────────────
def test_check_stale_ignores_non_escalated_artifacts(ws, capsys):
    # Tạo artifact pass (không escalated)
    art = save_artifact(ws, "A-ok", "content", "lit_review_md", "T-1")
    update_verification(ws, "A-ok", art["version"], "pass", "all good")

    args = Namespace(workspace=str(ws.root), threshold_hours=1.0)

    # Không có escalated artifact nào → exit 0
    with pytest.raises(SystemExit) as exc_info:
        cmd_check_stale(args)

    assert exc_info.value.code == 0
    captured = capsys.readouterr().out
    assert "không có artifact escalated" in captured.lower()


# ─────────────────────────────────────────────────────────────────────
# Test 3: Exit code nonzero when stale found
# ─────────────────────────────────────────────────────────────────────
def test_check_stale_exit_code_nonzero_when_stale_found(ws, capsys):
    _escalate_artifact(ws, "A-stale", "quiz_bank", hours_ago=100)

    args = Namespace(workspace=str(ws.root), threshold_hours=24.0)

    with pytest.raises(SystemExit) as exc_info:
        cmd_check_stale(args)

    assert exc_info.value.code == 1  # nonzero
    captured = capsys.readouterr().out
    assert "QUÁ HẠN" in captured


# ─────────────────────────────────────────────────────────────────────
# Test 4: Reads timestamp from event log, not from a new schema field
# ─────────────────────────────────────────────────────────────────────
def test_check_stale_reads_timestamp_from_event_log_not_new_field(ws, capsys):
    """Đảm bảo check-stale dùng event log để lấy timestamp escalate,
    không thêm field mới vào Artifact Schema."""
    _escalate_artifact(ws, "A-from-event", "lecture_draft", hours_ago=50)

    # Kiểm tra artifact index KHÔNG có field "escalated_at"
    idx = list_artifacts(ws)
    for entry in idx.values():
        if entry["artifact_id"] == "A-from-event":
            assert "escalated_at" not in entry, \
                "Artifact index must NOT have 'escalated_at' field — use event log instead"

    args = Namespace(workspace=str(ws.root), threshold_hours=24.0)

    with pytest.raises(SystemExit) as exc_info:
        cmd_check_stale(args)

    assert exc_info.value.code == 1  # still stale
    captured = capsys.readouterr().out
    assert "QUÁ HẠN" in captured
