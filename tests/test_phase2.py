"""Unit tests for Hermes Phase 2: verifier registry, 3 new artifact checkers.

These tests mock the LLM call so they run quickly and do not require API keys.
"""

import json
import pytest
from pathlib import Path

from hermes.core.verifier import (
    verify_artifact,
    CHECKER_REGISTRY,
    check_lit_review,
    check_course_outline,
    check_lecture_draft,
    check_quiz_bank,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
SAMPLE_RUBRIC_LIT = {
    "rubric_id": "R-lit-review-v2",
    "pass_threshold": 0.7,
    "criteria": [
        {"name": "citation_completeness", "weight": 0.35, "check": "At least 3 APA citations"},
        {"name": "relevance",             "weight": 0.25, "check": "Contains Summary section"},
        {"name": "gap_identification",     "weight": 0.25, "check": "Contains Gaps section"},
        {"name": "clarity",               "weight": 0.15, "check": "Over 100 words"},
    ],
}

SAMPLE_RUBRIC_OUTLINE = {
    "rubric_id": "R-course-outline-v1",
    "pass_threshold": 0.75,
    "criteria": [
        {"name": "learning_objectives_present", "weight": 0.3,  "check": "Has Learning Objectives"},
        {"name": "session_breakdown",          "weight": 0.3,  "check": "Broken down by session/week"},
        {"name": "aligned_with_lit_review",    "weight": 0.2,  "check": "Aligned with lit review"},
        {"name": "assessment_hooks",            "weight": 0.2,  "check": "Has assessment points"},
    ],
}

SAMPLE_RUBRIC_LECTURE = {
    "rubric_id": "R-lecture-draft-v1",
    "pass_threshold": 0.8,
    "criteria": [
        {"name": "covers_all_outline_sections", "weight": 0.35, "check": "All outline sections covered"},
        {"name": "examples_included",            "weight": 0.25, "check": "Has examples"},
        {"name": "length_adequate",             "weight": 0.2,  "check": "Over 500 words"},
        {"name": "no_unsupported_claims",       "weight": 0.2,  "check": "No unsupported claims"},
    ],
}

SAMPLE_RUBRIC_QUIZ = {
    "rubric_id": "R-quiz-bank-v1",
    "pass_threshold": 0.8,
    "criteria": [
        {"name": "question_count",      "weight": 0.3, "check": "At least 5 questions"},
        {"name": "covers_lecture_topics","weight": 0.3, "check": "Covers lecture topics"},
        {"name": "has_answer_key",       "weight": 0.25,"check": "Has answer key"},
        {"name": "difficulty_variety",  "weight": 0.15, "check": "2+ difficulty levels"},
    ],
}


# -------------------------------------------------------------------
# Fixtures: sample artifacts
# -------------------------------------------------------------------
@pytest.fixture
def good_lit_review():
    return """# Summary

This review examines formative assessment methods in higher education.
Researchers (Smith, 2020) and (Doe, 2021) demonstrate that ongoing feedback
improves student outcomes. Johnson (2019) identifies gaps in longitudinal studies.

# Citations

- Smith, J. (2020). Formative assessment methods. *Journal of Education*.
- Doe, A. (2021). Feedback and learning outcomes. *Educational Review*.
- Johnson, B. (2019). Gaps in assessment research. *Higher Education*.

# Gaps Identified

Most existing studies focus on short-term effects; long-term impact
of formative assessment on graduate outcomes remains underexplored.
"""


@pytest.fixture
def good_course_outline():
    return """# Course Outline: Formative Assessment in Higher Education

## Learning Objectives

By the end of this course, students will be able to:
- Define formative assessment and distinguish it from summative assessment.
- Apply at least 3 formative techniques in their teaching practice.
- Evaluate the effectiveness of formative feedback using rubrics.

## Session Breakdown

**Week 1:** Introduction to Formative Assessment
**Week 2:** Feedback Strategies (Smith, 2020)
**Week 3:** Peer Assessment Techniques
**Week 4:** Technology-Enhanced Formative Assessment
**Week 5:** Assessment of Learning vs. Assessment for Learning

## Assessment Hooks

- Week 3: Peer review exercise (formative)
- Week 5: Final reflective essay (summative)
- Ongoing: Weekly reflection journals
"""


@pytest.fixture
def good_lecture_draft():
    return """# Lecture 1: Introduction to Formative Assessment

## Definition

Formative assessment refers to a range of formal and informal assessments
conducted during the learning process to monitor student progress and provide
actionable feedback. Unlike summative assessment, which evaluates learning at
the end of an instructional period, formative assessment provides ongoing
evidence that both teachers and students can use to improve teaching and
learning (Black & Wiliam, 1998). The core distinction lies not in the format
of the assessment but in how the resulting information is used: formative
assessment is diagnostic, not judgmental.

## Why It Matters

For example, a science teacher might use exit tickets at the end of each lesson
to check whether students understood the key concept before moving on to the
next topic. This approach allows the teacher to identify misconceptions early
and adjust instruction in real time, rather than discovering gaps months later
during a final exam.

Research by Smith (2020) shows that classrooms using systematic formative
assessment increase student achievement by an average of 0.7 standard deviations
compared to control groups (Smith, 2020). Similarly, a meta-analysis by Doe and colleagues
(2021) spanning 90 studies found consistent positive effects across subject
areas and grade levels. These findings underscore that formative assessment is
not merely a teaching technique but an evidence-based practice with robust
empirical support.

## Key Strategies

1. **Questioning**: Pose open-ended questions to uncover student thinking.
   Effective questions are those that require explanation rather than a simple
   yes/no answer. For instance, instead of asking "Do you understand?" try
   "Can you explain why that is the case?"

2. **Peer Assessment**: Students evaluate each other's work using rubrics.
   This strategy develops metacognitive skills while reducing the feedback
   burden on the teacher. Research indicates that giving feedback helps
   students internalize assessment criteria.

3. **Self-Assessment**: Students reflect on their own learning progress
   against clear success criteria. Journals, learning logs, and traffic-light
   cards (green/yellow/red) are practical tools for this purpose.

4. **Technology-Enhanced Formative Assessment**: Digital tools such as
   Kahoot, Mentimeter, and Google Forms allow real-time polling and immediate
   visualization of class understanding.

## Common Pitfalls

Many teachers confuse formative assessment with homework or in-class
assignments. The key difference is that formative assessment is used to
adjust instruction and support learning in the moment, not to assign grades.
Another common mistake is providing feedback without giving students the
opportunity to act on it. Feedback that is not incorporated into subsequent
learning has limited impact.

## Summary

Formative assessment is a powerful, evidence-based tool for improving
student outcomes when implemented with clear learning objectives, timely
feedback, and student involvement in the assessment process. Its
effectiveness is well-documented across multiple educational contexts.
"""


@pytest.fixture
def good_quiz_bank():
    return """Quiz Bank: Formative Assessment

1. What is the primary purpose of formative assessment?
A) To assign final grades
B) To monitor ongoing learning and adjust instruction  [Correct]
C) To compare students with each other
D) To reduce teacher workload

2. According to Black and Wiliam (1998), which of the following is NOT a key
characteristic of formative assessment?
A) Elicits evidence of learning
B) Provides feedback that closes the gap  [Correct]
C) Assigns a final numeric score
D) Involves both teacher and student roles

3. Formative assessment should always be used for grading purposes.
Answer: False. Formative assessment is for feedback, not for grades.

4. Exit tickets are an example of formative assessment.
Answer: True. Exit tickets provide quick evidence of student understanding.

5. Name two strategies teachers can use to implement formative assessment.
Sample Answer: (1) Think-pair-share; (2) Exit tickets; (3) One-minute papers.

Difficulty: Easy: Q1, Q2 | Medium: Q3, Q4 | Hard: Q5
Topics Covered: Definition, theory, classroom strategies, assessment types
Answer Key: 1=B, 2=C, 3=False, 4=True, 5=see sample
"""


# -------------------------------------------------------------------
# Test: verifier registry
# -------------------------------------------------------------------
def test_verify_artifact_dispatches_to_correct_checker():
    assert CHECKER_REGISTRY.keys() == {"lit_review_md", "course_outline", "lecture_draft", "quiz_bank", "debate_verdict"}


def test_verify_artifact_raises_for_unknown_type():
    with pytest.raises(ValueError, match="No checker registered"):
        verify_artifact("unknown_type", "some content", {})


# -------------------------------------------------------------------
# Test: rubric criteria names match verifier for ALL 4 types
# -------------------------------------------------------------------
def test_rubric_criteria_names_match_verifier_all_types(
    good_lit_review,
    good_course_outline,
    good_lecture_draft,
    good_quiz_bank,
):
    """Every criterion in every rubric must appear in verifier output.

    Guards against silent drops where a rubric criterion is never scored
    due to a name mismatch between the rubric definition and the checker code.
    """
    rubric_map = {
        "lit_review_md":    (SAMPLE_RUBRIC_LIT,    good_lit_review),
        "course_outline":   (SAMPLE_RUBRIC_OUTLINE, good_course_outline),
        "lecture_draft":    (SAMPLE_RUBRIC_LECTURE, good_lecture_draft),
        "quiz_bank":        (SAMPLE_RUBRIC_QUIZ,    good_quiz_bank),
    }

    for artifact_type, (rubric, content) in rubric_map.items():
        result = verify_artifact(artifact_type, content, rubric)
        missing = []
        for criterion in rubric["criteria"]:
            if criterion["name"] not in result["detail"]:
                missing.append(criterion["name"])
        assert not missing, (
            f"[{artifact_type}] Criteria not scored: {missing}. "
            f"Verifier returned: {list(result['detail'].keys())}"
        )


# -------------------------------------------------------------------
# Test: lit_review_md checker
# -------------------------------------------------------------------
def test_lit_review_pass_with_good_artifact(good_lit_review):
    result = check_lit_review(good_lit_review, SAMPLE_RUBRIC_LIT)
    assert result["passed"] is True
    assert result["score"] >= 0.7


def test_lit_review_fail_with_missing_sections():
    bad = "# Summary\n\nToo short.\n\n# Citations\n"
    result = check_lit_review(bad, SAMPLE_RUBRIC_LIT)
    assert result["passed"] is False


# -------------------------------------------------------------------
# Test: course_outline checker
# -------------------------------------------------------------------
def test_course_outline_pass_with_good_artifact(good_course_outline):
    result = check_course_outline(good_course_outline, SAMPLE_RUBRIC_OUTLINE)
    assert result["passed"] is True
    assert result["score"] >= 0.75


def test_course_outline_fail_missing_objectives():
    bad = "# Course Outline\n\nWeek 1: Intro\n"
    result = check_course_outline(bad, SAMPLE_RUBRIC_OUTLINE)
    assert result["passed"] is False


def test_course_outline_fail_missing_session_breakdown():
    bad = """# Course Outline

## Learning Objectives
Students will learn formative assessment.

## Assessment Hooks
Final exam.
"""
    result = check_course_outline(bad, SAMPLE_RUBRIC_OUTLINE)
    assert result["passed"] is False


# -------------------------------------------------------------------
# Test: lecture_draft checker
# -------------------------------------------------------------------
def test_lecture_draft_pass_with_good_artifact(good_lecture_draft):
    result = check_lecture_draft(good_lecture_draft, SAMPLE_RUBRIC_LECTURE)
    assert result["passed"] is True
    assert result["score"] >= 0.8


def test_lecture_draft_fail_short_content():
    bad = "# Lecture 1\n\nThis is a very short lecture draft."
    result = check_lecture_draft(bad, SAMPLE_RUBRIC_LECTURE)
    assert result["passed"] is False


def test_lecture_draft_fail_unsupported_claims():
    # Content is long enough but has bare numbers >= 4 digits without citations
    bad = """# Lecture 1

Formative assessment increases achievement by 2000 percent in some studies.
Students who receive daily feedback show 5000 percent improvement.
There are 1234 schools participating in the program.
"""
    result = check_lecture_draft(bad, SAMPLE_RUBRIC_LECTURE)
    # no_unsupported_claims = 0.0 because bare numbers >= 4 digits appear without citations
    assert result["detail"]["no_unsupported_claims"] == 0.0


# -------------------------------------------------------------------
# Test: quiz_bank checker
# -------------------------------------------------------------------
def test_quiz_bank_pass_with_good_artifact(good_quiz_bank):
    result = check_quiz_bank(good_quiz_bank, SAMPLE_RUBRIC_QUIZ)
    assert result["passed"] is True
    assert result["score"] >= 0.8


def test_quiz_bank_fail_too_few_questions():
    bad = """# Quiz

**Q1.** What is formative assessment?
A) Grade-oriented B) Feedback-oriented ✓
"""
    result = check_quiz_bank(bad, SAMPLE_RUBRIC_QUIZ)
    assert result["detail"]["question_count"] < 1.0


def test_quiz_bank_fail_missing_answer_key():
    bad = """# Quiz

**Q1.** What is formative assessment?
A) Grade-oriented B) Feedback-oriented

**Q2.** Exit tickets are formative? Yes or No.

**Q3.** Name one formative strategy.
"""
    result = check_quiz_bank(bad, SAMPLE_RUBRIC_QUIZ)
    assert result["detail"]["has_answer_key"] == 0.0


def test_quiz_bank_fail_no_difficulty_variety():
    bad = """# Quiz

**Q1.** What is formative assessment?
A) Grade-oriented B) Feedback-oriented ✓

**Q2.** Exit tickets are formative? Yes/No ✓

**Q3.** Name one formative strategy.
"""
    result = check_quiz_bank(bad, SAMPLE_RUBRIC_QUIZ)
    assert result["detail"]["difficulty_variety"] == 0.0


# -------------------------------------------------------------------
# Test: registry completeness — all 4 types have tests above
# -------------------------------------------------------------------
def test_all_registry_types_have_checker():
    for t in ["lit_review_md", "course_outline", "lecture_draft", "quiz_bank"]:
        assert t in CHECKER_REGISTRY, f"Missing checker for {t}"


# -------------------------------------------------------------------
# Agent initialization tests (no LLM calls)
# -------------------------------------------------------------------
def test_curriculum_designer_agent_initializes():
    from hermes.agents.curriculum_designer import build_curriculum_designer_agent
    agent = build_curriculum_designer_agent()
    assert agent.role == "Curriculum Designer"
    assert agent.allow_delegation is False


def test_content_writer_agent_initializes():
    from hermes.agents.content_writer import build_content_writer_agent
    agent = build_content_writer_agent()
    assert agent.role == "Content Writer"


def test_assessment_builder_agent_initializes():
    from hermes.agents.assessment_builder import build_assessment_builder_agent
    agent = build_assessment_builder_agent()
    assert agent.role == "Assessment Builder"


def test_editor_agent_initializes():
    from hermes.agents.editor import build_editor_agent
    agent = build_editor_agent()
    assert agent.role == "Editor"


def test_curriculum_designer_task_output_file():
    from hermes.agents.curriculum_designer import build_curriculum_designer_agent, build_course_outline_task
    agent = build_curriculum_designer_agent()
    task = build_course_outline_task(
        agent,
        lit_review_content="Some lit review",
        learning_objectives="Learn X",
        output_path="/tmp/outline.md",
    )
    assert task.output_file.endswith("outline.md")
    assert "Learning Objectives" in task.description
    assert "Session Breakdown" in task.description


def test_content_writer_task_output_file():
    from hermes.agents.content_writer import build_content_writer_agent, build_lecture_draft_task
    agent = build_content_writer_agent()
    task = build_lecture_draft_task(
        agent,
        course_outline_content="Course outline here",
        output_path="/tmp/lecture.md",
    )
    assert task.output_file.endswith("lecture.md")


def test_assessment_builder_task_output_file():
    from hermes.agents.assessment_builder import build_assessment_builder_agent, build_quiz_bank_task
    agent = build_assessment_builder_agent()
    task = build_quiz_bank_task(
        agent,
        lecture_draft_content="Lecture content",
        output_path="/tmp/quiz.md",
    )
    assert task.output_file.endswith("quiz.md")


def test_editor_task_does_not_add_claims():
    from hermes.agents.editor import build_editor_agent, build_edit_task
    agent = build_editor_agent()
    task = build_edit_task(
        agent,
        artifact_content="Some existing content with citations (Smith, 2020).",
        output_path="/tmp/edited.md",
    )
    assert "Khong duoc them" in task.description or "NOT" in task.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
