"""
Editor subagent for Hermes.

Phase 2 scope:
- Reads a verified artifact (lecture_draft) that has already passed rubric verification.
- Normalizes formatting, improves clarity, applies house style.
- Does NOT add new claims or new content — only edits/reshapes what is given.
- Does NOT have external tools.
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
        "temperature": 0.2,  # Lower temperature for editorial consistency
        "timeout": cfg.get("timeout", 120),
        "max_tokens": cfg.get("max_tokens", 8000),
    }
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return LLM(**kwargs)


def build_editor_agent(provider: str | None = None):
    return Agent(
        role="Editor",
        goal="Chinh sua van ban da qua kiem tra, chuan hoa cu phap, cai thien ngon ngu",
        backstory=(
            "Ban la mot biên tap Vien hau can, chuyen nghiep trong viec chuan hoa "
            "van ban khoa hoc. Ban khong bao gio tu them claim moi — chi format lai "
            "va lam ro nhung gi da co. Ban giu ngu nguyen tat ca cac trich dan va "
            "noi dung co ban."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_edit_task(
    agent,
    artifact_content: str,
    output_path: str,
):
    return Task(
        description=(
            "Ban nhan mot van ban da duoc kiem tra va xac nhan (verified). "
            "Cong viec cua ban chi la CHINH SUA, KHONG duoc them noi dung moi.\n\n"
            "Thuc hien cac bien phap chinh sua sau:\n"
            "- Chuan hoa tieu de, dau cua cau, danh sach cho nhat quan\n"
            "- Dam bao giong noi that, nhung van chinh xac ve noi dung\n"
            "- Loai bo cac loi chinh ta, cu phap, va sai lam dinh dang\n"
            "- Giu nguyen TAT CA cac trich dan, so lieu, va claim cua ban goc\n"
            "- Khong duoc them bat ky claim hay nguồn moi nao\n\n"
            "Van ban dau vao:\n"
            f"{artifact_content}"
        ),
        expected_output=(
            "Van ban da chinh sua, chuan hoa, giong noi dung goc nhung nang cao ve ngon ngu. "
            "Tat ca trich dan va nguồn phai giu nguyen."
        ),
        agent=agent,
        output_file=output_path,
    )
