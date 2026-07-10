"""Phase 5.7 pipeline: edit an existing paper.

Full chain:
  existing .docx → assess → Human Gate (choose option)
    OPTION=1: run_code_runner() → generated_data → verify → ingest as paper_draft
    OPTION=2: text suggestions → ingest as paper_draft
      → verify citations via Literature Researcher
      → Reviewer (with self-source if no external data)
      → Editor → Debate → Publisher
"""

from __future__ import annotations

import json
import re
from typing import Any


def assess_existing_paper(
    paper_text: str,
    has_accompanying_data: bool = False,
) -> dict[str, Any]:
    """Analyze an existing paper and produce an assessment (rule-based, no LLM)."""
    text_lower = paper_text.lower()

    imrad_sections = {
        "abstract": "abstract" in text_lower,
        "introduction": "introduction" in text_lower,
        "methods": "method" in text_lower,
        "results": "result" in text_lower,
        "discussion": "discussion" in text_lower,
        "references": "reference" in text_lower,
    }
    present = [k for k, v in imrad_sections.items() if v]
    missing = [k for k, v in imrad_sections.items() if not v]

    number_count = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", paper_text))

    suggestions = []
    if missing:
        suggestions.append(f"Complete missing IMRaD sections: {', '.join(missing)}")
    if number_count < 10:
        suggestions.append("Add more quantitative data to strengthen empirical claims")
    suggestions.append(
        "Review citations — ensure all referenced works are real and accessible"
    )

    notes_parts = [f"Paper has {len(present)}/6 IMRaD sections: {', '.join(present)}"]
    if missing:
        notes_parts.append(f"Missing: {', '.join(missing)}")
    if has_accompanying_data:
        notes_parts.append("Accompanying raw data available for verification")
    else:
        notes_parts.append("No accompanying raw data — limited to internal consistency checks")

    return {
        "artifact_type": "existing_paper_assessment",
        "has_accompanying_data": has_accompanying_data,
        "data_completeness_notes": ". ".join(notes_parts),
        "imrad_sections_present": present,
        "imrad_sections_missing": missing,
        "number_of_data_points": number_count,
        "option_1_feasible": has_accompanying_data,
        "option_1_description": (
            "Run code to regenerate/verify data from accompanying raw sources"
            if has_accompanying_data else
            "Not feasible — no raw data available"
        ),
        "option_2_suggestions": suggestions,
    }


def parse_chosen_option_from_notes(verification_notes: str) -> int | None:
    """Extract OPTION=N from Human Gate approval notes."""
    m = re.search(r"OPTION=(\d)", verification_notes)
    return int(m.group(1)) if m else None


def _extract_citations_from_text(text: str) -> list[dict[str, str]]:
    """Extract citation (author, year) pairs from paper text."""
    pattern = re.compile(
        r"([A-Z][a-z]+(?:\s*,\s*[A-Z]\.)?)\s*\(\s*(\d{4})\s*\)",
        re.IGNORECASE,
    )
    citations = []
    seen = set()
    for m in pattern.finditer(text):
        author = m.group(1).strip()
        year = m.group(2)
        key = (author.lower(), year)
        if key not in seen:
            seen.add(key)
            citations.append({"author": author, "year": year})
    return citations


def verify_existing_citations(
    paper_text: str,
    workspace=None,
) -> dict[str, Any]:
    """Run Literature Researcher to verify citations found in an existing paper.

    Returns a literature_support-compatible dict with verified entries.
    If Literature Researcher is unavailable, returns empty entries.
    """
    citations = _extract_citations_from_text(paper_text)
    if not citations:
        return {"entries": [], "search_attempted": False}

    # Build search queries from citation authors
    queries = [f"{c['author']} {c['year']}" for c in citations[:5]]

    try:
        from hermes.agents.literature_researcher import search_semantic_scholar
        entries = search_semantic_scholar(queries, max_results_per_query=2)
        return {
            "entries": entries,
            "search_attempted": True,
            "queries_used": queries,
        }
    except Exception:
        return {
            "entries": [],
            "search_attempted": True,
            "search_error": "Literature Researcher unavailable",
            "queries_used": queries,
        }


def get_or_build_source(
    paper_text: str,
    has_accompanying_data: bool = False,
    source_analysis_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get the appropriate source_analysis for Reviewer.

    If external data is available, use it. Otherwise, build a self-source
    from the paper's own numbers for internal consistency checking.
    """
    if has_accompanying_data and source_analysis_artifact:
        return source_analysis_artifact

    # No external data — build self-source
    from hermes.agents.ingest_paper import _build_self_source
    return _build_self_source(paper_text)


def run_existing_paper_to_publisher(
    workspace,
    paper_draft_content: str,
    source_data: dict[str, Any],
    literature_data: dict[str, Any] | None = None,
    artifact_id: str = "existing-paper-draft",
    provider: str = "local_cx",
) -> dict[str, Any]:
    """Run Reviewer → Verification → Debate → Publisher for an existing paper.

    This is the SAME flow as the original paper pipeline from paper_draft
    onward.  Uses finalize_verification() which auto-triggers debate review
    when risk=high.  Reuses 100% of Phase 5 infrastructure.
    """
    from hermes.agents.paper_reviewer import run_reviewer_judge
    from hermes.core.storage import save_artifact, read_artifact_content, get_artifact
    from hermes.core.verifier import finalize_verification, verify_artifact
    from hermes.rubrics import load_rubric
    from hermes.pipeline.debate_review_task import run_debate_review
    from hermes.core.risk import should_trigger_debate
    from hermes.agents.publisher import publish_paper_draft
    from pathlib import Path

    # Save paper_draft
    paper_artifact = save_artifact(
        workspace, artifact_id, paper_draft_content,
        "paper_draft", f"T-{artifact_id}",
    )

    # Reviewer
    verdict = run_reviewer_judge(
        paper_draft_content, source_data, literature_data, provider=provider,
    )

    # Verification (risk-adjusted, may trigger debate)
    rubric = load_rubric("paper_draft")
    base_result = verify_artifact("paper_draft", paper_draft_content, rubric)
    detail = dict(base_result.get("detail", {}))
    detail["data_fidelity"] = verdict.get("data_fidelity", 0.5)
    detail["reviewer_verdict"] = 1.0 if verdict.get("passed") else 0.0

    score = sum(
        detail.get(c["name"], 0.0) * c["weight"]
        for c in rubric.get("criteria", [])
    )
    rubric_pass = score >= rubric.get("pass_threshold", 0.85)

    # Debate review (auto-triggered by finalize_verification when risk=high)
    debate_verdict = None
    if should_trigger_debate("paper_draft") and rubric_pass and not verdict.get("llm_unavailable"):
        debate_verdict = run_debate_review(
            artifact_content=paper_draft_content,
            artifact_id=artifact_id,
            artifact_version=paper_artifact["version"],
            artifact_type="paper_draft",
            max_rounds=3,
            workdir=workspace.root,
        )

    status = finalize_verification(
        workspace, artifact_id, paper_artifact["version"],
        "paper_draft",
        {"passed": rubric_pass, "score": round(score, 3), "detail": detail},
        notes=f"P5.7a pipeline, debate={'yes' if debate_verdict else 'no'}",
        rubric_pass_threshold=rubric.get("pass_threshold", 0.85),
        debate_verdict=debate_verdict,
    )

    # If escalated after debate, Human Gate must approve before Publisher
    if status == "escalated":
        return {
            "artifact": paper_artifact,
            "reviewer_verdict": verdict,
            "debate_verdict": debate_verdict,
            "status": "escalated",
            "message": "Awaiting Human Gate approval before Publisher",
        }

    # Publisher
    output = Path(workspace.root) / f"{artifact_id}-final.docx"
    result_path = publish_paper_draft(paper_draft_content, output)

    return {
        "artifact": paper_artifact,
        "reviewer_verdict": verdict,
        "debate_verdict": debate_verdict,
        "status": status,
        "docx_path": str(result_path),
    }


# ============================================================================
# Phase 5.7b — OPTION=1: run code, generate data, verify
# ============================================================================

def run_option1_code_runner(
    workspace,
    source_analysis_artifact: dict[str, Any],
    existing_paper_assessment_artifact: dict[str, Any],
    artifact_id: str | None = None,
    provider: str = "local_cx",
    max_retries: int = 3,
) -> dict[str, Any]:
    """Run code_runner with retry + verification + debate for OPTION=1.

    This is the full lifecycle for generated_data:
      run_code_runner() → verify_artifact() → finalize_verification()
      → should_trigger_debate() → (if trigger) run_debate_review()

    Args:
        workspace: Workspace instance.
        source_analysis_artifact: Verified source_analysis record.
        existing_paper_assessment_artifact: Assessment from assess_existing_paper().
        artifact_id: Optional artifact ID for generated_data.
        provider: LLM provider.
        max_retries: Max LLM calls if static scan or runtime fails.

    Returns:
        Dict with generated_data artifact, verification status, and debate info.

    The caller MUST handle:
      - "fail" after retries → pipeline stops, inform user
      - "escalated" → pipeline stops, wait for Human Gate (D.4)
    """
    from hermes.agents.code_runner import run_code_runner as _run_code_runner
    from hermes.core.storage import get_artifact, read_artifact_content
    from hermes.core.verifier import verify_artifact, finalize_verification
    from hermes.rubrics import load_rubric
    from hermes.core.risk import should_trigger_debate
    from hermes.pipeline.debate_review_task import run_debate_review
    from hermes.core.events import log_event

    if artifact_id is None:
        import uuid
        artifact_id = f"gen-data-{uuid.uuid4().hex[:8]}"

    last_error = None

    for attempt in range(1, max_retries + 1):
        log_event(workspace, "code_runner_started", {
            "artifact_id": artifact_id,
            "attempt": attempt,
            "max_retries": max_retries,
        })

        try:
            gen_artifact = _run_code_runner(
                workspace=workspace,
                source_analysis_artifact=source_analysis_artifact,
                existing_paper_assessment_artifact=existing_paper_assessment_artifact,
                artifact_id=artifact_id,
                provider=provider,
            )
            # Use the actual artifact_id returned (run_code_runner may modify it)
            actual_art_id = gen_artifact["artifact_id"]
            actual_version = gen_artifact["version"]
        except RuntimeError as exc:
            # LLM call failed or infrastructure error
            last_error = str(exc)
            log_event(workspace, "code_runner_error", {
                "artifact_id": artifact_id,
                "attempt": attempt,
                "error": last_error,
            })
            continue

        # Read the artifact content
        gen_content_str = read_artifact_content(workspace, gen_artifact)
        try:
            gen_content = json.loads(gen_content_str)
        except json.JSONDecodeError:
            gen_content = {}

        # Static scan check
        static_ok = gen_content.get("static_scan_result", {}).get("passed", False)
        if not static_ok:
            last_error = f"static_scan_failed: {gen_content.get('static_scan_result', {}).get('violations', [])}"
            # This artifact was already saved with violations — skip to next retry
            continue

        # Verify the artifact
        rubric = load_rubric("generated_data")
        base_result = verify_artifact("generated_data", gen_content_str, rubric)
        rubric_pass = base_result["score"] >= rubric.get("pass_threshold", 0.90)

        # Check timeout → escalated (principle 10)
        timeout = gen_artifact.get("metadata", {}).get("timeout", False)

        # Debate review (auto-triggered when risk=critical and rubric pass)
        debate_verdict = None
        if should_trigger_debate("generated_data") and rubric_pass and not timeout:
            debate_verdict = run_debate_review(
                artifact_content=gen_content_str,
                artifact_id=actual_art_id,
                artifact_version=actual_version,
                artifact_type="generated_data",
                max_rounds=3,
                workdir=workspace.root,
                workspace=workspace,
            )

        status = finalize_verification(
            workspace, actual_art_id, actual_version,
            "generated_data",
            {"passed": rubric_pass, "score": round(base_result["score"], 3),
             "detail": base_result.get("detail", {})},
            notes=(
                f"P5.7b code_runner attempt {attempt}/{max_retries}, "
                f"debate={'yes' if debate_verdict else 'no'}"
            ),
            rubric_pass_threshold=rubric.get("pass_threshold", 0.90),
            debate_verdict=debate_verdict,
        )

        gen_artifact = get_artifact(workspace, actual_art_id, actual_version)
        return {
            "artifact": gen_artifact,
            "debate_verdict": debate_verdict,
            "verification_status": status,
            "attempts": attempt,
        }

    # Exhausted retries
    log_event(workspace, "code_runner_error", {
        "artifact_id": artifact_id,
        "error": f"All {max_retries} retries exhausted: {last_error}",
    })
    return {
        "artifact": None,
        "debate_verdict": None,
        "verification_status": "fail",
        "attempts": max_retries,
        "error": f"All {max_retries} retries exhausted: {last_error}",
    }
