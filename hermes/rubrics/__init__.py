"""
Rubric loader for Hermes Phase 2.

Provides `load_rubric(artifact_type)` which loads the rubric JSON file
matching the given artifact type (e.g. "lecture_draft", "quiz_bank").
Rubric files live in the same directory as this module.
"""

import json
from pathlib import Path

_RUBRIC_DIR = Path(__file__).parent

# Map artifact_type → rubric filename suffix
_TYPE_TO_FILE = {
    "lit_review": "R-lit-review-v2.json",
    "lit_review_md": "R-lit-review-v2.json",
    "source_analysis": "R-source-analysis-v1.json",
    "literature_support": "R-literature-support-v1.json",
    "paper_draft": "R-paper-draft-v1.json",
    "final_paper": "R-final-paper-v1.json",
    "existing_paper_assessment": "R-existing-paper-assessment-v1.json",
    "generated_data": "R-generated-data-v1.json",
    "course_outline": "R-course-outline-v1.json",
    "lecture_draft": "R-lecture-draft-v1.json",
    "quiz_bank": "R-quiz-bank-v1.json",
    "debate_verdict": "R-debate-verdict-v1.json",
}


def load_rubric(artifact_type: str) -> dict:
    """
    Load rubric dict for the given artifact type or rubric ID.

    Args:
        artifact_type: artifact type name (e.g. "lecture_draft") OR
                      rubric ID (e.g. "R-lecture-draft-v1").

    Returns:
        Rubric dict with rubric_id, name, pass_threshold, criteria.

    Raises:
        FileNotFoundError: if no rubric file exists for the given identifier.
    """
    # Try direct type mapping first
    filename = _TYPE_TO_FILE.get(artifact_type)
    if filename is None:
        # Try treating as full rubric ID — find by prefix in rubric dir
        for json_file in _RUBRIC_DIR.glob("R-*.json"):
            if json_file.stem == artifact_type:
                filename = json_file.name
                break
        if filename is None:
            raise FileNotFoundError(
                f"No rubric for artifact type or ID: {artifact_type}; "
                f"available: {list(_RUBRIC_DIR.glob('R-*.json'))}"
            )
    path = _RUBRIC_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)
