"""
Content Writer subagent for Hermes.

Phase 2 scope:
- Reads course_outline artifact content.
- Produces a lecture_draft Markdown artifact.
"""

from crewai import Agent, LLM, Task

try:
    from hermes.core.llm_config import get_llm_config
except ModuleNotFoundError:
    from hermes.core.llm_config import get_llm_config


def _build_llm(provider: str | None = None):
    cfg = get_llm_config(provider)
    kwargs = {
        "model": cfg["model"],
        "api_key": cfg["api_key"],
        "temperature": 0.3,
        "timeout": cfg.get("timeout", 120),
        "max_tokens": cfg.get("max_tokens", 8000),
    }
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return LLM(**kwargs)


def build_content_writer_agent(provider: str | None = None):
    return Agent(
        role="Content Writer",
        goal="Viet ban thao lecture draft day du, chi tiet, co vi du minh hoa",
        backstory=(
            "Ban la mot giang vien co kinh nghiem, viet bai giang ro rang, "
            "co theo doi cac nguon trich dan ro rang va co vi du thuc te cho moi khai niem."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_lecture_draft_task(
    agent,
    course_outline_content: str,
    output_path: str,
):
    return Task(
        description=(
            "Dua tren course outline sau:\n"
            f"{course_outline_content}\n\n"
            "Viet mot lecture draft day du cho MOT buoi hoc (moi section cua outline). "
            "Yeu cau bat buoc:\n"
            "- Moi section trong outline deu phai co noi dung\n"
            "- Moi section phai co it nhat 1 vi du minh hoa (VD: 'For example...')\n"
            "- Bai draft phai tren 500 tu\n"
            "- Khong duoc them so lieu hay claim thiếu nguồn; neu co so lieu phai ghi nguon ngay sau\n"
            "- Dinh dang Markdown ro rang, co tieu de theo phan cua outline"
        ),
        expected_output=(
            "Van ban Markdown bai giang day du cho 1 buoi hoc, "
            "voi tieu de, noi dung, vi du, va trich dan nguon (neu co). "
            "Tong the tren 500 tu."
        ),
        agent=agent,
        output_file=output_path,
    )
