"""
CLI tối thiểu cho Hermes Phase 0.5.

Sử dụng:
    python -m hermes init --workspace /path/to/folder
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.core.workspace import Workspace


def cmd_init(args):
    workspace = Workspace(args.workspace)
    workspace.ensure_initialized()
    print(f"Initialized Hermes workspace at: {workspace.root}")
    print(f"  config: {workspace.config_path}")
    print(f"  artifacts: {workspace.artifact_dir}")
    print(f"  tasks: {workspace.task_dir}")
    print(f"  rubrics: {workspace.rubric_dir}")
    print(f"  logs: {workspace.log_dir}")


def main():
    parser = argparse.ArgumentParser(prog="hermes", description="Hermes Engineering OS CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a new Hermes workspace")
    init_parser.add_argument(
        "--workspace",
        default=None,
        help="Path to workspace folder (default: current directory)",
    )
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
