"""
Researcher subagent for Hermes.

Phase 1 scope:
- Builds a CrewAI Agent configured from hermes.core.llm_config.
- Does NOT attach web_search tools yet (Phase 1.1).
- Produces a literature-review Markdown artifact saved to output_path.
"""

from crewai import Agent, LLM, Task

try:
    from hermes.core.llm_config import get_llm_config
except ModuleNotFoundError:
    from core.llm_config import get_llm_config


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


def build_researcher_agent(provider: str | None = None):
    """Return a CrewAI Researcher Agent."""
    return Agent(
        role="Researcher",
        goal="Tong hop tai lieu hoc thuat chinh xac, co trich dan ro rang",
        backstory=(
            "Ban la mot nha nghien cuu can trong, luon ghi ro nguon goc moi "
            "thong tin va khong suy dien ngoai pham vi tai lieu tim duoc."
        ),
        llm=_build_llm(provider),
        verbose=True,
        allow_delegation=False,
        tools=[],  # Phase 1: no real web search yet.
    )


def build_lit_review_task(agent, research_question: str, output_path: str):
    """Return a CrewAI Task asking the agent to produce a lit review."""
    return Task(
        description=(
            f"Viet mot ban tong hop tai lieu (literature review) tra loi cau hoi: "
            f"'{research_question}'. Yeu cau: co phan Summary, co Citations "
            f"(it nhat 3 nguon, dinh dang APA), va co phan 'Gaps Identified'."
        ),
        expected_output=(
            "Van ban Markdown co it nhat 3 phan: Summary, Citations, Gaps Identified"
        ),
        agent=agent,
        output_file=output_path,
    )
