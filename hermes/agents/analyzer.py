"""Analyzer utilities for Phase 5 source_analysis artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes.core.llm_config import get_llm


class AnalyzerError(RuntimeError):
    """Raised when analyzer input is malformed."""


def build_source_analysis(ingested_doc: dict[str, Any], provider: str = "local_cx") -> dict[str, Any]:
    """Combine docx text, tables, and image descriptions into source_analysis."""
    paragraphs = ingested_doc.get("paragraphs", [])
    tables = ingested_doc.get("tables", [])
    images = ingested_doc.get("images", [])

    if not isinstance(paragraphs, list) or not isinstance(tables, list) or not isinstance(images, list):
        raise AnalyzerError("ingested_doc must contain list fields: paragraphs, tables, images")

    llm = get_llm(provider)
    described_images = []
    for image in images:
        described_images.append(_describe_image_entry(llm, image))

    summary = _summarize_paragraphs(paragraphs)
    key_statistics = _extract_key_statistics(paragraphs, tables, described_images)

    return {
        "artifact_type": "source_analysis",
        "paragraphs_summary": summary,
        "tables": tables,
        "images": described_images,
        "key_statistics": key_statistics,
    }


def _describe_image_entry(llm, image: dict[str, Any]) -> dict[str, Any]:
    image_path = image.get("path", "")
    prompt = (
        "Mô tả ảnh tài liệu khoa học này thật cụ thể: loại biểu đồ/sơ đồ gì, "
        "có số liệu nào, xu hướng nào, chú thích nào. Nếu có văn bản trong ảnh, hãy đọc lại."
    )
    described = dict(image)
    try:
        data_url = _image_file_to_data_url(image_path)
        described["description"] = llm.describe_image(data_url, prompt)
    except Exception as exc:  # pragma: no cover - exercised via test doubles
        described["description"] = f"[LOI DOC ANH: {exc}]"
    return described


def _image_file_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
    encoded = path.read_bytes().hex()
    # Use hex -> bytes -> base64 via stdlib-free JSON roundtrip is wasteful; keep binary path local.
    import base64

    encoded_b64 = base64.b64encode(bytes.fromhex(encoded)).decode("ascii")
    return f"data:{mime};base64,{encoded_b64}"


def _summarize_paragraphs(paragraphs: list[str], max_items: int = 5) -> str:
    if not paragraphs:
        return ""
    selected = [p.strip() for p in paragraphs if p.strip()][:max_items]
    return " ".join(selected)


def _extract_key_statistics(
    paragraphs: list[str],
    tables: list[list[list[str]]],
    images: list[dict[str, Any]],
) -> list[str]:
    stats: list[str] = []

    import re

    for paragraph in paragraphs:
        for match in re.findall(r"\b\d+(?:[.,]\d+)?%?\b", paragraph):
            stats.append(match)

    for table in tables:
        for row in table:
            numeric_cells = [cell for cell in row if any(ch.isdigit() for ch in cell)]
            if numeric_cells:
                stats.append(" | ".join(numeric_cells))

    for image in images:
        description = image.get("description", "")
        if description:
            for match in re.findall(r"\b\d+(?:[.,]\d+)?%?\b", description):
                stats.append(match)

    # Preserve order while removing duplicates.
    deduped: list[str] = []
    seen = set()
    for item in stats:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def source_analysis_to_json(analysis: dict[str, Any]) -> str:
    return json.dumps(analysis, ensure_ascii=False, indent=2)


def run_analyzer(
    workspace,
    docx_path: str,
    artifact_id: str,
    provider: str = "local_cx",
    task_id: str = "analyzer-task",
) -> dict:
    """End-to-end: ingest docx → build source_analysis → save & verify.

    Returns the artifact record (with verification_status set).
    """
    from hermes.core.docx_ingest import ingest_docx
    from hermes.core.storage import save_artifact
    from hermes.core.verifier import verify_artifact, finalize_verification
    from hermes.rubrics import load_rubric

    workspace.ensure_initialized()
    image_dir = str(Path(workspace.artifact_dir) / "extracted-images")

    ingested = ingest_docx(docx_path, image_dir)
    analysis = build_source_analysis(ingested, provider=provider)
    content = source_analysis_to_json(analysis)

    artifact = save_artifact(
        workspace=workspace,
        artifact_id=artifact_id,
        content=content,
        artifact_type="source_analysis",
        produced_by_task=task_id,
        metadata={"docx_source": str(docx_path)},
    )

    rubric = load_rubric("source_analysis")
    result = verify_artifact("source_analysis", content, rubric)
    finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        "source_analysis",
        result,
        notes="Analyzer end-to-end",
        rubric_pass_threshold=rubric.get("pass_threshold"),
    )

    # Re-read so caller sees the updated verification_status
    from hermes.core.storage import get_artifact
    return get_artifact(workspace, artifact_id, artifact["version"])
