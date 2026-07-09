"""Phase 5.7a pipeline: edit an existing paper (option 2 — text suggestions).

Full chain:
  existing .docx → assess → Human Gate (choose option=2)
      → ingest as paper_draft v1
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
