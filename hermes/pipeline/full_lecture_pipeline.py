"""
Phase 2 pipeline: Full lecture generation — Researcher -> Curriculum Designer ->
Content Writer -> Assessment Builder -> Editor, with 2-tier verification
and human gate for lecture_draft and quiz_bank.

Produces 4 artifacts in sequence:
  1. lit_review_md       (Phase 1, reused)
  2. course_outline     (new, verified)
  3. lecture_draft      (new, verified + escalated to human)
  4. quiz_bank          (new, verified + escalated to human)
  5. final_lecture      (editor output, verified pass → human gate)

Each stage after lit_review uses the shared run_stage() helper and only
receives verified artifacts from the previous stage as input.
"""

import json
import time
from pathlib import Path
from typing import Callable

from crewai import Crew, Process

from hermes.agents.researcher import build_researcher_agent, build_lit_review_task
from hermes.agents.curriculum_designer import (
    build_curriculum_designer_agent,
    build_course_outline_task,
)
from hermes.agents.content_writer import (
    build_content_writer_agent,
    build_lecture_draft_task,
)
from hermes.agents.assessment_builder import (
    build_assessment_builder_agent,
    build_quiz_bank_task,
)
from hermes.agents.editor import build_editor_agent, build_edit_task
from hermes.core.workspace import Workspace
from hermes.core.storage import save_artifact, read_artifact_content
from hermes.core.verifier import verify_artifact, finalize_verification
from hermes.core.risk import should_trigger_debate, get_risk_level
from hermes.pipeline.debate_review_task import run_debate_review


def _maybe_run_debate(
    workspace: Workspace,
    artifact: dict,
    artifact_type: str,
    content: str,
    result: dict,
    rubric: dict,
    provider: str | None,
    notes: str,
) -> str:
    """Run debate review if risk triggers it, then re-finalize.

    Returns the new verification status.  If debate is not triggered,
    returns ``None``.
    """
    if not (should_trigger_debate(artifact_type) and result["passed"]):
        return None

    print(f"[DEBATE] Triggering debate for {artifact_type} v{artifact['version']} (risk={get_risk_level(artifact_type)})")
    debate_verdict = run_debate_review(
        artifact_content=content,
        artifact_id=artifact["artifact_id"],
        artifact_version=artifact["version"],
        artifact_type=artifact_type,
        provider=provider,
        max_rounds=3,
        workdir=str(workspace.artifact_dir),
    )
    # Persist debate_verdict to Artifact Store so human reviewers can
    # see the full proponent/opponent arguments when approving escalated
    # artifacts.  Versioned, never overwritten.
    import json
    verdict_artifact = save_artifact(
        workspace=workspace,
        artifact_id=f"{artifact['artifact_id']}-debate",
        content=json.dumps(debate_verdict, ensure_ascii=False, indent=2),
        artifact_type="debate_verdict",
        produced_by_task=f"debate-{artifact['artifact_id']}",
        metadata={
            "target_artifact_id": artifact["artifact_id"],
            "target_artifact_version": artifact["version"],
            "target_artifact_type": artifact_type,
        },
    )
    print(f"[DEBATE] Verdict saved as {verdict_artifact['artifact_id']}_v{verdict_artifact['version']}")
    new_status = finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        artifact_type,
        result,
        notes=f"{notes} + debate",
        rubric_pass_threshold=rubric.get("pass_threshold"),
        debate_verdict=debate_verdict,
    )
    print(f"[DEBATE] Result: {debate_verdict['final_decision']} → status={new_status}")
    return new_status


def run_stage(
    workspace: Workspace,
    agent_builder: Callable,
    task_builder: Callable,
    artifact_type: str,
    rubric: dict,
    produced_by_task: str,
    provider: str | None = None,
    max_retries: int = 2,
) -> dict:
    """Run one agent→task→verify→(escalate)→retry stage.

    Returns:
        dict with keys: artifact (record), verification (result),
        stage (artifact_type), escalated (bool), elapsed_seconds
    """
    agent = agent_builder(provider)
    output_path = str(workspace.artifact_dir / f"{produced_by_task}.md")
    task = task_builder(agent, output_path=output_path)

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    start = time.time()
    crew.kickoff()
    crew.calculate_usage_metrics()
    elapsed = round(time.time() - start, 2)

    content = Path(output_path).read_text(encoding="utf-8")

    artifact = save_artifact(
        workspace=workspace,
        artifact_id=produced_by_task,
        content=content,
        artifact_type=artifact_type,
        produced_by_task=produced_by_task,
    )

    result = verify_artifact(artifact_type, content, rubric)
    status = finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        artifact_type,
        result,
        notes=f"attempt 1",
        rubric_pass_threshold=rubric.get("pass_threshold"),
    )

    # ── Phase 3: Debate review for high/critical-risk artifacts ───────
    debate_status = _maybe_run_debate(
        workspace, artifact, artifact_type, content, result, rubric,
        provider, notes="attempt 1",
    )
    if debate_status is not None:
        status = debate_status

    if status == "escalated":
        print(f"[ESCALATED] {artifact_type} v{artifact['version']} -- score {result['score']} -- chờ người duyệt")
        return {
            "artifact": artifact,
            "verification": result,
            "stage": artifact_type,
            "escalated": True,
            "elapsed_seconds": elapsed,
        }

    if result["passed"]:
        print(f"[PASS] {artifact_type} v{artifact['version']} -- score {result['score']}")
        return {
            "artifact": artifact,
            "verification": result,
            "stage": artifact_type,
            "escalated": False,
            "elapsed_seconds": elapsed,
        }

    # Failed rubric — retry
    print(f"[FAIL] {artifact_type} v{artifact['version']} -- score {result['score']} -- {result['detail']}")
    for attempt in range(2, max_retries + 2):  # attempt 2..max_retries+1
        retry_note = (
            f"[Ghi chú từ lần trước — cần khắc phục]: "
            f"{json.dumps(result['detail'], ensure_ascii=False)}\n\n"
            f"Thử lại task cũ."
        )
        task.description = retry_note + "\n\n" + task.description

        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
        start2 = time.time()
        crew.kickoff()
        crew.calculate_usage_metrics()
        elapsed2 = round(time.time() - start2, 2)
        elapsed += elapsed2

        content = Path(output_path).read_text(encoding="utf-8")
        artifact = save_artifact(
            workspace=workspace,
            artifact_id=produced_by_task,
            content=content,
            artifact_type=artifact_type,
            produced_by_task=produced_by_task,
        )
        result = verify_artifact(artifact_type, content, rubric)
        status = finalize_verification(
            workspace,
            artifact["artifact_id"],
            artifact["version"],
            artifact_type,
            result,
            notes=f"attempt {attempt}",
            rubric_pass_threshold=rubric.get("pass_threshold"),
        )

        # ── Debate for retry path too ──────────────────────────────
        debate_status = _maybe_run_debate(
            workspace, artifact, artifact_type, content, result, rubric,
            provider, notes=f"attempt {attempt}",
        )
        if debate_status is not None:
            status = debate_status

        if status != "fail":
            print(f"[{status.upper()}] {artifact_type} v{artifact['version']} (attempt {attempt}) -- score {result['score']}")
            return {
                "artifact": artifact,
                "verification": result,
                "stage": artifact_type,
                "escalated": status == "escalated",
                "elapsed_seconds": elapsed,
            }

        print(f"[FAIL] {artifact_type} v{artifact['version']} (attempt {attempt}) -- {result['detail']}")

    # All retries exhausted → escalate
    print(f"[ESCALATED] {artifact_type} after {max_retries} retries")
    return {
        "artifact": artifact,
        "verification": result,
        "stage": artifact_type,
        "escalated": True,
        "elapsed_seconds": elapsed,
    }


def run_full_lecture_pipeline(
    workspace_root: str,
    research_question: str,
    learning_objectives: str,
    task_id_prefix: str = "lecture",
    rubric_lit: dict | None = None,
    rubric_outline: dict | None = None,
    rubric_lecture: dict | None = None,
    rubric_quiz: dict | None = None,
    provider: str | None = None,
) -> dict:
    """Run the complete lecture pipeline.

    Args:
        workspace_root: Path to the Hermes workspace.
        research_question: The research question for the literature review.
        learning_objectives: Learning objectives string for the curriculum designer.
        task_id_prefix: Prefix for artifact IDs (default "lecture").
        rubric_*: Rubric dicts; if None, loaded from hermes.rubrics/ directory.
        provider: LLM provider key.

    Returns:
        dict with status, artifacts, and per-stage metrics.
    """
    ws = Workspace(workspace_root)
    ws.ensure_initialized()

    # Load rubrics if not provided — try workspace first, fall back to package
    from hermes.rubrics import load_rubric
    if rubric_lit is None:
        try:
            rubric_lit = json.loads((ws.rubric_dir / "R-lit-review-v1.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            rubric_lit = load_rubric("lit_review")
    if rubric_outline is None:
        try:
            rubric_outline = json.loads((ws.rubric_dir / "R-course-outline-v1.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            rubric_outline = load_rubric("course_outline")
    if rubric_lecture is None:
        try:
            rubric_lecture = json.loads((ws.rubric_dir / "R-lecture-draft-v1.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            rubric_lecture = load_rubric("lecture_draft")
    if rubric_quiz is None:
        try:
            rubric_quiz = json.loads((ws.rubric_dir / "R-quiz-bank-v1.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            rubric_quiz = load_rubric("quiz_bank")

    stages: list[dict] = []
    overall_start = time.time()

    # ── Stage 1: Literature Review (Phase 1, reused) ──────────────────
    from hermes.pipeline.lit_review_pipeline import run_lit_review_pipeline

    lit_artifact, lit_result, lit_metrics = run_lit_review_pipeline(
        workspace_root=workspace_root,
        research_question=research_question,
        task_id=f"{task_id_prefix}-lit",
        artifact_id=f"{task_id_prefix}-lit",
        rubric=rubric_lit,
        provider=provider,
        attempt=1,
        max_retries=2,
    )
    stages.append({
        "stage": "lit_review_md",
        "artifact_id": lit_artifact["artifact_id"],
        "version": lit_artifact["version"],
        "passed": lit_result["passed"],
        "score": lit_result["score"],
        "elapsed_seconds": lit_metrics["elapsed_seconds"],
    })
    if not lit_result["passed"]:
        return {
            "status": "escalated",
            "failed_stage": "lit_review_md",
            "stages": stages,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Stage 2: Curriculum Designer ──────────────────────────────────
    lit_content = read_artifact_content(ws, lit_artifact)
    outline_result = run_stage(
        workspace=ws,
        agent_builder=build_curriculum_designer_agent,
        task_builder=lambda a, output_path: build_course_outline_task(
            a, lit_review_content=lit_content, learning_objectives=learning_objectives, output_path=output_path
        ),
        artifact_type="course_outline",
        rubric=rubric_outline,
        produced_by_task=f"{task_id_prefix}-outline",
        provider=provider,
        max_retries=2,
    )
    stages.append({
        "stage": "course_outline",
        "artifact_id": outline_result["artifact"]["artifact_id"],
        "version": outline_result["artifact"]["version"],
        "passed": outline_result["verification"]["passed"],
        "score": outline_result["verification"]["score"],
        "elapsed_seconds": outline_result["elapsed_seconds"],
    })
    if outline_result["escalated"]:
        return {
            "status": "escalated",
            "failed_stage": "course_outline",
            "stages": stages,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Stage 3: Content Writer ───────────────────────────────────────
    outline_content = read_artifact_content(ws, outline_result["artifact"])
    lecture_result = run_stage(
        workspace=ws,
        agent_builder=build_content_writer_agent,
        task_builder=lambda a, output_path: build_lecture_draft_task(
            a, course_outline_content=outline_content, output_path=output_path
        ),
        artifact_type="lecture_draft",
        rubric=rubric_lecture,
        produced_by_task=f"{task_id_prefix}-lecture",
        provider=provider,
        max_retries=2,
    )
    stages.append({
        "stage": "lecture_draft",
        "artifact_id": lecture_result["artifact"]["artifact_id"],
        "version": lecture_result["artifact"]["version"],
        "passed": lecture_result["verification"]["passed"],
        "score": lecture_result["verification"]["score"],
        "elapsed_seconds": lecture_result["elapsed_seconds"],
        "escalated": lecture_result["escalated"],
    })
    if lecture_result["escalated"]:
        return {
            "status": "escalated",
            "failed_stage": "lecture_draft",
            "stages": stages,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Stage 4: Assessment Builder ───────────────────────────────────
    lecture_content = read_artifact_content(ws, lecture_result["artifact"])
    quiz_result = run_stage(
        workspace=ws,
        agent_builder=build_assessment_builder_agent,
        task_builder=lambda a, output_path: build_quiz_bank_task(
            a, lecture_draft_content=lecture_content, output_path=output_path
        ),
        artifact_type="quiz_bank",
        rubric=rubric_quiz,
        produced_by_task=f"{task_id_prefix}-quiz",
        provider=provider,
        max_retries=2,
    )
    stages.append({
        "stage": "quiz_bank",
        "artifact_id": quiz_result["artifact"]["artifact_id"],
        "version": quiz_result["artifact"]["version"],
        "passed": quiz_result["verification"]["passed"],
        "score": quiz_result["verification"]["score"],
        "elapsed_seconds": quiz_result["elapsed_seconds"],
        "escalated": quiz_result["escalated"],
    })
    if quiz_result["escalated"]:
        return {
            "status": "escalated",
            "failed_stage": "quiz_bank",
            "stages": stages,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Stage 5: Editor ───────────────────────────────────────────────
    editor_result = run_stage(
        workspace=ws,
        agent_builder=build_editor_agent,
        task_builder=lambda a, output_path: build_edit_task(
            a, artifact_content=lecture_content, output_path=output_path
        ),
        artifact_type="final_lecture",
        rubric=rubric_lecture,  # reuse lecture rubric as quality gate
        produced_by_task=f"{task_id_prefix}-final",
        provider=provider,
        max_retries=1,
    )
    stages.append({
        "stage": "final_lecture",
        "artifact_id": editor_result["artifact"]["artifact_id"],
        "version": editor_result["artifact"]["version"],
        "passed": editor_result["verification"]["passed"],
        "score": editor_result["verification"]["score"],
        "elapsed_seconds": editor_result["elapsed_seconds"],
    })

    return {
        "status": "complete",
        "stages": stages,
        "total_elapsed_seconds": round(time.time() - overall_start, 2),
    }
