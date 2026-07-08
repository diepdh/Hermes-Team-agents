"""Paper Writer subagent for Phase 5.2.

Reads a verified source_analysis artifact and produces an IMRaD paper_draft.
Uses opencode_go (text-only) since input is already extracted text/descriptions.
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, LLM, Task


def _build_llm(provider: str = "opencode_go", max_tokens: int | None = None):
    """Build a CrewAI LLM instance from Hermes configuration.

    ``max_tokens`` overrides the provider-level setting so this agent can
    request a larger context window without affecting other agents sharing
    the same provider.
    """
    try:
        from hermes.core.llm_config import get_llm_config
    except ModuleNotFoundError:
        from hermes.core.llm_config import get_llm_config

    cfg = get_llm_config(provider)
    kwargs = {
        "model": cfg["model"],
        "api_key": cfg["api_key"],
        "temperature": 0.3,
        "timeout": cfg.get("timeout", 120),
        "max_tokens": max_tokens if max_tokens is not None else cfg.get("max_tokens", 4000),
    }
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return LLM(**kwargs)


def build_paper_writer_agent(provider: str = "opencode_go", max_tokens: int = 8000):
    """Return a CrewAI Paper Writer Agent."""
    return Agent(
        role="Paper Writer",
        goal=(
            "Viết bài báo khoa học định dạng IMRaD chính xác, bám sát dữ liệu "
            "nguồn, không tự ý thêm số liệu hay kết luận ngoài phạm vi phân tích."
        ),
        backstory=(
            "Bạn là một nhà nghiên cứu kỳ cựu chuyên viết báo cáo khoa học từ "
            "dữ liệu thô. Bạn luôn trích dẫn đúng nguồn, giữ nguyên số liệu gốc, "
            "và tuân thủ nghiêm ngặt cấu trúc IMRaD."
        ),
        llm=_build_llm(provider, max_tokens=max_tokens),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_paper_draft_task(
    agent,
    source_analysis_content: str,
    output_path: str,
    paper_title: str = "Research Analysis Report",
) -> Task:
    """Return a CrewAI Task asking the agent to produce an IMRaD paper_draft."""
    return Task(
        description=(
            f"Dựa vào dữ liệu phân tích nguồn (source_analysis) dưới đây, "
            f"hãy viết một bài báo khoa học hoàn chỉnh theo cấu trúc IMRaD "
            f"(Title, Abstract, Introduction, Methods, Results, Discussion, References).\n\n"
            f"YÊU CẦU BẮT BUỘC:\n"
            f"1. Có đủ 7 phần: Title, Abstract, Introduction, Methods, Results, "
            f"Discussion, References (đúng IMRaD, KHÔNG thêm Conclusion riêng).\n"
            f"2. Mọi số liệu trong bài phải đến từ source_analysis bên dưới — "
            f"KHÔNG ĐƯỢC BỊA THÊM số liệu không có trong nguồn.\n"
            f"3. Phần Methods phải mô tả cách dữ liệu được thu thập/xử lý (dựa "
            f"trên mô tả trong source_analysis).\n"
            f"4. Phần Results phải trình bày số liệu từ bảng và mô tả ảnh trong "
            f"source_analysis, bao gồm cả key_statistics.\n"
            f"5. [QUAN TRỌNG] Phần References: TUYỆT ĐỐI KHÔNG ĐƯỢC BỊA RA "
            f"tên tác giả, tựa đề, nhà xuất bản, hay bất kỳ citation học thuật nào "
            f"không có thật. Nếu source_analysis không cung cấp danh sách tài liệu "
            f"tham khảo thực sự (có URL hoặc trích dẫn gốc), hãy để phần References "
            f"trống hoặc ghi 'Data provided by the attached source analysis document.' "
            f"— KHÔNG tạo tên giả như Smith (2020), Doe (2019), Johnson (2021) "
            f"hay bất kỳ tên nào khác.\n\n"
            f"=== SOURCE_ANALYSIS ===\n{source_analysis_content}\n=== END ==="
        ),
        expected_output=(
            "Bài báo khoa học Markdown hoàn chỉnh theo IMRaD: Title, Abstract, "
            "Introduction, Methods, Results, Discussion, References. "
            "References chỉ chứa nguồn thật từ source_analysis hoặc để trống."
        ),
        agent=agent,
        output_file=output_path,
    )


def run_paper_writer(
    workspace,
    source_analysis_artifact: dict[str, Any],
    artifact_id: str,
    provider: str = "opencode_go",
) -> dict:
    """End-to-end: read source_analysis → writer agent → save & verify paper_draft.

    Returns the artifact record (with verification_status set).
    """
    from crewai import Crew, Process
    from hermes.core.storage import save_artifact, read_artifact_content, get_artifact
    from hermes.core.verifier import verify_artifact, finalize_verification
    from hermes.rubrics import load_rubric

    workspace.ensure_initialized()

    source_content = read_artifact_content(workspace, source_analysis_artifact)
    agent = build_paper_writer_agent(provider)
    output_path = str(workspace.artifact_dir / f"{artifact_id}_v1.md")
    task = build_paper_draft_task(agent, source_content, output_path)

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    crew.kickoff()
    crew.calculate_usage_metrics()

    with open(output_path, encoding="utf-8") as f:
        content = f.read()

    artifact = save_artifact(
        workspace=workspace,
        artifact_id=artifact_id,
        content=content,
        artifact_type="paper_draft",
        produced_by_task=f"writer-{artifact_id}",
        metadata={
            "source_artifact_id": source_analysis_artifact.get("artifact_id"),
            "source_artifact_version": source_analysis_artifact.get("version"),
        },
    )

    rubric = load_rubric("R-paper-draft-v1")
    result = verify_artifact("paper_draft", content, rubric)
    finalize_verification(
        workspace,
        artifact["artifact_id"],
        artifact["version"],
        "paper_draft",
        result,
        notes="P5.2 Paper Writer end-to-end",
        rubric_pass_threshold=rubric.get("pass_threshold"),
    )

    return get_artifact(workspace, artifact_id, artifact["version"])
