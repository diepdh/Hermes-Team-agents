"""
Debate Review Task for Hermes Phase 3.

Orchestrates a bounded multi-round debate between Proponent and Opponent
agents to validate high-risk artifacts before they are used downstream.

Key design decisions (per Phase 3 spec):
- judge_consensus() is a PURE function — no LLM calls inside control loop
- Max 3 rounds; stop early on consensus_pass or consensus_fail
- "no_consensus" after max_rounds → escalated (human decides)
- Only triggers for risk ∈ {high, critical} AND rubric_pass = True
"""

from pathlib import Path

from crewai import Crew, Process
from crewai.project import CrewBase


# ─────────────────────────────────────────────────────────────────────
# Pure function: consensus detection (no LLM calls — testable)
# ─────────────────────────────────────────────────────────────────────
def judge_consensus(proponent_argument: str, opponent_argument: str) -> str:
    """
    Determine debate outcome from a single round's arguments.

    This is a PURE function — no LLM calls, no network I/O, fully
    deterministic.  It uses lightweight heuristics on the argument text
    to decide whether consensus has been reached.

    Returns one of:
      - "consensus_pass"   — opponent concedes or finds no material errors
      - "consensus_fail"   — proponent concedes or cannot defend
      - "continue"         — no consensus yet, continue to next round

    Heuristics (designed to be cheap and reproducible):
      - Opponent signals concession → consensus_pass
      - Proponent signals inability to defend → consensus_fail
      - Both acknowledge agreement → consensus_pass
      - Otherwise → continue
    """
    prop_lower = proponent_argument.lower()
    opp_lower = opponent_argument.lower()

    # ── Opponent concession patterns ─────────────────────────────────
    opp_concession = (
        "không có lỗi" in opp_lower
        or "khong co loi" in opp_lower
        or "no errors found" in opp_lower
        or "đồng ý với lập luận" in opp_lower
        or "dong y voi lap luan" in opp_lower
        or "i agree" in opp_lower
        or "no significant issues" in opp_lower
        or "không tìm thấy vấn đề" in opp_lower
        or "artifact is correct" in opp_lower
    )

    # ── Proponent concession patterns ────────────────────────────────
    prop_concession = (
        "thừa nhận sai sót" in prop_lower
        or "thua nhan sai sot" in prop_lower
        or "i concede" in prop_lower
        or "cannot defend" in prop_lower
        or "không thể bảo vệ" in prop_lower
        or "khong the bao ve" in prop_lower
        or "artifact có lỗi" in prop_lower
        or "artifact co loi" in prop_lower
    )

    # ── Mutual agreement patterns ────────────────────────────────────
    mutual_agree = (
        ("đồng ý" in prop_lower or "dong y" in prop_lower or "agree" in prop_lower)
        and ("đồng ý" in opp_lower or "dong y" in opp_lower or "agree" in opp_lower)
    )

    # ── Resolution ───────────────────────────────────────────────────
    if opp_concession:
        return "consensus_pass"
    if prop_concession:
        return "consensus_fail"
    if mutual_agree:
        # If both agree, assume the opponent's assessment is the tiebreaker:
        # opponent tends to agree when artifact is correct → pass
        return "consensus_pass"

    return "continue"


# ─────────────────────────────────────────────────────────────────────
# Debate verdict builder
# ─────────────────────────────────────────────────────────────────────
def build_verdict(
    target_artifact_id: str,
    target_artifact_version: int,
    target_artifact_type: str,
    rounds: list,
    final_decision: str,
) -> dict:
    """
    Build a debate_verdict artifact record.

    Args:
        target_artifact_id: The artifact being debated.
        target_artifact_version: Version of the target artifact.
        target_artifact_type: Type of the target artifact.
        rounds: List of round dicts with proponent_argument / opponent_argument.
        final_decision: "consensus_pass" | "consensus_fail" | "no_consensus"

    Returns:
        A debate_verdict dict matching the schema.
    """
    unresolved = []
    if final_decision == "no_consensus":
        unresolved = [
            f"Debate ended without consensus after {len(rounds)} round(s). "
            f"Human review required."
        ]

    return {
        "artifact_type": "debate_verdict",
        "target_artifact_id": target_artifact_id,
        "target_artifact_version": target_artifact_version,
        "target_artifact_type": target_artifact_type,
        "rounds": rounds,
        "final_decision": final_decision,
        "unresolved_issues": unresolved,
    }


# ─────────────────────────────────────────────────────────────────────
# Run debate review (main entry point)
# ─────────────────────────────────────────────────────────────────────
def run_debate_review(
    artifact_content: str,
    artifact_id: str,
    artifact_version: int,
    artifact_type: str,
    provider: str | None = None,
    max_rounds: int = 3,
    workdir: str | None = None,
) -> dict:
    """
    Run bounded multi-round debate review for a high/critical-risk artifact.

    Args:
        artifact_content: Full text content of the artifact under review.
        artifact_id: Artifact identifier.
        artifact_version: Version number of the artifact.
        artifact_type: The artifact type string (e.g. "lecture_draft").
        provider: LLM provider key.
        max_rounds: Maximum debate rounds (default 3).
        workdir: Working directory for output files.

    Returns:
        A debate_verdict dict.
    """
    from hermes.agents.debate_proponent import (
        build_proponent_agent,
        build_proponent_argument_task,
    )
    from hermes.agents.debate_opponent import (
        build_opponent_agent,
        build_opponent_argument_task,
    )

    # Guard: never debate a debate_verdict itself (prevents recursion)
    from hermes.core.risk import SKIP_DEBATE_TYPES
    if artifact_type in SKIP_DEBATE_TYPES:
        return build_verdict(
            artifact_id, artifact_version, artifact_type, [],
            "consensus_pass",
        )

    workpath = Path(workdir) if workdir else Path(".")

    rounds: list[dict] = []

    for i in range(1, max_rounds + 1):
        # ── Build fresh agents each round (clean context) ────────────
        prop_agent = build_proponent_agent(provider)
        opp_agent = build_opponent_agent(provider)

        prop_task = build_proponent_argument_task(
            prop_agent,
            artifact_content=artifact_content,
            artifact_type=artifact_type,
            previous_rounds=rounds if rounds else None,
            output_path=str(workpath / f"debate_round_{i}_proponent.md"),
        )
        opp_task = build_opponent_argument_task(
            opp_agent,
            artifact_content=artifact_content,
            artifact_type=artifact_type,
            previous_rounds=rounds if rounds else None,
            output_path=str(workpath / f"debate_round_{i}_opponent.md"),
        )

        # Run proponent and opponent in sequence within one Crew
        crew = Crew(
            agents=[prop_agent, opp_agent],
            tasks=[prop_task, opp_task],
            process=Process.sequential,
        )
        crew.kickoff()
        crew.calculate_usage_metrics()

        # Read output files
        prop_output_path = workpath / f"debate_round_{i}_proponent.md"
        opp_output_path = workpath / f"debate_round_{i}_opponent.md"

        prop_arg = (
            prop_output_path.read_text(encoding="utf-8")
            if prop_output_path.exists()
            else "[Proponent output not found]"
        )
        opp_arg = (
            opp_output_path.read_text(encoding="utf-8")
            if opp_output_path.exists()
            else "[Opponent output not found]"
        )

        rounds.append({
            "round": i,
            "proponent_argument": prop_arg,
            "opponent_argument": opp_arg,
        })

        # ── Judge consensus (pure function, no LLM) ──────────────────
        decision = judge_consensus(prop_arg, opp_arg)
        if decision in ("consensus_pass", "consensus_fail"):
            return build_verdict(
                artifact_id, artifact_version, artifact_type, rounds, decision
            )

    # Exhausted max_rounds without consensus
    return build_verdict(
        artifact_id, artifact_version, artifact_type, rounds, "no_consensus"
    )
