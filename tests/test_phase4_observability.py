"""Tests for Phase 4 — Observability layer (events, logging, dashboard)."""

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from hermes.core.events import log_event, read_events, EVENT_TYPES
from hermes.core.verifier import finalize_verification
from hermes.core.storage import save_artifact
from hermes.core.workspace import Workspace
from hermes.__main__ import cmd_dashboard


# ── Fixture ───────────────────────────────────────────────────────────
@pytest.fixture
def ws(tmp_path):
    w = Workspace(str(tmp_path / "workspace"))
    w.ensure_initialized()
    return w


# ─────────────────────────────────────────────────────────────────────
# Test 1: log_event rejects unknown event types
# ─────────────────────────────────────────────────────────────────────
def test_log_event_rejects_unknown_type(ws):
    with pytest.raises(ValueError, match="Unknown event_type"):
        log_event(ws, "nonexistent_type", {})


# ─────────────────────────────────────────────────────────────────────
# Test 2: log_event appends, không ghi đè
# ─────────────────────────────────────────────────────────────────────
def test_log_event_appends_not_overwrites(ws):
    log_event(ws, "artifact_created", {"artifact_id": "A-1", "type": "lecture_draft"})
    log_event(ws, "artifact_created", {"artifact_id": "A-2", "type": "quiz_bank"})

    events = read_events(ws)
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    assert events[0]["artifact_id"] == "A-1"
    assert events[1]["artifact_id"] == "A-2"


# ─────────────────────────────────────────────────────────────────────
# Test 3: finalize_verification emits verification_result event
# ─────────────────────────────────────────────────────────────────────
def test_finalize_verification_emits_verification_result_event(ws):
    # Tạo artifact và gọi finalize_verification
    art = save_artifact(ws, "test-art", "content here", "lit_review_md", "T-1")

    result = {"passed": True, "score": 0.95, "detail": {}}
    status = finalize_verification(
        ws, art["artifact_id"], art["version"], "lit_review_md",
        result, notes="test", rubric_pass_threshold=0.7,
    )

    assert status == "pass"

    # Đọc event log — phải có verification_result
    events = read_events(ws, "verification_result")
    assert len(events) == 1, f"Expected 1 verification_result event, got {len(events)}"
    evt = events[0]
    assert evt["artifact_id"] == "test-art"
    assert evt["status"] == "pass"
    assert evt["artifact_type"] == "lit_review_md"


# ─────────────────────────────────────────────────────────────────────
# Test 4: save_artifact emits artifact_version_created event
# ─────────────────────────────────────────────────────────────────────
def test_save_artifact_emits_artifact_version_created_event(ws):
    # Xóa event từ bước fixture save_artifact nếu có
    # (ws fixture gọi ensure_initialized nhưng không gọi save_artifact)

    art = save_artifact(ws, "art-1", "content", "lit_review_md", "T-test")
    assert art["artifact_id"] == "art-1"

    events = read_events(ws, "artifact_version_created")
    assert len(events) == 1, f"Expected 1 artifact_version_created event, got {len(events)}"
    evt = events[0]
    assert evt["artifact_id"] == "art-1"
    assert evt["artifact_type"] == "lit_review_md"
    assert evt["version"] == 1


# ─────────────────────────────────────────────────────────────────────
# Test 5: Dashboard command prints summary (updated Phase 4 round 1)
# ─────────────────────────────────────────────────────────────────────
def test_dashboard_command_runs_and_prints_summary(ws, capsys):
    # Tạo dữ liệu để dashboard có gì để in
    save_artifact(ws, "A-1", "x " * 200, "lecture_draft", "T-10")
    art = save_artifact(ws, "A-1", "x " * 200, "lecture_draft", "T-10")

    result = {"passed": True, "score": 0.90, "detail": {}}
    finalize_verification(
        ws, art["artifact_id"], art["version"], "lecture_draft",
        result, notes="test", rubric_pass_threshold=0.80,
    )

    # Gọi dashboard function trực tiếp
    args = Namespace(workspace=str(ws.root))
    cmd_dashboard(args)

    captured = capsys.readouterr().out

    # Assert có các mục chính
    assert "Hermes Dashboard" in captured
    assert "Artifacts:" in captured
    # Có escalated artifact (lecture_draft là human gate)
    assert "escalated" in captured.lower()
    assert "Đang chờ duyệt" in captured


# ─────────────────────────────────────────────────────────────────────
# Test 6: Dashboard internal consistency (Phase 4 round 1 fix)
# ─────────────────────────────────────────────────────────────────────
def test_dashboard_counts_are_internally_consistent(ws, capsys):
    """Tổng breakdown phải khớp với tổng artifact, và số escalated
    trong summary phải khớp với số lượng trong danh sách 'chờ duyệt'."""
    from hermes.core.storage import list_artifacts

    # Tạo nhiều artifact với các trạng thái khác nhau
    # 2 pass, 1 fail, 2 escalated
    art_pass1 = save_artifact(ws, "pass-1", "content", "lit_review_md", "T-1")
    finalize_verification(ws, "pass-1", art_pass1["version"], "lit_review_md",
        {"passed": True, "score": 0.90, "detail": {}}, rubric_pass_threshold=0.7)

    art_pass2 = save_artifact(ws, "pass-2", "content", "course_outline", "T-2")
    finalize_verification(ws, "pass-2", art_pass2["version"], "course_outline",
        {"passed": True, "score": 0.90, "detail": {}}, rubric_pass_threshold=0.7)

    art_fail = save_artifact(ws, "fail-1", "x", "lit_review_md", "T-3")
    finalize_verification(ws, "fail-1", art_fail["version"], "lit_review_md",
        {"passed": False, "score": 0.20, "detail": {}}, rubric_pass_threshold=0.7)

    art_esc1 = save_artifact(ws, "esc-1", "x " * 200, "lecture_draft", "T-4")
    finalize_verification(ws, "esc-1", art_esc1["version"], "lecture_draft",
        {"passed": True, "score": 0.90, "detail": {}}, rubric_pass_threshold=0.80)

    art_esc2 = save_artifact(ws, "esc-2", "x " * 200, "quiz_bank", "T-5")
    finalize_verification(ws, "esc-2", art_esc2["version"], "quiz_bank",
        {"passed": True, "score": 0.90, "detail": {}}, rubric_pass_threshold=0.80)

    # Chạy dashboard
    args = Namespace(workspace=str(ws.root))
    cmd_dashboard(args)
    captured = capsys.readouterr().out

    # Verify từ artifact index
    idx = list_artifacts(ws)
    total = len(idx)
    pass_total = sum(1 for e in idx.values() if e["verification_status"] == "pass")
    fail_total = sum(1 for e in idx.values() if e["verification_status"] == "fail")
    esc_total = sum(1 for e in idx.values() if e["verification_status"] == "escalated")

    assert pass_total + fail_total + esc_total == total, \
        f"Breakdown {pass_total}+{fail_total}+{esc_total} != total {total}"

    # Assert dashboard output có đúng số liệu
    assert f"{total} versions" in captured
    assert f"{pass_total} pass" in captured
    assert f"{fail_total} fail" in captured
    assert f"{esc_total} escalated" in captured

    # Số escalated trong summary phải khớp danh sách "chờ duyệt"
    esc_in_list = captured.count("— chờ")
    assert esc_total == esc_in_list, \
        f"Escalated in summary ({esc_total}) != in list ({esc_in_list})"
