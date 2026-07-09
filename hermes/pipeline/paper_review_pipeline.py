"""Phase 5.3 pipeline: Writer ↔ Reviewer retry loop.

Uses the existing retry pattern from Phase 1 (recursive retry with
feedback propagation).
"""

from __future__ import annotations

import json
import time
from typing import Any

from hermes.agents.paper_reviewer import run_reviewer_judge, check_citations_exist_in_literature
from hermes.agents.paper_writer import run_paper_writer as _run_writer
from hermes.core.storage import read_artifact_content, get_artifact
from hermes.core.verifier import verify_artifact, finalize_verification
from hermes.rubrics import load_rubric


def _update_verification_with_reviewer(
    workspace,
    artifact: dict[str, Any],
    reviewer_result: dict[str, Any],
) -> str:
    """Re-finalize verification using the Reviewer's real scores.

    Replaces the hardcoded defaults (data_fidelity=0.7, reviewer_verdict=1.0)
    from the rule-based checker with the LLM-judge's actual evaluation.
    """
    content = read_artifact_content(workspace, artifact)
    rubric = load_rubric("paper_draft")

    # Re-verify with reviewer-provided scores injected into the detail
    base_result = verify_artifact("paper_draft", content, rubric)

    # Override hardcoded defaults with reviewer's real scores
    detail = dict(base_result.get("detail", {}))
    detail["data_fidelity"] = reviewer_result.get("data_fidelity", 0.5)
    detail["reviewer_verdict"] = (
        1.0 if reviewer_result.get("passed") else 0.0
    )
    if reviewer_result.get("llm_unavailable"):
        detail["llm_unavailable"] = True
        detail["reviewer_verdict"] = 0.0

    # Recompute score
    weighted_total = sum(
        detail.get(c["name"], 0.0) * c["weight"]
        for c in rubric.get("criteria", [])
    )
    threshold = rubric.get("pass_threshold", 0.85)
    passed = weighted_total >= threshold

    result = {
        "passed": passed,
        "score": round(weighted_total, 3),
        "detail": detail,
    }

    return finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        "paper_draft",
        result,
        notes=f"P5.3 Reviewer verdict: {json.dumps(reviewer_result, ensure_ascii=False)[:300]}",
        rubric_pass_threshold=threshold,
    )


def run_paper_pipeline_with_reviewer(
    workspace,
    source_analysis_artifact: dict[str, Any],
    literature_support_artifact: dict[str, Any] | None = None,
    artifact_id: str = "paper-pipeline",
    provider: str = "opencode_go",
    max_retries: int = 2,
    attempt: int = 1,
) -> dict[str, Any]:
    """Run Writer → Reviewer → retry if needed.

    Returns a dict with keys: artifact, reviewer_verdict, status,
    attempts, total_elapsed_seconds.
    """
    overall_start = time.time()

    # ── Step 1: Get paper content ──────────────────────────────────
    if attempt == 1:
        # First attempt: Writer generates the paper
        writer_artifact = _run_writer(
            workspace,
            source_analysis_artifact,
            artifact_id=artifact_id,
            provider=provider,
        )
        paper_content = read_artifact_content(workspace, writer_artifact)
        current_artifact = writer_artifact
    else:
        # Retry: read the latest paper_draft from Artifact Store (persisted).
        # Editor saved it via save_artifact() in the previous iteration.
        current_artifact = get_artifact(workspace, artifact_id, attempt)
        paper_content = read_artifact_content(workspace, current_artifact)

    # ── Step 2: Load inputs ────────────────────────────────────────
    source_data = json.loads(
        read_artifact_content(workspace, source_analysis_artifact),
    )
    lit_data = None
    if literature_support_artifact:
        lit_data = json.loads(
            read_artifact_content(workspace, literature_support_artifact),
        )

    # ── Step 3: Reviewer ──────────────────────────────────────────
    reviewer_result = run_reviewer_judge(
        paper_content, source_data, lit_data, provider=provider,
    )

    # ── Step 4: LLM unavailable → escalate immediately ────────────
    if reviewer_result.get("llm_unavailable"):
        _update_verification_with_reviewer(workspace, current_artifact, reviewer_result)
        updated_artifact = get_artifact(
            workspace, artifact_id, current_artifact["version"],
        )
        return {
            "artifact": updated_artifact,
            "reviewer_verdict": reviewer_result,
            "status": "escalated",
            "attempts": attempt,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Step 4b: Search error → escalate (retry won't fix infra) ────
    if (not reviewer_result.get("citation_valid")
            and lit_data
            and lit_data.get("search_error")):
        _update_verification_with_reviewer(workspace, current_artifact, reviewer_result)
        updated_artifact = get_artifact(
            workspace, artifact_id, current_artifact["version"],
        )
        return {
            "artifact": updated_artifact,
            "reviewer_verdict": reviewer_result,
            "status": "escalated",
            "attempts": attempt,
            "total_elapsed_seconds": round(time.time() - overall_start, 2),
        }

    # ── Step 5: Update verification with real scores ──────────────
    _update_verification_with_reviewer(workspace, current_artifact, reviewer_result)

    elapsed = round(time.time() - overall_start, 2)

    # Re-read to get updated status
    updated_artifact = get_artifact(
        workspace, artifact_id, current_artifact["version"],
    )

    if reviewer_result["passed"]:
        return {
            "artifact": updated_artifact,
            "reviewer_verdict": reviewer_result,
            "status": "pass" if updated_artifact["verification_status"] == "pass" else updated_artifact["verification_status"],
            "attempts": attempt,
            "total_elapsed_seconds": elapsed,
        }

    # ── Step 6: Retry with Editor ──────────────────────────────────
    feedback = reviewer_result.get("feedback", "")
    print(f"[REVIEWER FAIL] attempt {attempt}: {feedback[:200]}")

    if attempt <= max_retries:
        # ── Rule-based diff guard BEFORE Editor runs ────────────────
        from hermes.core.verifier import check_editor_diff

        # ── Call Editor ─────────────────────────────────────────────
        from hermes.agents.editor_paper import run_paper_editor
        edited_content = run_paper_editor(
            paper_draft=paper_content,
            source_analysis=source_data,
            reviewer_feedback=feedback,
            literature_support=lit_data,
            provider=provider,
        )

        # ── Rule-based diff check ───────────────────────────────────
        diff_ok, diff_violations = check_editor_diff(
            original=paper_content,
            edited=edited_content,
            source_analysis=source_data,
            literature_support=lit_data,
        )
        if not diff_ok:
            print(f"[EDITOR DIFF FAIL] {diff_violations}")
            # Editor violated rules — use original content and escalate
            from hermes.core.storage import save_artifact
            _ = save_artifact(
                workspace=workspace,
                artifact_id=f"{artifact_id}-edit-fail-{attempt}",
                content=edited_content,
                artifact_type="paper_draft",
                produced_by_task=f"editor-fail-{attempt}",
            )
            return {
                "artifact": updated_artifact,
                "reviewer_verdict": reviewer_result,
                "status": "escalated",
                "attempts": attempt,
                "total_elapsed_seconds": elapsed,
            }

        # ── Save edited paper as new version ─────────────────────────
        from hermes.core.storage import save_artifact
        edited_artifact = save_artifact(
            workspace=workspace,
            artifact_id=artifact_id,
            content=edited_content,
            artifact_type="paper_draft",
            produced_by_task=f"editor-{attempt}",
        )

        # ── Recursive call with edited paper ─────────────────────────
        # Pass the edited content through augmented source for the next iteration
        augmented_source = dict(source_data)
        augmented_source["reviewer_feedback"] = feedback
        augmented_content = json.dumps(augmented_source, ensure_ascii=False)

        tmp_source = save_artifact(
            workspace=workspace,
            artifact_id=f"{artifact_id}-feedback-{attempt}",
            content=augmented_content,
            artifact_type="source_analysis",
            produced_by_task=f"editor-feedback-{attempt}",
        )

        inner = run_paper_pipeline_with_reviewer(
            workspace=workspace,
            source_analysis_artifact=tmp_source,
            literature_support_artifact=literature_support_artifact,
            artifact_id=artifact_id,
            provider=provider,
            max_retries=max_retries,
            attempt=attempt + 1,
        )
        inner["total_elapsed_seconds"] = round(
            elapsed + inner.get("total_elapsed_seconds", 0), 2,
        )
        return inner

    return {
        "artifact": updated_artifact,
        "reviewer_verdict": reviewer_result,
        "status": "escalated",
        "attempts": attempt,
        "total_elapsed_seconds": elapsed,
    }
