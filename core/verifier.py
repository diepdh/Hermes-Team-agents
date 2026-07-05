"""
Rule-based verifier for Hermes artifacts.

Phase 1 scope: rubric-based evaluation for literature-review Markdown artifacts.
No LLM judge yet — scores must be deterministic, reproducible, and cheap.
"""

import re
from typing import Dict, Any


def check_lit_review(content: str, rubric: dict) -> dict:
    """Score a literature review artifact against a rubric.

    Args:
        content: Markdown text of the artifact.
        rubric: Dictionary with 'criteria' list and 'pass_threshold' float.
                Each criterion has 'name' and 'weight'.

    Returns:
        dict with 'passed' (bool), 'score' (float), and 'detail' (dict).
    """
    scores: Dict[str, float] = {}
    text_lower = content.lower()
    criterion_names = {c["name"] for c in rubric.get("criteria", [])}

    if "citation_completeness" in criterion_names:
        # Count APA-style parenthetical years like (2024) or (Smith, 2024).
        citation_count = len(re.findall(r"\(\d{4}\)|\([A-Za-z\-]+[,\s]+\d{4}\)", content))
        scores["citation_completeness"] = min(citation_count / 3.0, 1.0)

    if "relevance" in criterion_names or "relevance_summary" in criterion_names:
        # The artifact must explicitly contain a Summary section.
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
