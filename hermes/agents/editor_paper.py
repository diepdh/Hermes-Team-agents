"""Editor subagent for Phase 5.6 — targeted paper editing.

Replaces the Writer in the retry loop from attempt 2 onwards.
Unlike Writer (which regenerates the whole paper), Editor only
fixes the specific issues Reviewer identified, preserving correct
content untouched.
"""

from __future__ import annotations

import json
from typing import Any


def run_paper_editor(
    paper_draft: str,
    source_analysis: dict[str, Any],
    reviewer_feedback: str,
    literature_support: dict[str, Any] | None = None,
    provider: str = "opencode_go",
) -> str:
    """Edit paper_draft fixing ONLY the issues in reviewer_feedback.

    Args:
        paper_draft: Current paper content (the version Reviewer found issues in).
        source_analysis: Ground-truth data from the original document.
        reviewer_feedback: Specific issues the Reviewer wants fixed.
        literature_support: Verified literature entries for citation fixes.
        provider: LLM provider name.

    Returns:
        Edited paper_draft (full IMRaD markdown).
    """
    from hermes.core.llm_config import get_llm

    source_json = json.dumps(source_analysis, ensure_ascii=False, indent=2)[:3000]
    lit_json = json.dumps(
        (literature_support or {}).get("entries", [])[:5],
        ensure_ascii=False, indent=2,
    )[:1500]

    prompt = f"""You are an Academic Editor. Fix ONLY the specific issues listed
in the Reviewer's feedback. Everything else must stay EXACTLY as-is.

=== CURRENT PAPER ===
{paper_draft[:4000]}

=== SOURCE DATA (ground truth — do NOT contradict this) ===
{source_json[:2000]}

=== VERIFIED LITERATURE (use only these for citations) ===
{lit_json[:1000]}

=== REVIEWER FEEDBACK (fix ONLY these issues) ===
{reviewer_feedback[:2000]}

RULES:
1. ONLY fix the issues in the Reviewer feedback. Do NOT rewrite or
   "improve" sections that the Reviewer did not complain about.
2. Every number you write MUST match the SOURCE DATA exactly.
3. If you need to add a citation, ONLY use entries from VERIFIED LITERATURE.
4. Keep the IMRaD structure exactly as in the CURRENT PAPER.
5. Return the COMPLETE edited paper (all sections), not just the fixes.

Return the full edited paper in IMRaD markdown format."""

    try:
        llm = get_llm(provider)
        resp = llm.call(prompt, max_tokens=3000)
        if not resp or not resp.strip():
            # LLM failed — return original unchanged with a note
            return paper_draft
        return resp.strip()
    except Exception:
        # LLM unavailable — return original unchanged
        return paper_draft
