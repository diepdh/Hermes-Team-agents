"""
Debate Proponent subagent for Hermes Phase 3.

Defends the academic correctness of an artifact during debate_review.
Runs as a CrewAI Agent within the local debate crew.
"""

from crewai import Agent

try:
    from hermes.core.llm_config import get_llm_config
except ModuleNotFoundError:
    from hermes.core.llm_config import get_llm_config
from crewai import LLM


def _build_llm(provider: str | None = None):
    """Build a CrewAI LLM instance from Hermes configuration."""
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


def build_proponent_agent(provider: str | None = None):
    """Return a CrewAI Proponent Agent that defends artifact correctness."""
    return Agent(
        role="Academic Proponent",
        goal=(
            "Bao ve tinh dung dan hoc thuat cua artifact. "
            "Lap luan dua tren bang chung, trich dan, va logic hoc thuat."
        ),
        backstory=(
            "Ban la mot chuyen gia trong linh vuc, co nhiem vu bao ve noi dung "
            "cua artifact truoc moi phe phan. Ban khong bao gio bia dat hoac "
            "suy dien ngoai nhung gi artifact da trinh bay."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_proponent_argument_task(
    agent,
    artifact_content: str,
    artifact_type: str,
    previous_rounds: list | None = None,
    output_path: str | None = None,
):
    """Return a CrewAI Task asking the proponent to defend the artifact."""
    previous_context = ""
    if previous_rounds:
        rounds_text = "\n\n".join(
            f"## Vong {r['round']}\n"
            f"### Luan diem benh vuc (Proponent):\n{r['proponent_argument']}\n\n"
            f"### Luan diem phan bien (Opponent):\n{r['opponent_argument']}"
            for r in previous_rounds
        )
        previous_context = (
            f"\n\n# Cac vong tranh luan truoc do:\n\n{rounds_text}\n\n"
            f"Hay phan hoi lai cac phe phan cua Opponent o vong truoc "
            f"va cung co lap luan cua ban."
        )

    description = (
        f"Ban la nguoi bao ve tinh dung dan cua mot artifact loai '{artifact_type}'. "
        f"Duoi day la noi dung artifact:\n\n"
        f"---\n{artifact_content}\n---\n"
        f"{previous_context}\n"
        f"Nhiem vu: Trinh bay lap luan bao ve artifact nay. "
        f"Chi ra cac diem manh ve mat hoc thuat, "
        f"cac trich dan duoc su dung dung cach, "
        f"va logic cua cac lap luan trong artifact. "
        f"Tra loi bang tieng Viet."
    )

    kwargs = {
        "description": description,
        "expected_output": "Luan diem benh vuc bang tieng Viet, co dan chung cu the tu artifact.",
        "agent": agent,
    }
    if output_path:
        kwargs["output_file"] = output_path

    from crewai import Task
    return Task(**kwargs)
