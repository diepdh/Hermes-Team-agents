"""Paper Reviewer subagent for Phase 5.3.

LLM-judge that evaluates a paper_draft against source_analysis and
literature_support.  Replaces the hardcoded checker defaults with real
judgment.
"""

from __future__ import annotations

import json
import re
from typing import Any

from hermes.core.llm_config import get_llm


# ── Layer 1: rule-based citation existence check ──────────────────────
def check_citations_exist_in_literature(
    paper_draft: str,
    literature_support: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    """Return (all_citations_valid, list_of_violations).

    Every citation in References must match an entry in literature_support
    (by title, author, or year).  If literature_support is None or has
    zero entries, this check is skipped (trivially passes).
    """
    entries = (literature_support or {}).get("entries", []) or []
    if not entries:
        return True, []  # no refs to check against → skip

    # Build a searchable index from literature entries
    index: list[dict[str, Any]] = []
    for e in entries:
        index.append({
            "title_lower": (e.get("title", "") or "").strip().lower(),
            "authors_lower": (e.get("authors", "") or "").strip().lower(),
            "year": str(e.get("year", "") or ""),
        })

    # Extract References section from paper
    ref_match = re.search(
        r"(?:^|\n)#+\s*(?:references?|tài liệu tham khảo)\s*\n(.+)",
        paper_draft, re.DOTALL | re.IGNORECASE,
    )
    ref_text = ref_match.group(1) if ref_match else ""

    violations: list[str] = []

    # Find citation patterns: "Author, X. (Year)" or "Author (Year)"
    citation_patterns = re.findall(
        r"([A-Z][a-z]+(?:,\s*[A-Z]\.)*)\s*\(\s*(\d{4})\s*\)",
        ref_text,
    )

    for author_snippet, year in citation_patterns:
        author_lower = author_snippet.strip().lower()
        found = False
        for entry in index:
            if year == entry["year"] and (
                author_lower in entry["authors_lower"]
                or author_lower in entry["title_lower"]
            ):
                found = True
                break
        if not found:
            violations.append(
                f"Citation '{author_snippet} ({year})' not found in literature_support"
            )

    return len(violations) == 0, violations


# ── Layer 2: LLM-judge data fidelity + citation relevance ─────────────
def run_reviewer_judge(
    paper_draft: str,
    source_analysis: dict[str, Any],
    literature_support: dict[str, Any] | None = None,
    provider: str = "opencode_go",
) -> dict[str, Any]:
    """LLM-judge: evaluate paper_draft and return verdict + feedback.

    Returns:
        {
            "passed": bool,
            "score": float (0-1),
            "data_fidelity": float (0-1),
            "citation_valid": bool,
            "citation_relevant": float (0-1),
            "feedback": str (actionable notes for Writer retry),
        }
    """
    # ── Layer 1: rule-based citation check ─────────────────────────
    citation_valid, citation_violations = check_citations_exist_in_literature(
        paper_draft, literature_support,
    )

    # ── Layer 2: LLM evaluation ────────────────────────────────────
    llm_unavailable = False

    try:
        llm = get_llm(provider)

        source_json = json.dumps(source_analysis, ensure_ascii=False, indent=2)[:3000]
        lit_json = json.dumps(
            (literature_support or {}).get("entries", [])[:5], ensure_ascii=False, indent=2,
        )[:2000]

        prompt = f"""Academic reviewer: evaluate this paper draft.

PAPER (excerpt):
{paper_draft[:2000]}

SOURCE DATA (ground truth):
{source_json[:1500]}

LITERATURE REFERENCES:
{lit_json[:1000]}

Return ONLY a JSON object:
{{"data_fidelity": 0.0-1.0, "citation_relevant": 0.0-1.0,
  "feedback": "specific fixes or No issues found",
  "passed": true/false}}

Rules:
- data_fidelity: do all numbers match source? Penalize fabricated numbers.
- citation_relevant: are citations used in proper context?
- passed: true if data_fidelity >= 0.8 AND citation_relevant >= 0.7
- If no literature references exist, set citation_relevant=1.0"""

        resp = llm.call(prompt, max_tokens=800)
        resp_clean = resp.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not resp_clean:
            raise RuntimeError("LLM returned empty response")
        judge = json.loads(resp_clean)
    except Exception:
        # If LLM fails, escalate — do NOT auto-pass.
        # A review that never happened cannot certify quality.
        llm_unavailable = True
        judge = {
            "data_fidelity": 0.0,
            "citation_relevant": 0.0,
            "feedback": "[Reviewer LLM call failed — manual review needed]",
            "passed": False,
        }

    # Override passed based on rule-based citation check
    if not citation_valid:
        judge["passed"] = False
        violation_note = "; ".join(citation_violations)
        judge["feedback"] = (
            f"CITATION VIOLATIONS: {violation_note}. "
            + judge.get("feedback", "")
        )

    return {
        "passed": judge.get("passed", False),
        "score": (judge.get("data_fidelity", 0.5) * 0.6 + judge.get("citation_relevant", 0.5) * 0.4),
        "data_fidelity": judge.get("data_fidelity", 0.5),
        "citation_valid": citation_valid,
        "citation_relevant": judge.get("citation_relevant", 0.5),
        "feedback": judge.get("feedback", ""),
        "llm_unavailable": llm_unavailable,
    }


def reviewer_verdict_to_json(verdict: dict[str, Any]) -> str:
    return json.dumps(verdict, ensure_ascii=False, indent=2)
