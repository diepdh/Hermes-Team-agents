"""
Phase 1 pipeline: Researcher -> Verifier -> Retry loop.

Produces a literature-review artifact for a research question, evaluates it
with a rule-based rubric, and retries with diagnostic feedback if it fails.
"""

import json
import time
from pathlib import Path
from typing import Tuple

from crewai import Crew, Process

try:
    from hermes.agents.researcher import build_researcher_agent, build_lit_review_task
    from hermes.core.workspace import Workspace
    from hermes.core.storage import save_artifact, update_verification
    from hermes.core.verifier import check_lit_review
except ModuleNotFoundError:  # pragma: no cover - supports running without package install
    from agents.researcher import build_researcher_agent, build_lit_review_task
    from core.workspace import Workspace
    from core.storage import save_artifact, update_verification
    from core.verifier import check_lit_review


def run_lit_review_pipeline(
    workspace_root: str,
    research_question: str,
    task_id: str,
    artifact_id: str,
    rubric: dict,
    attempt: int = 1,
    max_retries: int = 2,
) -> Tuple[dict, dict]:
    """Run one literature-review pipeline iteration including verification.

    Args:
        workspace_root: Path to the Hermes workspace.
        research_question: The research question to answer.
        task_id: Task identifier to link the artifact to.
        artifact_id: Artifact identifier (will be versioned automatically).
        rubric: Rubric dictionary with criteria and pass_threshold.
        attempt: Current attempt number (starts at 1).
        max_retries: Maximum number of retry attempts after the first failure.

    Returns:
        Tuple of (artifact_record, verification_result).
    """
    ws = Workspace(workspace_root)
    ws.ensure_initialized()

    agent = build_researcher_agent()
    output_path = str(ws.artifact_dir / f"{artifact_id}_v{attempt}.md")
    task_def = build_lit_review_task(agent, research_question, output_path)

    crew = Crew(agents=[agent], tasks=[task_def], process=Process.sequential)
    crew.kickoff()

    with open(output_path, encoding="utf-8") as f:
        content = f.read()

    artifact = save_artifact(
        workspace=ws,
        artifact_id=artifact_id,
        content=content,
        artifact_type="lit_review_md",
        produced_by_task=task_id,
    )

    result = check_lit_review(content, rubric)
    status = "pass" if result["passed"] else "fail"
    update_verification(
        ws,
        artifact_id,
        artifact["version"],
        status,
        notes=json.dumps(result["detail"], ensure_ascii=False),
    )

    if result["passed"]:
        print(f"[PASS] {artifact_id} v{artifact['version']} -- score {result['score']}")
        return artifact, result

    print(f"[FAIL] {artifact_id} v{artifact['version']} -- score {result['score']} -- {result['detail']}")
    if attempt < max_retries:
        retry_question = (
            f"{research_question}\n\n"
            f"[Ghi chu tu lan truoc -- can khac phuc]: "
            f"{json.dumps(result['detail'], ensure_ascii=False)}"
        )
        return run_lit_review_pipeline(
            workspace_root,
            retry_question,
            task_id,
            artifact_id,
            rubric,
            attempt=attempt + 1,
            max_retries=max_retries,
        )

    print(f"[ESCALATED] {artifact_id} sau {max_retries} lan van fail -- can nguoi xem lai")
    return artifact, result


def run_lit_review_with_baseline(
    workspace_root: str,
    research_question: str,
    task_id: str,
    artifact_id: str,
    rubric: dict,
    run_id: str,
    max_retries: int = 2,
) -> dict:
    """Run the pipeline and record token/time baseline metrics.

    Returns a dictionary suitable for appending to logs/phase1_baseline.json.
    """
    ws = Workspace(workspace_root)
    ws.ensure_initialized()

    start = time.time()
    artifact, result = run_lit_review_pipeline(
        workspace_root, research_question, task_id, artifact_id, rubric,
        attempt=1, max_retries=max_retries,
    )
    elapsed = round(time.time() - start, 2)

    # CrewAI usage metrics are version-dependent; capture if available.
    try:
        from hermes.agents.researcher import build_researcher_agent
        agent = build_researcher_agent()
        usage = agent.llm.additional_params if hasattr(agent.llm, "additional_params") else {}
    except Exception:
        usage = {}

    baseline = {
        "run_id": run_id,
        "research_question": research_question,
        "artifact_id": artifact_id,
        "attempts": artifact["version"],
        "final_status": "pass" if result["passed"] else "escalated",
        "score": result["score"],
        "elapsed_seconds": elapsed,
        "total_tokens": usage.get("total_tokens", 0),
    }

    log_path = ws.log_dir / "phase1_baseline.json"
    existing = []
    if log_path.exists():
        existing = json.loads(log_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = [existing]
    existing.append(baseline)
    log_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return baseline
