"""
Assessment Builder subagent for Hermes.

Phase 2 scope:
- Reads lecture_draft artifact content.
- Produces a quiz_bank Markdown artifact with questions + answer key.
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
        "max_tokens": cfg.get("max_tokens", 6000),
    }
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return LLM(**kwargs)


def build_assessment_builder_agent(provider: str | None = None):
    return Agent(
        role="Assessment Builder",
        goal="Xay dung bo câu hoi kiem tra day du, co dap an, co muc do kho khac nhau",
        backstory=(
            "Ban la chuyen gia thiet ke danh gia, biet cach tao bo câu hoi "
            "vua kiem tra duoc kien thuc vua kich thich tu duy phan bien, "
            "voi cac muc do kho khac nhau."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_quiz_bank_task(
    agent,
    lecture_draft_content: str,
    output_path: str,
):
    return Task(
        description=(
            "Dua tren lecture draft sau:\n"
            f"{lecture_draft_content}\n\n"
            "Xay dung mot quiz bank voi yeu cau bat buoc:\n"
            "- It nhat 5 câu hoi\n"
            "- Bao gom True/False, Multiple Choice, va Short Answer\n"
            "- Co dap an dung cho moi câu (Answer Key)\n"
            "- Co it nhat 2 muc do kho khac nhau (VD: Easy, Medium, Hard)\n"
            "- Cau hoi phai bam sat noi dung lecture draft\n"
            "- Dinh dang Markdown ro rang, de doc"
        ),
        expected_output=(
            "Van ban Markdown chua it nhat 5 câu hoi, co the loai khac nhau, "
            "co dap an, va chi ro muc do kho. Co the hien thi duoi bang hoac danh sach."
        ),
        agent=agent,
        output_file=output_path,
    )
