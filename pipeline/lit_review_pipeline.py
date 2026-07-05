"""
Phase 1 pipeline: Researcher -> Verifier -> Retry loop.

Produces a literature-review artifact for a research question, evaluates it
with a rule-based rubric, and retries with diagnostic feedback if it fails.
"""

import json
import os
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


# CrewAI usage_metrics shape changed across versions.  Some builds expose
# token usage as a list of UsageMetrics objects.  This helper normalizes it.
def _extract_usage(crew):
    """Return normalized token usage from a CrewAI Crew instance if available."""
    empty = {"prompt": 0, "completion": 0, "total": 0}
    metrics = getattr(crew, "usage_metrics", None)
    if not metrics:
        return empty

    # Newer CrewAI: usage_metrics is a list of UsageMetrics objects.
    if isinstance(metrics, list) and metrics:
        last = metrics[-1]
        return {
            "prompt": getattr(last, "prompt_tokens", 0) or 0,
            "completion": getattr(last, "completion_tokens", 0) or 0,
            "total": getattr(last, "total_tokens", 0) or 0,
        }

    # Dict form.
    if isinstance(metrics, dict):
        return {
            "prompt": metrics.get("prompt_tokens", 0) or 0,
            "completion": metrics.get("completion_tokens", 0) or 0,
            "total": metrics.get("total_tokens", 0) or 0,
        }

    return empty


def run_lit_review_pipeline(
    workspace_root: str,
    research_question: str,
    task_id: str,
    artifact_id: str,
    rubric: dict,
    provider: str | None = None,
    attempt: int = 1,
    max_retries: int = 2,
) -> Tuple[dict, dict, dict]:
    """Run one literature-review pipeline iteration including verification.

    Args:
        workspace_root: Path to the Hermes workspace.
        research_question: The research question to answer.
        task_id: Task identifier to link the artifact to.
        artifact_id: Artifact identifier (will be versioned automatically).
        rubric: Rubric dictionary with criteria and pass_threshold.
        provider: LLM provider key (None uses HERMES_LLM_PROVIDER default).
        attempt: Current attempt number (starts at 1).
        max_retries: Maximum number of retry attempts after the first failure.

    Returns:
        Tuple of (artifact_record, verification_result, usage_summary).
    """
    ws = Workspace(workspace_root)
    ws.ensure_initialized()

    agent = build_researcher_agent(provider)
    output_path = str(ws.artifact_dir / f"{artifact_id}_v{attempt}.md")
    task_def = build_lit_review_task(agent, research_question, output_path)

    crew = Crew(agents=[agent], tasks=[task_def], process=Process.sequential)
    start = time.time()
    crew.kickoff()
    crew.calculate_usage_metrics()
    elapsed = round(time.time() - start, 2)
    usage = _extract_usage(crew)

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
        return artifact, result, {"elapsed_seconds": elapsed, "usage": usage}

    print(f"[FAIL] {artifact_id} v{artifact['version']} -- score {result['score']} -- {result['detail']}")
    if attempt < max_retries:
        retry_question = (
            f"{research_question}\n\n"
            f"[Ghi chu tu lan truoc -- can khac phuc]: "
            f"{json.dumps(result['detail'], ensure_ascii=False)}"
        )
        inner_artifact, inner_result, inner_usage = run_lit_review_pipeline(
            workspace_root,
            retry_question,
            task_id,
            artifact_id,
            rubric,
            provider=provider,
            attempt=attempt + 1,
            max_retries=max_retries,
        )
        # Aggregate time/tokens across attempts.
        inner_usage["elapsed_seconds"] = round(elapsed + inner_usage.get("elapsed_seconds", 0), 2)
        inner_usage["usage"]["prompt"] += usage.get("prompt", 0)
        inner_usage["usage"]["completion"] += usage.get("completion", 0)
        inner_usage["usage"]["total"] += usage.get("total", 0)
        return inner_artifact, inner_result, inner_usage

    print(f"[ESCALATED] {artifact_id} sau {max_retries} lan van fail -- can nguoi xem lai")
    return artifact, result, {"elapsed_seconds": elapsed, "usage": usage}


def _load_baseline(log_path: Path):
    """Load existing baseline JSON or return the empty template."""
    if not log_path.exists():
        return {"opencode_go": {"runs": [], "avg_elapsed_seconds": 0.0, "pass_rate_first_attempt": 0.0}, "local_cx": None}
    data = json.loads(log_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        # Legacy list format: convert to new keyed format.
        converted = {"opencode_go": {"runs": [], "avg_elapsed_seconds": 0.0, "pass_rate_first_attempt": 0.0}, "local_cx": None}
        for entry in data:
            prov = entry.get("provider", "opencode_go")
            converted.setdefault(prov, {"runs": [], "avg_elapsed_seconds": 0.0, "pass_rate_first_attempt": 0.0})
            converted[prov]["runs"].append(entry)
        return converted
    return data


def _save_baseline(log_path: Path, data: dict):
    """Persist baseline and recompute aggregate stats."""
    for prov, section in data.items():
        if section is None or not section.get("runs"):
            continue
        runs = section["runs"]
        section["avg_elapsed_seconds"] = round(
            sum(r["elapsed_seconds"] for r in runs) / len(runs), 2
        )
        first_attempts = [r for r in runs if r["retries"] == 0]
        section["pass_rate_first_attempt"] = round(
            len(first_attempts) / len(runs), 2
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_lit_review_with_baseline(
    workspace_root: str,
    research_question: str,
    task_id: str,
    artifact_id: str,
    rubric: dict,
    run_id: str,
    provider: str | None = None,
    max_retries: int = 2,
) -> dict:
    """Run the pipeline and record token/time baseline metrics.

    Returns the run entry appended to logs/phase1_baseline.json.
    """
    provider = provider or os.environ.get("HERMES_LLM_PROVIDER", "opencode_go")
    artifact, result, metrics = run_lit_review_pipeline(
        workspace_root, research_question, task_id, artifact_id, rubric,
        provider=provider, attempt=1, max_retries=max_retries,
    )

    baseline = {
        "run_id": run_id,
        "question": research_question,
        "elapsed_seconds": metrics["elapsed_seconds"],
        "retries": artifact["version"] - 1,
        "status": "pass" if result["passed"] else "escalated",
        "tokens": metrics["usage"],
    }

    ws = Workspace(workspace_root)
    ws.ensure_initialized()
    log_path = ws.log_dir / "phase1_baseline.json"
    data = _load_baseline(log_path)
    data.setdefault(provider, {"runs": [], "avg_elapsed_seconds": 0.0, "pass_rate_first_attempt": 0.0})
    data[provider]["runs"].append(baseline)
    _save_baseline(log_path, data)

    return baseline
