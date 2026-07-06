"""
Debate Opponent subagent for Hermes Phase 3.

Challenges the academic correctness of an artifact during debate_review.
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


def build_opponent_agent(provider: str | None = None):
    """Return a CrewAI Opponent Agent that challenges artifact correctness."""
    return Agent(
        role="Academic Opponent",
        goal=(
            "Tim kiem loi hoc thuat, thieu sot, va lap luan yeu trong artifact. "
            "Phan bien dua tren bang chung va logic."
        ),
        backstory=(
            "Ban la mot nha phan bien hoc thuat kho tinh, co nhiem vu tim ra "
            "moi diem yeu, sai sot, va thieu nhat quan trong artifact. "
            "Ban luon dua ra dan chung cu the, khong chi trich chung chung."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],
    )


def build_opponent_argument_task(
    agent,
    artifact_content: str,
    artifact_type: str,
    previous_rounds: list | None = None,
    output_path: str | None = None,
):
    """Return a CrewAI Task asking the opponent to challenge the artifact."""
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
            f"Hay phan hoi lai cac lap luan bao ve cua Proponent o vong truoc "
            f"va dua ra cac phe phan moi hoac sau hon."
        )

    description = (
        f"Ban la nguoi phan bien mot artifact loai '{artifact_type}'. "
        f"Duoi day la noi dung artifact:\n\n"
        f"---\n{artifact_content}\n---\n"
        f"{previous_context}\n"
        f"Nhiem vu: Tim ra cac loi hoc thuat, thieu sot, lap luan yeu, "
        f"hoac nhung cho thieu nhat quan trong artifact. "
        f"Hay chi ra CU THE: trich dan nao sai, logic nao yeu, "
        f"thong tin nao co the la hallucination. "
        f"Tra loi bang tieng Viet."
    )

    kwargs = {
        "description": description,
        "expected_output": "Luan diem phan bien bang tieng Viet, chi ra loi cu the trong artifact.",
        "agent": agent,
    }
    if output_path:
        kwargs["output_file"] = output_path

    from crewai import Task
    return Task(**kwargs)
