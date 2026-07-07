"""
CLI tối thiểu cho Hermes Phase 2+4.

Sử dụng:
    python -m hermes init --workspace /path/to/folder
    python -m hermes approve --workspace /path --artifact lecture-lecture --version 1
    python -m hermes dashboard --workspace /path
    python -m hermes check-stale --workspace /path --threshold-hours 24
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from hermes.core.workspace import Workspace
from hermes.core.storage import update_verification, list_artifacts
from hermes.core.events import read_events


def cmd_init(args):
    workspace = Workspace(args.workspace)
    workspace.ensure_initialized()
    print(f"Initialized Hermes workspace at: {workspace.root}")
    print(f"  config: {workspace.config_path}")
    print(f"  artifacts: {workspace.artifact_dir}")
    print(f"  tasks: {workspace.task_dir}")
    print(f"  rubrics: {workspace.rubric_dir}")
    print(f"  logs: {workspace.log_dir}")


def _find_verification_record(ws: Workspace, artifact_id: str, version: int) -> dict | None:
    """Scan artifacts/ for the matching verification record."""
    idx = list_artifacts(ws)
    for key, entry in idx.items():
        if entry.get("artifact_id") == artifact_id and entry.get("version") == version:
            return entry
    return None


def cmd_approve(args):
    workspace = Workspace(args.workspace)
    workspace.ensure_initialized()

    record = _find_verification_record(workspace, args.artifact, args.version)
    if record is None:
        print(f"[ERROR] Khong tim thay artifact '{args.artifact}' v{args.version}")
        sys.exit(1)

    current = record.get("verification_status", "unknown")
    if current == "pass":
        print(f"[WARN] Artifact '{args.artifact}' v{args.version} da la 'pass', khong can approve.")
        return

    if current not in ("escalated", "fail"):
        print(f"[ERROR] Khong the approve artifact dang '{current}' (chi escalated/fail moi can approve).")
        sys.exit(1)

    update_verification(
        workspace,
        args.artifact,
        args.version,
        "pass",
        notes=f"[CLI approve] Duc ung vien da duyet thu cong lan {args.note or 1}.",
    )
    print(f"[OK] Da approve: {args.artifact} v{args.version} -> pass")
    if args.workspace:
        print(f"Workspace: {workspace.root}")


# ── Phase 4: Dashboard ────────────────────────────────────────────────
def cmd_dashboard(args):
    workspace = Workspace(args.workspace)
    workspace.ensure_initialized()

    idx = list_artifacts(workspace)

    # ── Artifact counts from index (single source of truth) ──────────
    # Dùng artifact index, không dùng event log, để đảm bảo các con số
    # ở dòng tổng và danh sách escalated bên dưới khớp nhau tuyệt đối.
    unique_types = set(entry.get("type", "") for entry in idx.values())
    total_versions = len(idx)
    pass_count = sum(1 for e in idx.values() if e.get("verification_status") == "pass")
    fail_count = sum(1 for e in idx.values() if e.get("verification_status") == "fail")
    escalated_count = sum(1 for e in idx.values() if e.get("verification_status") == "escalated")

    # ── Debate stats from events (only available source) ─────────────
    events = read_events(workspace)
    debate_resolved = [e for e in events if e["event_type"] == "debate_resolved"]
    consensus_pass = sum(1 for e in debate_resolved if e.get("final_decision") == "consensus_pass")
    consensus_fail = sum(1 for e in debate_resolved if e.get("final_decision") == "consensus_fail")
    no_consensus = sum(1 for e in debate_resolved if e.get("final_decision") == "no_consensus")

    # ── In bảng tổng hợp ─────────────────────────────────────────────
    print()
    print("=== Hermes Dashboard ===")
    print(f"Artifacts:    {total_versions} versions across {len(unique_types)} types "
          f"({pass_count} pass, {fail_count} fail, {escalated_count} escalated)")
    if debate_resolved:
        print(f"Debates:      {len(debate_resolved)} resolved "
              f"({consensus_pass} consensus_pass, {consensus_fail} consensus_fail, "
              f"{no_consensus} no_consensus)")

    # ── Đang chờ duyệt (escalated) ───────────────────────────────────
    escalated_artifacts = [
        entry for entry in idx.values()
        if entry.get("verification_status") == "escalated"
    ]

    if escalated_artifacts:
        now = datetime.now(timezone.utc)
        print()
        print("Đang chờ duyệt (escalated):")
        for art in escalated_artifacts:
            art_id = art["artifact_id"]
            art_type = art.get("type", "?")
            art_ver = art.get("version", "?")
            created_str = art.get("created_at", "")
            try:
                created = datetime.fromisoformat(created_str)
                wait_hours = (now - created).total_seconds() / 3600
                print(f"  {art_id} ({art_type}, v{art_ver}) — chờ {wait_hours:.1f} giờ")
            except (ValueError, TypeError):
                print(f"  {art_id} ({art_type}, v{art_ver}) — chờ ? giờ")
    else:
        print()
        print("Đang chờ duyệt (escalated): (không có)")
    print()


# ── Phase 4: Check-stale ──────────────────────────────────────────────
def cmd_check_stale(args):
    workspace = Workspace(args.workspace)
    workspace.ensure_initialized()

    events = read_events(workspace)
    idx = list_artifacts(workspace)
    now = datetime.now(timezone.utc)
    threshold_hours = float(args.threshold_hours)
    stale_found = False

    # Tìm artifact escalated và đọc timestamp escalate từ event log
    # (không thêm field mới vào Artifact Schema)
    escalated_entries = [
        entry for entry in idx.values()
        if entry.get("verification_status") == "escalated"
    ]

    print(f"Artifacts escalated quá {threshold_hours:.0f}h:")
    if not escalated_entries:
        print("  (không có artifact escalated nào)")
        sys.exit(0)

    for art in escalated_entries:
        art_id = art["artifact_id"]
        art_type = art.get("type", "?")
        art_ver = art.get("version", "?")

        # Tìm event verification_result escalated gần nhất cho artifact này
        escalated_events = [
            e for e in events
            if e["event_type"] == "verification_result"
            and e.get("artifact_id") == art_id
            and e.get("status") == "escalated"
        ]
        # Lấy timestamp escalate từ event cuối cùng
        if escalated_events:
            ts_str = escalated_events[-1].get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                wait_hours = (now - ts).total_seconds() / 3600
            except (ValueError, TypeError):
                ts = None
                wait_hours = 0
        else:
            ts = None
            wait_hours = 0

        if ts is None:
            print(f"  {art_id} ({art_type}, v{art_ver}) — không rõ thời điểm escalate")
        elif wait_hours > threshold_hours:
            print(f"  {art_id} ({art_type}, v{art_ver}) — {wait_hours:.1f}h  [QUÁ HẠN]")
            stale_found = True
        else:
            print(f"  {art_id} ({art_type}, v{art_ver}) — {wait_hours:.1f}h  [OK, chưa quá hạn]")

    sys.exit(1 if stale_found else 0)


def main():
    parser = argparse.ArgumentParser(prog="hermes", description="Hermes Engineering OS CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize a new Hermes workspace")
    init_parser.add_argument(
        "--workspace",
        default=None,
        help="Path to workspace folder (default: current directory)",
    )
    init_parser.set_defaults(func=cmd_init)

    # approve
    approve_parser = subparsers.add_parser("approve", help="Approve a escalated artifact for use")
    approve_parser.add_argument("--workspace", required=True, help="Path to Hermes workspace")
    approve_parser.add_argument("--artifact", required=True, help="Artifact ID to approve")
    approve_parser.add_argument("--version", type=int, required=True, help="Artifact version number")
    approve_parser.add_argument("--note", default=None, help="Optional note (e.g. approval number)")
    approve_parser.set_defaults(func=cmd_approve)

    # dashboard (Phase 4)
    dash_parser = subparsers.add_parser("dashboard", help="Print observability dashboard")
    dash_parser.add_argument("--workspace", required=True, help="Path to Hermes workspace")
    dash_parser.set_defaults(func=cmd_dashboard)

    # check-stale (Phase 4)
    stale_parser = subparsers.add_parser("check-stale", help="Check for escalated artifacts past threshold")
    stale_parser.add_argument("--workspace", required=True, help="Path to Hermes workspace")
    stale_parser.add_argument(
        "--threshold-hours", type=float, required=True,
        help="Max hours before an escalated artifact is considered stale",
    )
    stale_parser.set_defaults(func=cmd_check_stale)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
