"""
Artifact Store tối giản cho Hermes Phase 0.

Cung cấp CRUD + versioning cho artifact lưu trên filesystem,
cùng file index JSON để truy vết metadata.
"""

import json
import pathlib
from datetime import datetime, timezone

ARTIFACT_DIR = pathlib.Path("artifacts")
INDEX_PATH = ARTIFACT_DIR / "index.json"


def _load_index() -> dict:
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _save_index(index: dict) -> None:
    INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_artifact(
    artifact_id: str,
    content: str,
    artifact_type: str,
    produced_by_task: str,
    metadata: dict | None = None,
    parent_artifact_id: str | None = None,
) -> dict:
    """
    Lưu artifact mới. Nếu artifact_id đã tồn tại, tạo version tiếp theo
    thay vì ghi đè.
    """
    index = _load_index()
    existing_versions = [
        v for k, v in index.items() if v["artifact_id"] == artifact_id
    ]
    version = len(existing_versions) + 1
    file_path = ARTIFACT_DIR / f"{artifact_id}_v{version}.md"
    file_path.write_text(content, encoding="utf-8")

    record = {
        "artifact_id": artifact_id,
        "produced_by_task": produced_by_task,
        "type": artifact_type,
        "version": version,
        "content_ref": str(file_path),
        "metadata": metadata or {},
        "verification_status": "pending",
        "verification_notes": "",
        "parent_artifact_id": parent_artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    index[f"{artifact_id}_v{version}"] = record
    _save_index(index)
    return record


def get_artifact(artifact_id: str, version: int | None = None) -> dict | None:
    """
    Lấy artifact theo id. Nếu không truyền version, trả về bản mới nhất.
    """
    index = _load_index()
    if version:
        return index.get(f"{artifact_id}_v{version}")
    matches = [v for k, v in index.items() if v["artifact_id"] == artifact_id]
    return max(matches, key=lambda x: x["version"]) if matches else None


def update_verification(
    artifact_id: str, version: int, status: str, notes: str = ""
) -> None:
    """
    Cập nhật trạng thái verification của một artifact cụ thể.
    """
    if status not in ("pending", "pass", "fail"):
        raise ValueError(f"Trạng thái verification không hợp lệ: {status}")
    index = _load_index()
    key = f"{artifact_id}_v{version}"
    if key not in index:
        raise KeyError(f"Artifact {key} không tồn tại")
    index[key]["verification_status"] = status
    index[key]["verification_notes"] = notes
    _save_index(index)


def list_artifacts() -> dict:
    """Trả về toàn bộ index."""
    return _load_index()
