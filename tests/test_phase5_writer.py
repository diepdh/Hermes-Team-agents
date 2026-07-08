"""Unit tests for Phase 5.2 — Paper Writer subagent."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.agents.paper_writer import (
    build_paper_writer_agent,
    build_paper_draft_task,
    run_paper_writer,
)
from hermes.core.verifier import CHECKER_REGISTRY, verify_artifact
from hermes.core.workspace import Workspace
from hermes.rubrics import load_rubric

FAKE_SOURCE_ANALYSIS = json.dumps(
    {
        "artifact_type": "source_analysis",
        "paragraphs_summary": "Study on formative assessment in higher education. Table shows accuracy 92% with 128 samples.",
        "tables": [[["Metric", "Value"], ["Accuracy", "92%"], ["Samples", "128"]]],
        "images": [
            {
                "path": "img_001.png",
                "filename": "img_001.png",
                "order": 1,
                "position_context": "Sales comparison",
                "description": "Biểu đồ cột so sánh A=12 và B=18.",
            }
        ],
        "key_statistics": ["92%", "128", "12", "18"],
    },
    ensure_ascii=False,
)


@pytest.fixture
def good_paper_draft() -> str:
    return """# Title: Formative Assessment Effectiveness in Higher Education

## Abstract

This study examines formative assessment using 128 samples, achieving 92% accuracy according to standardized testing frameworks. The research explores the comparative performance between two categories and provides evidence for formative methods.

## Introduction

Formative assessment is critical in higher education. Prior work by Smith (2020) and Doe (2021) explored various methods including feedback loops and peer evaluation. Johnson (2019) identified significant gaps in longitudinal research on assessment effectiveness. The current study addresses these gaps by conducting a comprehensive analysis using a robust dataset of 128 samples across multiple dimensions. This research contributes to the growing body of literature on evidence-based educational practices and provides actionable insights for practitioners and policymakers alike. The importance of this study lies in its systematic approach to evaluating assessment outcomes using both quantitative metrics and visual data representations. Researchers have long advocated for mixed-methods approaches in educational research, and this study exemplifies that methodology by combining statistical tables with graphical analysis.

## Methods

Data was collected from 128 samples using a standardized assessment protocol. Analysis used comparison of categories A=12 and B=18 to determine relative performance differences. The methodology follows established procedures from prior research including Smith (2020) and Doe (2021), ensuring reliability and validity of the findings. Statistical analysis was performed to validate the significance of observed differences and to establish confidence intervals for the reported metrics. The data processing pipeline involved multiple stages including data cleaning, normalization, comparative analysis, and visualization. Each sample underwent rigorous quality control checks before inclusion in the final dataset. The analytical framework was designed to accommodate both categorical comparisons and continuous growth measurements.

## Results

The accuracy reached 92% across all samples tested, demonstrating strong performance of the assessment method. Category B (value 18) outperformed category A (value 12) by approximately 50%, indicating substantial differentiation in the measured outcomes. The table of metrics confirms these findings with consistent patterns across all test conditions. Key statistics include an accuracy rate of 92% with 128 total samples analyzed, providing sufficient statistical power for the conclusions drawn.

## Discussion

Results confirm formative assessment's positive impact on educational outcomes. The 50% performance gap between categories suggests meaningful differences that warrant further investigation. Limitations include the moderate sample size of 128 and the focus on a single institutional context. Future research should expand to multiple settings and incorporate longitudinal tracking of assessment effects over time. The findings align with previous studies by Smith (2020) and Doe (2021), reinforcing the validity of formative assessment as a reliable measurement tool. The implications extend beyond the immediate context to broader educational policy considerations. Additional research should explore the interaction effects between sample size, assessment methodology, and outcome variability across diverse educational settings and student populations.

## References

- Smith, J. (2020). Assessment methods in higher education. *Journal of Education*, 45(2), 100-120.
- Doe, A. (2021). Feedback and learning outcomes. *Educational Review*, 33(1), 50-70.
- Johnson, B. (2019). Gaps in assessment research practices. *Higher Education Journal*, 22(4), 200-220.
- Williams, C. (2022). Statistical methods for educational data analysis. *Journal of Applied Statistics in Education*, 15(3), 300-325.
- Brown, D. (2018). Comparative assessment techniques: A comprehensive review. *Educational Measurement Review*, 40(1), 75-98.
- Lee, E. (2023). Modern approaches to formative feedback in higher education. *Teaching and Learning Quarterly*, 28(2), 150-175.
"""


def test_paper_writer_agent_initializes():
    agent = build_paper_writer_agent()
    assert agent.role == "Paper Writer"
    assert agent.allow_delegation is False


def test_paper_writer_task_has_output_file():
    agent = build_paper_writer_agent()
    task = build_paper_draft_task(agent, FAKE_SOURCE_ANALYSIS, "/tmp/test.md")
    assert task.output_file.endswith("test.md")
    assert "IMRaD" in task.description
    assert "92%" in task.description


def test_paper_draft_registered_in_checker():
    assert "paper_draft" in CHECKER_REGISTRY


def test_paper_draft_rubric_pass_with_good_artifact(good_paper_draft):
    rubric = load_rubric("paper_draft")
    result = verify_artifact("paper_draft", good_paper_draft, rubric)
    assert result["passed"] is True
    assert result["score"] >= rubric["pass_threshold"]


def test_paper_draft_rubric_fail_missing_sections():
    rubric = load_rubric("paper_draft")
    bad = "# Only Title\n\nSome text without IMRaD structure."
    result = verify_artifact("paper_draft", bad, rubric)
    assert result["detail"]["structure_completeness"] < 1.0


def test_paper_draft_does_not_fabricate_academic_citations():
    """When source_analysis has no real references, paper must NOT invent author names."""
    from hermes.agents.paper_writer import build_paper_writer_agent, build_paper_draft_task
    from crewai import Crew, Process

    # Source has NO references — only a table and image descriptions
    source_no_refs = json.dumps(
        {
            "artifact_type": "source_analysis",
            "paragraphs_summary": "Simple data analysis with one table.",
            "tables": [[["Metric", "Value"], ["Accuracy", "92%"]]],
            "images": [
                {
                    "path": "img.png",
                    "order": 1,
                    "description": "Chart showing value of 42.",
                }
            ],
            "key_statistics": ["92%", "42"],
        },
        ensure_ascii=False,
    )

    agent = build_paper_writer_agent()
    output_path = str(Path(__file__).parent / "fixtures" / "_test_no_fab_refs.md")
    task = build_paper_draft_task(agent, source_no_refs, output_path)

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    crew.kickoff()

    content = Path(output_path).read_text(encoding="utf-8")

    # These patterns indicate fabricated academic citations:
    # "Tên, X. (năm). Tựa đề..." with publisher/journal info
    fabricated_patterns = [
        r"[A-Z][a-z]+,\s+[A-Z]\.\s+\(\d{4}\)\.",   # e.g. Smith, J. (2020).
        r"\*[A-Z][a-z]+\s+[A-Z][a-z]+\*",           # Italicized title in markdown
    ]
    import re
    fabricated_count = sum(
        len(re.findall(pat, content)) for pat in fabricated_patterns
    )

    # Allow at most 1 mention that looks like a citation (may be in prompt context)
    # But full fabricated academic reference list is forbidden
    ref_section_idx = content.lower().find("## references")
    if ref_section_idx != -1:
        ref_content = content[ref_section_idx:]
        # A fabricated reference list has year patterns like (2020) in References
        years_in_refs = len(re.findall(r"\(\d{4}\)", ref_content))
        assert years_in_refs == 0, (
            f"References section contains {years_in_refs} year-pattern(s) "
            f"but source has no real references. Fabricated citations:\n{ref_content[:300]}"
        )


def test_paper_draft_references_actual_data_not_fabricated():
    """Writer output should mention numbers from source_analysis, not random ones."""
    from hermes.agents.paper_writer import build_paper_writer_agent, build_paper_draft_task
    from crewai import Crew, Process

    agent = build_paper_writer_agent()
    output_path = str(Path(__file__).parent / "fixtures" / "_test_paper_artifact.md")
    task = build_paper_draft_task(agent, FAKE_SOURCE_ANALYSIS, output_path)

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    crew.kickoff()

    content = Path(output_path).read_text(encoding="utf-8")
    # Should contain key numbers from source
    assert "92%" in content or "92" in content, "Output missing 92% from source"
    assert "128" in content, "Output missing 128 from source"
    # Should NOT fabricate large random numbers
    assert "9999" not in content, "Output contains fabricated number 9999"


def test_paper_draft_persisted_through_save_artifact(tmp_path):
    """Artifact should be persisted to workspace, readable back."""
    from hermes.core.storage import save_artifact, get_artifact, read_artifact_content

    ws = Workspace(str(tmp_path))
    ws.ensure_initialized()

    content = "# Test Paper\n\n## Abstract\n\nTest abstract.\n\n## Introduction\n\nIntro text.\n\n## Methods\n\nMethods.\n\n## Results\n\nResults.\n\n## Discussion\n\nDiscussion.\n\n## References\n\nRef 1."
    artifact = save_artifact(
        workspace=ws,
        artifact_id="writer-test-persist",
        content=content,
        artifact_type="paper_draft",
        produced_by_task="T-writer-test",
    )
    assert artifact["artifact_id"] == "writer-test-persist"

    retrieved = get_artifact(ws, "writer-test-persist", artifact["version"])
    assert retrieved is not None
    assert retrieved["type"] == "paper_draft"

    read_back = read_artifact_content(ws, retrieved)
    assert "Test Paper" in read_back
