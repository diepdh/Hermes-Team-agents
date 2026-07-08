"""Unit tests for Phase 5.2.5 — Literature Researcher subagent."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.literature_researcher import (
    build_literature_support,
    literature_support_to_json,
    run_literature_researcher,
)
from hermes.core.verifier import CHECKER_REGISTRY, verify_artifact
from hermes.core.workspace import Workspace
from hermes.core.risk import RISK_MATRIX
from hermes.rubrics import load_rubric


def test_literature_support_registered_in_risk_matrix():
    assert RISK_MATRIX["literature_support"] == "high"


def test_literature_support_registered_in_checker():
    assert "literature_support" in CHECKER_REGISTRY


def test_literature_support_rubric_pass_with_real_entries():
    rubric = load_rubric("literature_support")
    artifact = json.dumps({
        "artifact_type": "literature_support",
        "queries_used": ["formative assessment", "feedback methods"],
        "search_attempted": True,
        "entries": [
            {
                "title": "Real Paper Title",
                "authors": "Smith, J.",
                "year": "2020",
                "venue": "Journal of Education",
                "url": "https://doi.org/10.1234/example",
                "excerpt": "This is a real abstract excerpt from the API.",
            }
        ],
    })
    result = verify_artifact("literature_support", artifact, rubric)
    assert result["passed"] is True
    assert result["detail"]["has_url_for_all"] == 1.0
    assert result["detail"]["has_excerpt_for_all"] == 1.0
    assert result["detail"]["search_attempted"] == 1.0


def test_literature_support_rubric_pass_with_empty_entries():
    """Empty entries is a valid result — rubric must not penalize it."""
    rubric = load_rubric("literature_support")
    artifact = json.dumps({
        "artifact_type": "literature_support",
        "queries_used": ["obscure topic with no papers"],
        "search_attempted": True,
        "search_error": None,
        "entries": [],
    })
    result = verify_artifact("literature_support", artifact, rubric)
    assert result["passed"] is True
    assert result["detail"]["search_attempted"] == 1.0


def test_literature_support_rubric_fail_missing_url():
    rubric = load_rubric("literature_support")
    artifact = json.dumps({
        "artifact_type": "literature_support",
        "queries_used": ["test"],
        "search_attempted": True,
        "entries": [{"title": "T", "authors": "X", "year": "2020", "url": "", "excerpt": "ok"}],
    })
    result = verify_artifact("literature_support", artifact, rubric)
    assert result["detail"]["has_url_for_all"] == 0.0


def test_literature_support_rubric_fail_search_not_attempted():
    rubric = load_rubric("literature_support")
    artifact = json.dumps({
        "artifact_type": "literature_support",
        "queries_used": [],
        "search_attempted": False,
        "search_error": None,
        "entries": [],
    })
    result = verify_artifact("literature_support", artifact, rubric)
    assert result["detail"]["search_attempted"] == 0.0


def test_literature_support_rubric_fail_search_error():
    """When API fails (search_error != None), search_attempted must be 0.0."""
    rubric = load_rubric("literature_support")
    artifact = json.dumps({
        "artifact_type": "literature_support",
        "queries_used": ["transformer"],
        "search_attempted": True,
        "search_error": "rate_limited: 429 after 3 retries",
        "entries": [],
    })
    result = verify_artifact("literature_support", artifact, rubric)
    assert result["detail"]["search_attempted"] == 0.0
    assert result["passed"] is False  # score = 0.4+0.4+0.0 = 0.8 < 0.9


def test_literature_support_persisted_through_save_artifact(tmp_path):
    from hermes.core.storage import save_artifact, get_artifact, read_artifact_content

    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    content = literature_support_to_json({
        "artifact_type": "literature_support",
        "queries_used": ["formative assessment"],
        "search_attempted": True,
        "entries": [],
    })
    artifact = save_artifact(
        workspace=ws,
        artifact_id="lit-support-persist",
        content=content,
        artifact_type="literature_support",
        produced_by_task="T-lit-researcher-test",
    )
    assert artifact["type"] == "literature_support"

    retrieved = get_artifact(ws, "lit-support-persist", artifact["version"])
    assert retrieved is not None
    read_back = read_artifact_content(ws, retrieved)
    assert "search_attempted" in read_back
