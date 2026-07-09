"""Ingest an existing paper (.docx text) as a paper_draft artifact.

Deterministic — no LLM. Just format the text into IMRaD structure.
Also provides _build_self_source() to create a placeholder source_analysis
from the paper's own numbers for internal consistency checking.
"""

from __future__ import annotations

import re
from typing import Any


def _build_self_source(paper_text: str) -> dict[str, Any]:
    """Build a minimal source_analysis from the paper's own content.

    Used when no external ground-truth data is available.  Extracts
    numbers from the paper so Reviewer can at least check internal
    consistency (does Abstract match Results? etc.).
    """
    numbers = list(set(re.findall(r"\b\d+(?:\.\d+)?%?\b", paper_text)))
    # Filter out citation years (4-digit 19xx/20xx)
    data_numbers = [
        n for n in numbers
        if not (len(n) == 4 and n.startswith(("19", "20")))
    ]
    return {
        "paragraphs_summary": f"Self-extracted from existing paper ({len(data_numbers)} numeric values found).",
        "tables": [],
        "images": [],
        "key_statistics": data_numbers[:20],  # cap at 20
        "_note": "NO EXTERNAL GROUND TRUTH — internal consistency check only.",
    }


def ingest_existing_paper_as_draft(
    paper_text: str,
    suggestions: list[str] | None = None,
    has_source_data: bool = False,
) -> str:
    """Convert an existing paper's text into a properly formatted paper_draft.

    Args:
        paper_text: Raw text extracted from the .docx file.
        suggestions: Optional list of experimental suggestions to append
                     as a non-scored "Suggested Future Work" section.
        has_source_data: Whether ground-truth data is available for verification.

    Returns:
        Formatted IMRaD markdown string (paper_draft v1).

    The function is DETERMINISTIC: it normalizes markdown headings and
    appends suggestions without invoking any LLM.
    """
    # Normalize: ensure each section starts with ## Heading
    sections = [
        ("abstract", "## Abstract"),
        ("introduction", "## Introduction"),
        ("method", "## Methods"),
        ("result", "## Results"),
        ("discussion", "## Discussion"),
        ("reference", "## References"),
    ]

    text_lower = paper_text.lower()
    formatted_lines = paper_text.split("\n")
    new_lines = []

    for line in formatted_lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue

        added_heading = False
        # First non-empty line that doesn't match a known section → title
        is_section_name = any(
            stripped.lower() == kw or stripped.lower().startswith(kw)
            for kw, _ in sections
        )
        if not new_lines or (not is_section_name and not any(l.startswith("#") for l in new_lines)):
            # Could be the title
            if not is_section_name and not added_heading:
                new_lines.append(f"# {stripped}")
                added_heading = True

        if not added_heading:
            for keyword, heading in sections:
                if stripped.lower() == keyword or stripped.lower().startswith(keyword):
                    new_lines.append(heading)
                    added_heading = True
                    break
        if not added_heading:
            new_lines.append(line)

    formatted = "\n".join(new_lines)

    # Ensure IMRaD sections are present
    text_lower = formatted.lower()
    for keyword, heading in sections:
        if keyword not in text_lower:
            formatted += f"\n\n{heading}\n[Content not extracted — please review.]\n"

    # Append metadata note about data availability
    meta_note = (
        "\n\n<!-- META: has_source_data={} -->\n".format(str(has_source_data).lower())
    )
    formatted += meta_note

    # Append suggestions as a separate, non-scored section
    if suggestions:
        formatted += "\n\n## Suggested Future Work\n"
        formatted += "*(These are reviewer suggestions — not verified claims.)*\n\n"
        for i, s in enumerate(suggestions, 1):
            formatted += f"{i}. {s}\n"

    return formatted
