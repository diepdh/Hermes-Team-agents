"""
JSON Schema validator cho Task, Artifact và Rubric trong Hermes Phase 0.5.

Schema được load từ thư mục cài đặt code (gần file này), không phụ thuộc
vào workspace hiện hành để có thể dùng chung cho mọi workspace.
"""

import json
import pathlib
from jsonschema import validate, ValidationError

_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
_SCHEMA_DIR = _BASE_DIR / "schemas"


def _load_schema(name: str) -> dict:
    path = _SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


_TASK_SCHEMA = _load_schema("task.schema.json")
_ARTIFACT_SCHEMA = _load_schema("artifact.schema.json")
_RUBRIC_SCHEMA = _load_schema("rubric.schema.json")


def validate_task(task: dict) -> None:
    """Validate một Task theo task.schema.json."""
    validate(instance=task, schema=_TASK_SCHEMA)


def validate_artifact(artifact: dict) -> None:
    """Validate một Artifact theo artifact.schema.json."""
    validate(instance=artifact, schema=_ARTIFACT_SCHEMA)


def validate_rubric(rubric: dict) -> None:
    """Validate một Rubric theo rubric.schema.json."""
    validate(instance=rubric, schema=_RUBRIC_SCHEMA)


def is_valid_task(task: dict) -> bool:
    try:
        validate_task(task)
        return True
    except ValidationError:
        return False


def is_valid_artifact(artifact: dict) -> bool:
    try:
        validate_artifact(artifact)
        return True
    except ValidationError:
        return False
