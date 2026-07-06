"""Unit tests for Phase 3 — Debate Review Agent.

Tests cover:
- judge_consensus() pure function
- run_debate_review() with mocked agents
- finalize_verification() integration with debate_verdict
- Rubric criteria matching
"""

import json
from unittest import mock

import pytest

from hermes.pipeline.debate_review_task import (
    judge_consensus,
    build_verdict,
    run_debate_review,
)
from hermes.core.verifier import (
    finalize_verification,
    verify_artifact,
    CHECKER_REGISTRY,
)
from hermes.core.workspace import Workspace
from hermes.core.risk import get_risk_level, should_trigger_debate


# ─────────────────────────────────────────────────────────────────────
# Test: debate_verdict does not trigger another debate (recursion guard)
# ─────────────────────────────────────────────────────────────────────
def test_debate_verdict_does_not_trigger_another_debate():
    """debate_verdict must not trigger another debate (prevents recursion)."""
    # should_trigger_debate returns False for debate_verdict
    assert should_trigger_debate("debate_verdict") is False

    # run_debate_review called with debate_verdict returns immediately
    verdict = run_debate_review(
        artifact_content="any",
        artifact_id="A-guard",
        artifact_version=1,
        artifact_type="debate_verdict",
        max_rounds=3,
        workdir="/tmp",
    )
    assert verdict["final_decision"] == "consensus_pass"
    assert verdict["rounds"] == []  # No LLM calls made


# ─────────────────────────────────────────────────────────────────────
# Test 1: judge_consensus is a pure function (no LLM, no network)
# ─────────────────────────────────────────────────────────────────────
def test_judge_consensus_is_pure_function():
    """judge_consensus must be callable without any LLM/mock setup."""
    result = judge_consensus("any argument", "any response")
    assert result in ("consensus_pass", "consensus_fail", "continue")


def test_judge_consensus_opponent_concession():
    """Opponent signals no errors → consensus_pass."""
    result = judge_consensus(
        proponent_argument="Artifact is correct because X, Y, Z.",
        opponent_argument="After careful review, không có lỗi nào trong artifact này.",
    )
    assert result == "consensus_pass"


def test_judge_consensus_opponent_concession_english():
    result = judge_consensus(
        proponent_argument="Good argument.",
        opponent_argument="I agree, no errors found in this work.",
    )
    assert result == "consensus_pass"


def test_judge_consensus_proponent_concession():
    """Proponent admits error → consensus_fail."""
    result = judge_consensus(
        proponent_argument="Tôi thừa nhận sai sót trong phần citation.",
        opponent_argument="Citation section has errors.",
    )
    assert result == "consensus_fail"


def test_judge_consensus_continue():
    """No clear concession → continue."""
    result = judge_consensus(
        proponent_argument="This artifact is solid.",
        opponent_argument="I still have concerns about section 3.",
    )
    assert result == "continue"


# ─────────────────────────────────────────────────────────────────────
# Test 2: debate only triggers for high/critical risk
# ─────────────────────────────────────────────────────────────────────
def test_debate_only_triggers_for_high_critical_risk():
    """Debate should only be relevant for high and critical risk types."""
    # High risk types
    assert get_risk_level("lecture_draft") == "high"
    assert get_risk_level("quiz_bank") == "high"

    # Critical risk types
    assert get_risk_level("debate_verdict") == "critical"

    # Low/medium risk types — should NOT trigger debate
    assert get_risk_level("lit_review_md") == "low"
    assert get_risk_level("course_outline") == "medium"
    assert get_risk_level("verified_content") == "low"
    assert get_risk_level("final_content") == "medium"

    # Verify the trigger condition: risk ∈ {high, critical} AND rubric_pass
    high_critical = {"high", "critical"}
    for artifact_type in ["lecture_draft", "quiz_bank", "debate_verdict"]:
        assert get_risk_level(artifact_type) in high_critical, (
            f"{artifact_type} should be high/critical to trigger debate"
        )

    for artifact_type in ["lit_review_md", "course_outline", "final_content"]:
        assert get_risk_level(artifact_type) not in high_critical, (
            f"{artifact_type} should NOT trigger debate (low/medium risk)"
        )


# ─────────────────────────────────────────────────────────────────────
# Test 3: debate stops at max 3 rounds
# ─────────────────────────────────────────────────────────────────────
def test_debate_stops_at_max_3_rounds():
    """run_debate_review must never exceed max_rounds."""
    with mock.patch("hermes.pipeline.debate_review_task.Crew") as mock_crew_class:
        mock_crew_class.return_value = mock.MagicMock()
        # judge_consensus always returns "continue" → loop exhausts max_rounds
        with mock.patch(
            "hermes.pipeline.debate_review_task.judge_consensus",
            return_value="continue",
        ):
            with mock.patch("pathlib.Path.exists", return_value=False):
                verdict = run_debate_review(
                    artifact_content="Sample content",
                    artifact_id="A-test",
                    artifact_version=1,
                    artifact_type="lecture_draft",
                    max_rounds=3,
                    workdir="/tmp",
                )

    assert verdict["final_decision"] == "no_consensus"
    assert len(verdict["rounds"]) == 3  # exactly max_rounds, not more
    # All rounds used fallback text because Path.exists → False
    for r in verdict["rounds"]:
        assert "not found" in r["proponent_argument"] or "not found" in r["opponent_argument"]


def test_debate_stops_at_custom_max_rounds():
    """Custom max_rounds (e.g., 2) should be honored."""
    with mock.patch("hermes.pipeline.debate_review_task.Crew") as mock_crew_class:
        mock_crew_class.return_value = mock.MagicMock()
        with mock.patch(
            "hermes.pipeline.debate_review_task.judge_consensus",
            return_value="continue",
        ):
            with mock.patch("pathlib.Path.exists", return_value=False):
                verdict = run_debate_review(
                    artifact_content="Content",
                    artifact_id="A-test2",
                    artifact_version=1,
                    artifact_type="lecture_draft",
                    max_rounds=2,
                    workdir="/tmp",
                )

    assert verdict["final_decision"] == "no_consensus"
    assert len(verdict["rounds"]) == 2


# ─────────────────────────────────────────────────────────────────────
# Test 4: no_consensus maps to escalated, NOT fail or pass
# ─────────────────────────────────────────────────────────────────────
def test_no_consensus_maps_to_escalated_not_fail_not_pass(tmp_path):
    """When debate verdict is 'no_consensus', status must be 'escalated'."""
    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    from hermes.core.storage import save_artifact
    save_artifact(ws, "deb-test", "x", "lecture_draft", "T-20260706-001")
    artifact = save_artifact(ws, "deb-test", "x2", "lecture_draft", "T-20260706-001")

    rubric_result = {"passed": True, "score": 0.90, "detail": {}}
    debate_verdict = {
        "final_decision": "no_consensus",
        "rounds": [{"round": 1, "proponent_argument": "a", "opponent_argument": "b"}],
        "unresolved_issues": ["No consensus after 3 rounds"],
    }

    status = finalize_verification(
        ws,
        artifact["artifact_id"],
        artifact["version"],
        "lecture_draft",
        rubric_result,
        notes="debate test",
        rubric_pass_threshold=0.80,
        debate_verdict=debate_verdict,
    )

    assert status == "escalated", (
        f"no_consensus must map to 'escalated', got '{status}'"
    )


def test_consensus_fail_maps_to_fail(tmp_path):
    """When debate verdict is 'consensus_fail', status must be 'fail'."""
    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    from hermes.core.storage import save_artifact
    save_artifact(ws, "deb-fail", "x", "lecture_draft", "T-20260706-001")
    artifact = save_artifact(ws, "deb-fail", "x2", "lecture_draft", "T-20260706-001")

    rubric_result = {"passed": True, "score": 0.90, "detail": {}}
    debate_verdict = {
        "final_decision": "consensus_fail",
        "rounds": [{"round": 1, "proponent_argument": "x", "opponent_argument": "y"}],
    }

    status = finalize_verification(
        ws,
        artifact["artifact_id"],
        artifact["version"],
        "lecture_draft",
        rubric_result,
        notes="debate fail test",
        rubric_pass_threshold=0.80,
        debate_verdict=debate_verdict,
    )

    assert status == "fail", f"consensus_fail must map to 'fail', got '{status}'"


def test_consensus_pass_maps_to_escalated_for_human_gate(tmp_path):
    """For human-gate types, consensus_pass → escalated (still needs human)."""
    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    from hermes.core.storage import save_artifact
    save_artifact(ws, "deb-pass-hg", "x", "lecture_draft", "T-20260706-001")
    artifact = save_artifact(ws, "deb-pass-hg", "x2", "lecture_draft", "T-20260706-001")

    rubric_result = {"passed": True, "score": 0.95, "detail": {}}
    debate_verdict = {
        "final_decision": "consensus_pass",
        "rounds": [{"round": 1, "proponent_argument": "a", "opponent_argument": "b"}],
    }

    status = finalize_verification(
        ws,
        artifact["artifact_id"],
        artifact["version"],
        "lecture_draft",
        rubric_result,
        notes="debate pass + human gate",
        rubric_pass_threshold=0.80,
        debate_verdict=debate_verdict,
    )

    assert status == "escalated", (
        f"consensus_pass for human-gate type must escalate, got '{status}'"
    )


# ─────────────────────────────────────────────────────────────────────
# Test 5: early stop — consensus after round 1 does not run round 2
# ─────────────────────────────────────────────────────────────────────
def test_consensus_pass_after_round_1_does_not_run_round_2():
    """Debate must stop early when consensus is reached in round 1."""
    with mock.patch("hermes.pipeline.debate_review_task.Crew") as mock_crew_class:
        mock_crew_class.return_value = mock.MagicMock()
        # judge_consensus returns "consensus_pass" on first call
        with mock.patch(
            "hermes.pipeline.debate_review_task.judge_consensus",
            return_value="consensus_pass",
        ):
            with mock.patch("pathlib.Path.exists", return_value=False):
                verdict = run_debate_review(
                    artifact_content="Test content",
                    artifact_id="A-early",
                    artifact_version=1,
                    artifact_type="lecture_draft",
                    max_rounds=3,
                    workdir="/tmp",
                )

    assert verdict["final_decision"] == "consensus_pass"
    assert len(verdict["rounds"]) == 1
    # Crew should only be instantiated once (1 round)
    assert mock_crew_class.call_count == 1


# ─────────────────────────────────────────────────────────────────────
# Test: rubric criteria names match verifier for debate_verdict
# ─────────────────────────────────────────────────────────────────────
def test_rubric_criteria_names_match_verifier_debate_verdict():
    """Every criterion in R-debate-verdict-v1 must appear in verifier output."""
    from hermes.rubrics import load_rubric

    rubric = load_rubric("debate_verdict")
    # Sample debate verdict as dict
    sample_verdict = {
        "artifact_type": "debate_verdict",
        "target_artifact_id": "A-test",
        "target_artifact_version": 1,
        "target_artifact_type": "lecture_draft",
        "rounds": [
            {
                "round": 1,
                "proponent_argument": "The artifact is academically sound.",
                "opponent_argument": "I agree, no errors found.",
            }
        ],
        "final_decision": "consensus_pass",
        "unresolved_issues": [],
    }

    # Pass as JSON string
    result = verify_artifact("debate_verdict", json.dumps(sample_verdict), rubric)
    missing = []
    for criterion in rubric["criteria"]:
        if criterion["name"] not in result["detail"]:
            missing.append(criterion["name"])
    assert not missing, (
        f"debate_verdict criteria not scored: {missing}. "
        f"Verifier returned: {list(result['detail'].keys())}"
    )


# ─────────────────────────────────────────────────────────────────────
# Test: build_verdict produces correct structure
# ─────────────────────────────────────────────────────────────────────
def test_build_verdict_consensus_pass():
    verdict = build_verdict("A-001", 1, "lecture_draft", [
        {"round": 1, "proponent_argument": "Good", "opponent_argument": "Agree — no errors"}
    ], "consensus_pass")
    assert verdict["final_decision"] == "consensus_pass"
    assert len(verdict["rounds"]) == 1
    assert verdict["unresolved_issues"] == []


def test_build_verdict_no_consensus():
    verdict = build_verdict("A-002", 2, "quiz_bank", [
        {"round": 1, "proponent_argument": "X", "opponent_argument": "Y"},
        {"round": 2, "proponent_argument": "X2", "opponent_argument": "Y2"},
        {"round": 3, "proponent_argument": "X3", "opponent_argument": "Y3"},
    ], "no_consensus")
    assert verdict["final_decision"] == "no_consensus"
    assert len(verdict["rounds"]) == 3
    assert len(verdict["unresolved_issues"]) > 0


# ─────────────────────────────────────────────────────────────────────
# Test: run_debate_review outputs valid debate_verdict JSON
# ─────────────────────────────────────────────────────────────────────
def test_run_debate_review_output_valid_schema():
    """The output of run_debate_review must be a valid debate_verdict."""
    with mock.patch("hermes.pipeline.debate_review_task.Crew") as mock_crew_class:
        mock_crew_class.return_value = mock.MagicMock()
        with mock.patch(
            "hermes.pipeline.debate_review_task.judge_consensus",
            return_value="consensus_pass",
        ):
            with mock.patch("pathlib.Path.exists", return_value=False):
                verdict = run_debate_review(
                    artifact_content="Content",
                    artifact_id="A-schema",
                    artifact_version=1,
                    artifact_type="quiz_bank",
                    max_rounds=2,
                    workdir="/tmp",
                )

    assert verdict["artifact_type"] == "debate_verdict"
    assert verdict["target_artifact_id"] == "A-schema"
    assert verdict["final_decision"] in ("consensus_pass", "consensus_fail", "no_consensus")
    assert "rounds" in verdict
    assert "unresolved_issues" in verdict


# ─────────────────────────────────────────────────────────────────────
# Test: pipeline triggers debate for high-risk artifact end-to-end
# ─────────────────────────────────────────────────────────────────────
def test_pipeline_triggers_debate_for_high_risk_artifact_end_to_end(tmp_path):
    """When a high-risk artifact passes rubric, the pipeline must
    automatically call run_debate_review() before returning."""
    from unittest import mock
    from hermes.core.workspace import Workspace
    from hermes.pipeline.full_lecture_pipeline import run_stage

    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    rubric = {"pass_threshold": 0.80, "criteria": []}

    mock_debate_verdict = {
        "final_decision": "consensus_pass",
        "rounds": [{"round": 1, "proponent_argument": "Good.", "opponent_argument": "No errors."}],
    }

    fake_artifact = {
        "artifact_id": "pipeline-debate-test",
        "version": 1,
        "type": "lecture_draft",
        "content_ref": ".hermes/artifacts/pipeline-debate-test_v1.md",
        "produced_by_task": "T-20260706-001",
        "verification_status": "pending",
        "verification_notes": "",
    }

    with mock.patch("hermes.pipeline.full_lecture_pipeline.Crew") as mock_crew_class:
        mock_crew_class.return_value = mock.MagicMock()
        # Mock content file read
        with mock.patch("pathlib.Path.read_text", return_value="x " * 400):
            # Mock save_artifact to avoid JSON decode issues on index.json
            with mock.patch(
                "hermes.pipeline.full_lecture_pipeline.save_artifact",
                return_value=fake_artifact,
            ):
                # Mock verify_artifact to return pass
                with mock.patch(
                    "hermes.pipeline.full_lecture_pipeline.verify_artifact",
                    return_value={"passed": True, "score": 0.95, "detail": {}},
                ):
                    # Mock run_debate_review to track calls
                    with mock.patch(
                        "hermes.pipeline.full_lecture_pipeline.run_debate_review",
                        return_value=mock_debate_verdict,
                    ) as mock_debate:
                        with mock.patch(
                            "hermes.pipeline.full_lecture_pipeline.finalize_verification",
                            return_value="escalated",
                        ):
                            def fake_agent_builder(provider=None):
                                return mock.MagicMock()
                            def fake_task_builder(agent, output_path=None):
                                return mock.MagicMock()

                            stage_result = run_stage(
                                workspace=ws,
                                agent_builder=fake_agent_builder,
                                task_builder=fake_task_builder,
                                artifact_type="lecture_draft",
                                rubric=rubric,
                                produced_by_task="pipeline-debate-test",
                                provider=None,
                                max_retries=0,
                            )

    # Assertions
    mock_debate.assert_called_once()
    call_args = mock_debate.call_args[1]
    assert call_args["artifact_id"] == "pipeline-debate-test"
    assert call_args["artifact_type"] == "lecture_draft"
    assert stage_result["escalated"] is True
    assert stage_result["stage"] == "lecture_draft"


def test_pipeline_skips_debate_for_low_risk_artifact(tmp_path):
    """Low-risk artifacts (e.g., lit_review_md) should NOT trigger debate."""
    from unittest import mock
    from hermes.core.workspace import Workspace
    from hermes.pipeline.full_lecture_pipeline import run_stage

    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    rubric = {"pass_threshold": 0.70, "criteria": []}
    fake_artifact = {"artifact_id": "low", "version": 1, "content_ref": "x"}

    with mock.patch("hermes.pipeline.full_lecture_pipeline.Crew") as mock_crew:
        mock_crew.return_value = mock.MagicMock()
        with mock.patch("pathlib.Path.read_text", return_value="x " * 200):
            with mock.patch("hermes.pipeline.full_lecture_pipeline.save_artifact", return_value=fake_artifact):
                with mock.patch("hermes.pipeline.full_lecture_pipeline.verify_artifact",
                                return_value={"passed": True, "score": 0.90, "detail": {}}):
                    with mock.patch("hermes.pipeline.full_lecture_pipeline.run_debate_review") as mock_debate:
                        with mock.patch("hermes.pipeline.full_lecture_pipeline.finalize_verification", return_value="pass"):
                            run_stage(ws, lambda p=None: mock.MagicMock(), lambda a, **kw: mock.MagicMock(),
                                      "lit_review_md", rubric, "low", None, max_retries=0)

    mock_debate.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# Test: debate_verdict is actually persisted to Artifact Store
# ─────────────────────────────────────────────────────────────────────
def test_debate_verdict_persisted_to_store_after_debate(tmp_path):
    """After _maybe_run_debate, the verdict must be retrievable from
    the Artifact Store using the same API the approve command uses."""
    import json
    from unittest import mock
    from hermes.core.workspace import Workspace
    from hermes.core.storage import save_artifact, get_artifact, read_artifact_content
    from hermes.pipeline.full_lecture_pipeline import _maybe_run_debate

    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    # Create the target artifact first (simulating what run_stage does)
    target = save_artifact(
        ws, "lecture-debate-test", "Lecture content here...",
        "lecture_draft", "T-20260706-001",
    )

    rubric = {"pass_threshold": 0.80, "criteria": []}
    result = {"passed": True, "score": 0.90, "detail": {}}

    mock_verdict = {
        "artifact_type": "debate_verdict",
        "target_artifact_id": "lecture-debate-test",
        "target_artifact_version": target["version"],
        "rounds": [
            {"round": 1, "proponent_argument": "Solid defense.", "opponent_argument": "No errors — agree."}
        ],
        "final_decision": "consensus_pass",
        "unresolved_issues": [],
    }

    with mock.patch(
        "hermes.pipeline.full_lecture_pipeline.run_debate_review",
        return_value=mock_verdict,
    ):
        with mock.patch(
            "hermes.pipeline.full_lecture_pipeline.finalize_verification",
            return_value="escalated",
        ):
            new_status = _maybe_run_debate(
                ws, target, "lecture_draft", "content", result, rubric,
                provider=None, notes="test",
            )

    assert new_status == "escalated"

    # ── NOW READ BACK FROM THE REAL ARTIFACT STORE ──────────────
    verdict_from_store = get_artifact(ws, "lecture-debate-test-debate")
    assert verdict_from_store is not None, "debate_verdict NOT FOUND in Artifact Store!"
    assert verdict_from_store["type"] == "debate_verdict"
    assert verdict_from_store["version"] == 1
    assert verdict_from_store["verification_status"] == "pending"

    # Verify target_artifact metadata
    meta = verdict_from_store.get("metadata", {})
    assert meta.get("target_artifact_id") == "lecture-debate-test"
    assert meta.get("target_artifact_version") == target["version"]
    assert meta.get("target_artifact_type") == "lecture_draft"

    # Read actual content
    content = read_artifact_content(ws, verdict_from_store)
    parsed = json.loads(content)
    assert parsed["final_decision"] == "consensus_pass"
    assert len(parsed["rounds"]) == 1
    assert "No errors" in parsed["rounds"][0]["opponent_argument"]
