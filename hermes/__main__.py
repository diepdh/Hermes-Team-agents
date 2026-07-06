"""
CLI tối thiểu cho Hermes Phase 2.

Sử dụng:
    python -m hermes init --workspace /path/to/folder
    python -m hermes approve --workspace /path --artifact lecture-lecture --version 1
"""

import argparse
import json
import sys
from pathlib import Path

from hermes.core.workspace import Workspace
from hermes.core.storage import update_verification


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
    from hermes.core.storage import list_artifacts
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
