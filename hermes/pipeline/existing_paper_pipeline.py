"""Phase 5.7a pipeline: edit an existing paper (option 2 — text suggestions).

Route:
  existing .docx → Analyzer → existing_paper_assessment
      → Human Gate (choose option) → if option=2:
          → ingest as paper_draft v1
          → Reviewer → Editor → Debate → Publisher
          (reusing 100% of Phase 5 pipeline from paper_draft onward)
"""

from __future__ import annotations

import json
from typing import Any


def assess_existing_paper(
    paper_text: str,
    has_accompanying_data: bool = False,
) -> dict[str, Any]:
    """Analyze an existing paper and produce an assessment.

    This is rule-based (no LLM) — checks for data presence and suggests
    improvements based on IMRaD structure completeness.

    Args:
        paper_text: Raw text extracted from the existing .docx.
        has_accompanying_data: Whether raw data accompanies the paper.

    Returns:
        Assessment dict matching existing_paper_assessment schema.
    """
    text_lower = paper_text.lower()

    # Check which IMRaD sections are present
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

    # Count numbers (≈ data points)
    import re
    number_count = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", paper_text))

    # Generate option 2 suggestions
    suggestions = []
    if missing:
        suggestions.append(
            f"Complete missing IMRaD sections: {', '.join(missing)}"
        )
    if number_count < 10:
        suggestions.append(
            "Add more quantitative data to strengthen empirical claims"
        )
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
    """Extract OPTION=N from Human Gate approval notes.

    Returns None if no option found (binary approve for non-assessment types).
    """
    import re
    m = re.search(r"OPTION=(\d)", verification_notes)
    return int(m.group(1)) if m else None
