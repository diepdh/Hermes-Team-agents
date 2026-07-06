"""
pytest configuration: ensure hermes package is importable via sys.path.

Uses the repo root (where this file lives) as the package root, matching
the layout: hermes/workspace, hermes/core, hermes/agents, etc.
"""

import sys
from pathlib import Path

# Repo root is the directory containing this file's parent (hermes/)
REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
