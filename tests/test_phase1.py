"""Unit tests for Hermes Phase 1: Researcher, Verifier, Pipeline.

These tests mock the LLM call so they run quickly and do not require API keys.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.core.workspace import Workspace
from hermes.core.verifier import check_lit_review
from hermes.pipeline.lit_review_pipeline import run_lit_review_pipeline


SAMPLE_RUBRIC = {
    "name": "Test Lit Review Rubric",
    "pass_threshold": 0.7,
    "criteria": [
        {"name": "citation_completeness", "weight": 0.35},
        {"name": "relevance_summary", "weight": 0.25},
        {"name": "gaps_section", "weight": 0.20},
        {"name": "formatting_clarity", "weight": 0.20},
    ],
}


def _make_temp_workspace() -> Workspace:
    tmpdir = tempfile.mkdtemp(prefix="hermes_test_")
    return Workspace(tmpdir)


def sample_lit_review():
    return (
        "# Summary\n\n"
        "This review summarizes prior work on immediate feedback.\n"
        "Smith (2020) found positive effects; Doe (2021) refined the model.\n\n"
        "# Citations\n\n"
        "Doe, J. (2021). Feedback and learning. *Journal of Education*, 12(3), 1–10.\n\n"
        "Johnson, R. (2019). Learning strategies. *Ed Rev*, 8(2), 20–30.\n\n"
        "Smith, A. (2020). Immediate feedback. *Learning Sci*, 5(1), 100–120.\n\n"
        "# Gaps Identified\n\n"
        "Most studies are short-term and lack longitudinal follow-up.\n"
    )


def test_verifier_scores_complete_artifact():
    result = check_lit_review(sample_lit_review(), SAMPLE_RUBRIC)
    assert result["passed"] is True
    assert result["score"] >= 0.7
    assert result["detail"]["citation_completeness"] >= 0.6
    assert result["detail"]["relevance_summary"] == 1.0
    assert result["detail"]["gaps_section"] == 1.0
    assert result["detail"]["formatting_clarity"] >= 0.5


def test_verifier_fails_missing_citations():
    content = sample_lit_review()
    # Remove all author-year citations and standalone years.
    for token in ["Smith", "Doe", "Johnson", "2020", "2021", "2019"]:
        content = content.replace(token, "X")
    result = check_lit_review(content, SAMPLE_RUBRIC)
    assert result["passed"] is False
    assert result["detail"]["citation_completeness"] < 0.5


def test_verifier_fails_missing_summary():
    content = sample_lit_review().replace("# Summary", "# Overview")
    result = check_lit_review(content, SAMPLE_RUBRIC)
    assert result["detail"]["relevance_summary"] == 0.0


def test_verifier_fails_missing_gaps():
    content = sample_lit_review().replace("# Gaps Identified", "# Future Work")
    result = check_lit_review(content, SAMPLE_RUBRIC)
    assert result["detail"]["gaps_section"] == 0.0


def test_pipeline_mocked_kickoff_passes_first_attempt(tmp_path):
    ws = Workspace(tmp_path)
    ws.ensure_initialized()

    good_content = sample_lit_review()

    def fake_kickoff(_self):
        output_path = _self.tasks[0].output_file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(good_content)
        return None

    with patch("hermes.pipeline.lit_review_pipeline.Crew.kickoff", fake_kickoff):
        artifact, result, metrics = run_lit_review_pipeline(
            workspace_root=str(tmp_path),
            research_question="What is spaced practice?",
            task_id="T-test-002",
            artifact_id="A-test-002",
            rubric=SAMPLE_RUBRIC,
            provider="opencode_go",
            max_retries=0,
        )

    assert artifact["artifact_id"] == "A-test-002"
    assert artifact["version"] == 1
    assert result["passed"] is True
    assert result["score"] >= SAMPLE_RUBRIC["pass_threshold"]
    assert metrics["elapsed_seconds"] >= 0


def test_pipeline_passes_first_attempt(tmp_path, monkeypatch):
    """Pipeline should pass on first attempt with a high-quality mock response."""
    # Covered by test_pipeline_mocked_kickoff_passes_first_attempt.
    pass


def test_pipeline_retry_then_pass(tmp_path):
    ws = Workspace(tmp_path)
    ws.ensure_initialized()

    bad_content = "# Summary\n\nToo short.\n\n# Citations\n\n# Gaps Identified\n"
    good_content = sample_lit_review()

    outputs = [bad_content, good_content]

    def fake_kickoff(_self):
        output_path = _self.tasks[0].output_file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(outputs.pop(0))
        return None

    with patch("hermes.pipeline.lit_review_pipeline.Crew.kickoff", fake_kickoff):
        artifact, result, metrics = run_lit_review_pipeline(
            workspace_root=str(tmp_path),
            research_question="What is retrieval practice?",
            task_id="T-test-003",
            artifact_id="A-test-003",
            rubric=SAMPLE_RUBRIC,
            provider="opencode_go",
            max_retries=2,
        )

    assert artifact["version"] == 2
    assert result["passed"] is True


def test_pipeline_escalates_after_max_retries(tmp_path):
    ws = Workspace(tmp_path)
    ws.ensure_initialized()

    bad_content = "# Summary\n\nToo short.\n\n# Citations\n\n# Gaps Identified\n"

    def fake_kickoff(_self):
        output_path = _self.tasks[0].output_file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(bad_content)
        return None

    with patch("hermes.pipeline.lit_review_pipeline.Crew.kickoff", fake_kickoff):
        artifact, result, metrics = run_lit_review_pipeline(
            workspace_root=str(tmp_path),
            research_question="What is metacognition?",
            task_id="T-test-004",
            artifact_id="A-test-004",
            rubric=SAMPLE_RUBRIC,
            provider="opencode_go",
            max_retries=1,
        )

    assert result["passed"] is False
    # Retry increments attempt; max_retries counts retries AFTER the first attempt,
    # so with max_retries=1 we should see at most 2 attempts total.
    assert artifact["version"] <= 2  # initial + up to 1 retry


def test_llm_config_registry():
    """Verify the LLM config registry loads correct credentials per provider."""
    from hermes.core.llm_config import list_providers, get_llm_config

    providers = list_providers()
    assert "opencode_go" in providers
    assert "local_cx" in providers
    assert len(providers) >= 2

    cfg = get_llm_config("opencode_go")
    assert "model" in cfg
    assert "api_key" in cfg
    assert "max_tokens" in cfg
    assert cfg["max_tokens"] >= 1000


def test_rubric_criteria_names_match_verifier():
    """Every criterion in the rubric must appear in verifier output.

    This guards against silent drops where a rubric criterion is never scored
    due to a name mismatch between the rubric definition and the verifier code.
    """
    import json
    from pathlib import Path

    rubric_path = Path(__file__).resolve().parent.parent / "rubrics" / "R-lit-review-v2.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))

    # A representative complete artifact (passes all checks).
    sample = """# Summary

    This review summarizes key findings on formative assessment in higher
    education. Researchers (Smith, 2020) and (Doe, 2021) demonstrate that
    ongoing feedback improves student outcomes. Johnson (2019) identifies
    remaining gaps in longitudinal studies.

    # Citations

    - Smith, J. (2020). Formative assessment methods. *Journal of Education*.
    - Doe, A. (2021). Feedback and learning outcomes. *Educational Review*.
    - Johnson, B. (2019). Gaps in assessment research. *Higher Education*.

    # Gaps Identified

    Most existing studies focus on short-term effects; long-term impact
    of formative assessment on graduate outcomes remains underexplored.
    """

    result = check_lit_review(sample, rubric)

    for criterion in rubric["criteria"]:
        name = criterion["name"]
        assert name in result["detail"], (
            f"Criteria '{name}' not scored by verifier — "
            f"possible silent drop due to name mismatch. "
            f"Verifier returned: {list(result['detail'].keys())}"
        )


if __name__ == "__main__":
    test_verifier_scores_complete_artifact()
    test_verifier_fails_missing_citations()
    test_verifier_fails_missing_summary()
    test_verifier_fails_missing_gaps()
    test_pipeline_mocked_kickoff_passes_first_attempt(Workspace(tempfile.mkdtemp()))
    test_pipeline_retry_then_pass(Workspace(tempfile.mkdtemp()))
    test_pipeline_escalates_after_max_retries(Workspace(tempfile.mkdtemp()))
    test_llm_config_registry()
    print("All Phase 1 tests passed.")
