"""
Rule-based verifier for Hermes artifacts.

Phase 1+2 scope: rubric-based evaluation for 4 artifact types:
  - lit_review_md   (Phase 1)
  - course_outline  (Phase 2)
  - lecture_draft   (Phase 2)
  - quiz_bank       (Phase 2)

All checkers are deterministic, reproducible, and cheap — no LLM judge.
"""

import json
import re
from typing import Dict, Any

from .storage import update_verification


# -------------------------------------------------------------------
# Human gate: types that must be manually approved after passing rubric
# -------------------------------------------------------------------
HUMAN_GATE_TYPES = {"lecture_draft", "quiz_bank"}


# -------------------------------------------------------------------
# Checker registry — mirrors the PROVIDER_REGISTRY pattern from llm_config
# -------------------------------------------------------------------
CHECKER_REGISTRY: Dict[str, Any] = {}


def checker_for(artifact_type: str):
    """Decorator to register a checker function for an artifact type."""
    def decorator(fn):
        CHECKER_REGISTRY[artifact_type] = fn
        return fn
    return decorator


def verify_artifact(artifact_type: str, content: str, rubric: dict) -> dict:
    """Dispatch to the correct checker based on artifact_type.

    Raises:
        ValueError: if artifact_type is not registered.
    """
    checker = CHECKER_REGISTRY.get(artifact_type)
    if checker is None:
        registered = ", ".join(sorted(CHECKER_REGISTRY.keys()))
        raise ValueError(
            f"No checker registered for artifact_type '{artifact_type}'. "
            f"Registered types: {registered}"
        )
    return checker(content, rubric)


# -------------------------------------------------------------------
# Centralized verification finalization — single source of truth for
# human-gate policy.  Use this instead of calling update_verification()
# directly so every code path (pipeline, test, CLI) applies the same rules.
# -------------------------------------------------------------------
def finalize_verification(
    workspace,
    artifact_id: str,
    version: int,
    artifact_type: str,
    rubric_result: dict,
    notes: str = "",
) -> str:
    """
    Determine and persist the final verification status for an artifact.

    Policy:
      - rubric fails  → status = "fail"
      - rubric passes, type in HUMAN_GATE_TYPES → status = "escalated"
      - rubric passes, otherwise                 → status = "pass"

    Args:
        workspace:  Workspace instance
        artifact_id: artifact identifier
        version:   artifact version number
        artifact_type: one of the registered artifact types
        rubric_result: dict with "passed" (bool) and "detail" (dict)
        notes:     optional human-readable note (e.g. retry count)

    Returns:
        The status string that was written to the artifact index.
    """
    if not rubric_result["passed"]:
        status = "fail"
    elif artifact_type in HUMAN_GATE_TYPES:
        status = "escalated"
    else:
        status = "pass"

    detail_json = json.dumps(rubric_result.get("detail", {}), ensure_ascii=False)
    update_verification(
        workspace,
        artifact_id,
        version,
        status,
        notes=f"{notes}  {detail_json}".strip(),
    )
    return status


# -------------------------------------------------------------------
# Shared scoring helper
# -------------------------------------------------------------------
def _score(artifact_type: str, content: str, rubric: dict) -> dict:
    """Common return shape for all checkers."""
    checker = CHECKER_REGISTRY.get(artifact_type)
    if checker is None:
        raise ValueError(f"No checker for '{artifact_type}'")
    result = checker(content, rubric)
    return result


# -------------------------------------------------------------------
# Checker: lit_review_md (Phase 1 — kept as-is, now decorated)
# -------------------------------------------------------------------
@checker_for("lit_review_md")
def check_lit_review(content: str, rubric: dict) -> dict:
    scores: Dict[str, float] = {}
    text_lower = content.lower()
    criterion_names = {c["name"] for c in rubric.get("criteria", [])}

    if "citation_completeness" in criterion_names:
        citation_count = len(re.findall(r"\(\d{4}\)|\([A-Za-z\-]+[,\s]+\d{4}\)", content))
        scores["citation_completeness"] = min(citation_count / 3.0, 1.0)

    if "relevance" in criterion_names or "relevance_summary" in criterion_names:
        score = 1.0 if re.search(r"(^|#+\s*)summary", text_lower) else 0.0
        if "relevance" in criterion_names:
            scores["relevance"] = score
        if "relevance_summary" in criterion_names:
            scores["relevance_summary"] = score

    if "gap_identification" in criterion_names or "gaps_section" in criterion_names:
        score = 1.0 if "gaps identified" in text_lower else 0.0
        if "gap_identification" in criterion_names:
            scores["gap_identification"] = score
        if "gaps_section" in criterion_names:
            scores["gaps_section"] = score

    if "clarity" in criterion_names or "formatting_clarity" in criterion_names:
        word_count = len(content.split())
        if word_count > 100:
            score = 1.0
        elif word_count > 50:
            score = 0.5
        else:
            score = 0.0
        if "clarity" in criterion_names:
            scores["clarity"] = score
        if "formatting_clarity" in criterion_names:
            scores["formatting_clarity"] = score

    return _build_result(scores, rubric)


# -------------------------------------------------------------------
# Checker: course_outline (Phase 2)
# -------------------------------------------------------------------
@checker_for("course_outline")
def check_course_outline(content: str, rubric: dict) -> dict:
    scores: Dict[str, float] = {}
    text_lower = content.lower()
    criterion_names = {c["name"] for c in rubric.get("criteria", [])}

    if "learning_objectives_present" in criterion_names:
        has_lo = bool(re.search(r"learning\s+objective", text_lower))
        scores["learning_objectives_present"] = 1.0 if has_lo else 0.0

    if "session_breakdown" in criterion_names:
        has_breakdown = bool(re.search(r"(week|session|tuần|buổi)\s+\d+", text_lower))
        scores["session_breakdown"] = 1.0 if has_breakdown else 0.0

    if "aligned_with_lit_review" in criterion_names:
        has_alignment = bool(re.search(r"\(\d{4}\)", content))
        scores["aligned_with_lit_review"] = 1.0 if has_alignment else 0.0

    if "assessment_hooks" in criterion_names:
        has_assessment = bool(re.search(r"assessment|quiz|exam|kiểm\s*tra", text_lower))
        scores["assessment_hooks"] = 1.0 if has_assessment else 0.0

    return _build_result(scores, rubric)


# -------------------------------------------------------------------
# Checker: lecture_draft (Phase 2)
# -------------------------------------------------------------------
@checker_for("lecture_draft")
def check_lecture_draft(content: str, rubric: dict) -> dict:
    scores: Dict[str, float] = {}
    text_lower = content.lower()
    criterion_names = {c["name"] for c in rubric.get("criteria", [])}

    if "covers_all_outline_sections" in criterion_names:
        word_count = len(content.split())
        scores["covers_all_outline_sections"] = 1.0 if word_count > 300 else 0.0

    if "examples_included" in criterion_names:
        has_example = bool(re.search(r"for example|ví dụ|example|instance", text_lower))
        scores["examples_included"] = 1.0 if has_example else 0.0

    if "length_adequate" in criterion_names:
        word_count = len(content.split())
        scores["length_adequate"] = 1.0 if word_count > 500 else 0.0

    if "no_unsupported_claims" in criterion_names:
        bare_numbers = len(re.findall(r"(?<!\()\b\d{4,}(?!\))", content))
        citation_markers = len(re.findall(r"\(\d{4}\)", content))
        scores["no_unsupported_claims"] = 0.0 if bare_numbers > 0 and citation_markers == 0 else 1.0

    return _build_result(scores, rubric)


# -------------------------------------------------------------------
# Checker: quiz_bank (Phase 2)
# -------------------------------------------------------------------
@checker_for("quiz_bank")
def check_quiz_bank(content: str, rubric: dict) -> dict:
    scores: Dict[str, float] = {}
    text_lower = content.lower()
    criterion_names = {c["name"] for c in rubric.get("criteria", [])}

    if "question_count" in criterion_names:
        # Match numbered questions at start of a line.
        # Patterns: "1. ", "2) ", "Q1. ", "A. ", "**Q1.** ", "** 1.** ", "- Q1) "
        question_lines = re.findall(
            r"^\s*(?:\d+[.)]\s|(?:Q?\d+|\*\*)[.)]\s|(?:^|[^-])[A-Z]\.\s)",
            content,
            re.MULTILINE,
        )
        q_count = len(question_lines)
        scores["question_count"] = 1.0 if q_count >= 5 else q_count / 5.0

    if "covers_lecture_topics" in criterion_names:
        has_topic_markers = bool(re.search(r"(lecture|chủ đề|topic|bài học)", text_lower))
        scores["covers_lecture_topics"] = 1.0 if has_topic_markers else 0.0

    if "has_answer_key" in criterion_names:
        has_answer = bool(re.search(r"(?:đáp án|answer|correct answer|=>\s*[A-Z])", text_lower))
        scores["has_answer_key"] = 1.0 if has_answer else 0.0

    if "difficulty_variety" in criterion_names:
        easy_markers = re.findall(r"\b(easy|dễ|beginner|basic)\b", text_lower)
        hard_markers = re.findall(r"\b(hard|khó|advanced|expert)\b", text_lower)
        has_variety = bool(easy_markers) and bool(hard_markers)
        mc_markers = len(re.findall(r"\n\s*[A-Z][.)]\s", content))
        tf_markers = len(re.findall(r"\b(true|false|đúng|sai)\b", text_lower))
        has_variety = has_variety or (mc_markers > 0 and tf_markers > 0)
        scores["difficulty_variety"] = 1.0 if has_variety else 0.0

    return _build_result(scores, rubric)


# -------------------------------------------------------------------
# Shared result builder
# -------------------------------------------------------------------
def _build_result(scores: Dict[str, float], rubric: dict) -> dict:
    """Compute weighted total and build the standard result dict."""
    weighted_total = sum(
        scores.get(c["name"], 0.0) * c["weight"]
        for c in rubric.get("criteria", [])
    )
    threshold = rubric.get("pass_threshold", 0.7)
    passed = weighted_total >= threshold

    return {
        "passed": passed,
        "score": round(weighted_total, 3),
        "detail": scores,
    }
