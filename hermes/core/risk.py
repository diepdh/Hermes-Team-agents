"""Risk matrix: gán risk_level cho artifact_type + risk-adjusted pass threshold."""

RISK_MATRIX = {
    "lit_review_md":    "low",
    "source_analysis":  "low",
    "literature_support": "high",
    "course_outline":   "medium",
    "lecture_draft":    "high",
    "quiz_bank":        "high",
    "paper_draft":      "high",
    "final_paper":      "critical",
    "verified_content": "low",
    "final_content":    "medium",
    "debate_verdict":   "critical",
}

# Ngưỡng hiệu lực tối thiểu theo risk_level.
# Đây là SÀN (floor): nếu rubric base threshold > sàn này thì vẫn dùng rubric base.
RISK_ADJUSTED_FLOOR = {
    "low": 0.0,        # không nâng
    "medium": 0.0,     # không nâng, dùng nguyên rubric base
    "high": 0.85,
    "critical": 0.90,
}

# Artifact types that must NOT trigger a debate_review, even if their
# risk level is high/critical.  This prevents infinite recursion
# (e.g. debating the output of a debate).
SKIP_DEBATE_TYPES = {"debate_verdict"}


def should_trigger_debate(artifact_type: str) -> bool:
    """Return True if this artifact type should trigger a debate when
    risk ∈ {high, critical} and rubric passes."""
    if artifact_type in SKIP_DEBATE_TYPES:
        return False
    return get_risk_level(artifact_type) in {"high", "critical"}


def get_risk_level(artifact_type: str) -> str:
    """Return risk level for an artifact type.

    Unknown types default to "medium" (not "low") to avoid missing
    risk registration for newly added artifact types.
    """
    return RISK_MATRIX.get(artifact_type, "medium")


def get_effective_threshold(artifact_type: str, rubric_base_threshold: float) -> float:
    """Return the effective pass threshold after risk adjustment.

    The floor is determined by the artifact's risk level. The effective
    threshold is the maximum of the rubric base threshold and the floor,
    so risk adjustment only ever raises the bar, never lowers it.
    """
    floor = RISK_ADJUSTED_FLOOR.get(get_risk_level(artifact_type), 0.0)
    return max(rubric_base_threshold, floor)
