"""
Curriculum Designer subagent for Hermes.

Phase 2 scope:
- Reads lit_review artifact content + learning objectives.
- Produces a course_outline Markdown artifact.
- Follows pattern from agents/researcher.py.
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
        "max_tokens": cfg.get("max_tokens", 4000),
    }
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return LLM(**kwargs)


def build_curriculum_designer_agent(provider: str | None = None):
    return Agent(
        role="Curriculum Designer",
        goal="Thiet ke outline bai giang ro rang, bam sat learning objectives va lit review dau vao",
        backstory=(
            "Ban la chuyen gia thiet ke chuong trinh giang day, luon dam bao outline "
            "co the danh gia duoc va phu hop voi moi muc tieu hoc tap."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_course_outline_task(
    agent,
    lit_review_content: str,
    learning_objectives: str,
    output_path: str,
):
    return Task(
        description=(
            "Dua tren lit review sau:\n"
            f"{lit_review_content}\n\n"
            "Va learning objectives:\n"
            f"{learning_objectives}\n\n"
            "Viet mot course outline theo dinh dang Markdown bat buoc co 3 phan:\n"
            "1. Learning Objectives — muc tieu hoc tap cu the, co the danh gia duoc\n"
            "2. Session Breakdown — chia theo tuan/buoi cu the (VD: Week 1, Week 2...)\n"
            "3. Assessment Hooks — chi ra diem danh gia trong tung phan\n\n"
            "Outline phai bam sat noi dung lit review, co trich dan nguon khi phu hop."
        ),
        expected_output=(
            "Markdown day du 3 phan: Learning Objectives, Session Breakdown, Assessment Hooks. "
            "Co the hien thi duoi dang bang hoac danh sach."
        ),
        agent=agent,
        output_file=output_path,
    )
