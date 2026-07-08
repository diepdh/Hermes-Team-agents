"""Literature Researcher subagent for Phase 5.2.5.

Searches Semantic Scholar API for real academic papers related to
source_analysis content.  Produces a literature_support artifact
that the Writer can use for genuine citations.

Key anti-fabrication rule: excerpt is copied verbatim from the API
response's ``abstract`` field — LLM is never asked to paraphrase or
remember paper details.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from hermes.core.llm_config import get_llm

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
REQUEST_TIMEOUT = 30  # seconds


def _generate_keywords(source_analysis: dict[str, Any], provider: str = "opencode_go") -> list[str]:
    """Extract 2-4 English search phrases from source_analysis content.

    Uses deterministic phrase extraction (no LLM) for reliability and speed.
    The Semantic Scholar API handles the actual search — bad keywords just
    return fewer results, which is safe.
    """
    summary = source_analysis.get("paragraphs_summary", "")
    tables = source_analysis.get("tables", [])
    images = source_analysis.get("images", [])

    # Collect all English text
    text = summary
    for table in tables:
        for row in table:
            text += " " + " ".join(str(c) for c in row)
    for img in images:
        text += " " + img.get("description", "")

    # Extract meaningful multi-word candidates:
    # 1. Sequences of 2-3 capitalized words (likely proper nouns / technical terms)
    # 2. Known academic domain terms from the text
    candidates: list[str] = []

    # Multi-word capitalized phrases: e.g. "Vision Transformer", "Image Classification"
    cap_phrases = re.findall(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
    candidates.extend(p.strip().lower() for p in cap_phrases if len(p.strip()) > 8)

    # Domain-specific noun phrases from the context
    # Look for patterns like "X-based Y", "X of Y", "X and Y"
    domain_patterns = re.findall(
        r"(?:[a-z]+-based\s+[a-z]+(?:\s+[a-z]+)?)",
        text.lower(),
    )
    candidates.extend(domain_patterns)

    # If still empty, extract the longest words as single-term fallback
    if not candidates:
        words = re.findall(r"[A-Za-z]{6,}", text)
        # Group into pairs
        for i in range(0, len(words) - 1, 2):
            candidates.append(f"{words[i].lower()} {words[i+1].lower()}")

    # Dedupe preserving order, limit to 4
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        c = c.strip().lower()
        if c not in seen and len(c) > 4:
            seen.add(c)
            result.append(c)
    return result[:4]


def _search_semantic_scholar(query: str, limit: int = 5, max_retries: int = 2) -> tuple[list[dict[str, Any]], str | None]:
    """Call Semantic Scholar API and return (entries, error_message).

    ``error_message`` is None on success, or a string describing the failure
    (e.g. "rate_limited: 429 after 3 retries").
    """
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,abstract,url,externalIds,citationCount",
    }
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                last_error = f"rate_limited: 429 (attempt {attempt+1})"
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            papers = data.get("data", [])
            entries = []
            for paper in papers:
                title = paper.get("title", "").strip()
                if not title:
                    continue
                authors_list = paper.get("authors", [])
                authors = ", ".join(a.get("name", "") for a in authors_list if a.get("name"))
                year = paper.get("year") or ""
                venue = paper.get("venue", "") or ""
                url = paper.get("url", "") or ""
                doi = (paper.get("externalIds") or {}).get("DOI", "") or ""
                abstract = paper.get("abstract") or ""
                excerpt = (abstract[:500] if abstract else "").strip()
                citation_count = paper.get("citationCount") or 0
                # Only include entries with a usable excerpt (anti-fabrication:
                # we need verifiable content to cite).  Entries without an
                # abstract are skipped rather than included with empty excerpt,
                # because a single empty excerpt would fail the whole artifact.
                if (venue or citation_count >= 1) and excerpt:
                    entries.append({
                        "title": title,
                        "authors": authors,
                        "year": str(year),
                        "venue": venue,
                        "url": url,
                        "doi": doi,
                        "excerpt": excerpt,
                        "citation_count": citation_count,
                    })
            return entries, None
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < max_retries:
            time.sleep(3)

    return [], last_error


def build_literature_support(
    source_analysis: dict[str, Any],
    provider: str = "opencode_go",
    max_papers_per_query: int = 3,
) -> dict[str, Any]:
    """Search Semantic Scholar and return a literature_support artifact.

    ``entries`` may be empty if no relevant papers are found — that is
    a valid result (the rubric does not require a minimum count).
    """
    keywords = _generate_keywords(source_analysis, provider=provider)
    all_entries: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    errors: list[str] = []

    for kw in keywords[:4]:
        papers, err = _search_semantic_scholar(kw, limit=max_papers_per_query)
        if err:
            errors.append(f"{kw}: {err}")
        for paper in papers:
            title = paper["title"].lower()
            if title not in seen_titles:
                seen_titles.add(title)
                all_entries.append(paper)
        time.sleep(0.5)

    return {
        "artifact_type": "literature_support",
        "queries_used": keywords,
        "search_attempted": True,
        "search_error": "; ".join(errors) if errors else None,
        "entries": all_entries,
    }


def literature_support_to_json(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2)


def run_literature_researcher(
    workspace,
    source_analysis_artifact: dict[str, Any],
    artifact_id: str,
    provider: str = "opencode_go",
) -> dict:
    """End-to-end: read source_analysis → search → save & verify literature_support."""
    from hermes.core.storage import save_artifact, read_artifact_content, get_artifact
    from hermes.core.verifier import verify_artifact, finalize_verification
    from hermes.rubrics import load_rubric

    workspace.ensure_initialized()
    source_content = read_artifact_content(workspace, source_analysis_artifact)
    source_data = json.loads(source_content)

    artifact_data = build_literature_support(source_data, provider=provider)
    content = literature_support_to_json(artifact_data)

    artifact = save_artifact(
        workspace=workspace,
        artifact_id=artifact_id,
        content=content,
        artifact_type="literature_support",
        produced_by_task=f"lit-researcher-{artifact_id}",
        metadata={
            "source_artifact_id": source_analysis_artifact.get("artifact_id"),
            "source_artifact_version": source_analysis_artifact.get("version"),
        },
    )

    rubric = load_rubric("literature_support")
    result = verify_artifact("literature_support", content, rubric)
    finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        "literature_support",
        result,
        notes="P5.2.5 Literature Researcher end-to-end",
        rubric_pass_threshold=rubric.get("pass_threshold"),
    )

    return get_artifact(workspace, artifact_id, artifact["version"])
