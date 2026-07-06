"""
Artifact Store cho Hermes Phase 0.5.

Mọi hàm CRUD đều nhận workspace: Workspace làm tham số đầu tiên.
Dữ liệu artifact được lưu trong workspace do người dùng chỉ định,
code lõi của Hermes không phụ thuộc vào vị trí cài đặt.

content_ref được lưu dưới dạng path tương đối so với workspace root
để workspace có thể di chuyển sang máy/ổ đĩa khác mà vẫn đọc đúng.
"""

import json
from datetime import datetime, timezone

from .workspace import Workspace


def _load_index(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save_index(path, index):
    path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def save_artifact(
    workspace: Workspace,
    artifact_id: str,
    content: str,
    artifact_type: str,
    produced_by_task: str,
    metadata: dict | None = None,
    parent_artifact_id: str | None = None,
) -> dict:
    """Lưu artifact mới vào workspace. Tự động tăng version, không ghi đè."""
    workspace.ensure_initialized()
    index_path = workspace.artifact_index_path
    index = _load_index(index_path)

    existing_versions = [
        v for v in index.values() if v["artifact_id"] == artifact_id
    ]
    version = len(existing_versions) + 1
    file_path = workspace.artifact_dir / f"{artifact_id}_v{version}.md"
    file_path.write_text(content, encoding="utf-8")

    record = {
        "artifact_id": artifact_id,
        "produced_by_task": produced_by_task,
        "type": artifact_type,
        "version": version,
        "content_ref": workspace.relative(file_path).as_posix(),
        "metadata": metadata or {},
        "verification_status": "pending",
        "verification_notes": "",
        "parent_artifact_id": parent_artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    index[f"{artifact_id}_v{version}"] = record
    _save_index(index_path, index)
    return record


def get_artifact(workspace: Workspace, artifact_id: str, version: int | None = None) -> dict | None:
    """Lấy artifact theo id. Nếu không truyền version, trả về bản mới nhất."""
    workspace.ensure_initialized()
    index = _load_index(workspace.artifact_index_path)
    if version:
        return index.get(f"{artifact_id}_v{version}")
    matches = [v for v in index.values() if v["artifact_id"] == artifact_id]
    return max(matches, key=lambda x: x["version"]) if matches else None


def update_verification(
    workspace: Workspace,
    artifact_id: str,
    version: int,
    status: str,
    notes: str = "",
) -> None:
    """Cập nhật trạng thái verification của artifact."""
    if status not in ("pending", "pass", "fail"):
        raise ValueError(f"Trạng thái verification không hợp lệ: {status}")

    workspace.ensure_initialized()
    index_path = workspace.artifact_index_path
    index = _load_index(index_path)
    key = f"{artifact_id}_v{version}"
    if key not in index:
        raise KeyError(f"Artifact {key} không tồn tại trong workspace {workspace.root}")
    index[key]["verification_status"] = status
    index[key]["verification_notes"] = notes
    _save_index(index_path, index)


def list_artifacts(workspace: Workspace) -> dict:
    """Trả về toàn bộ artifact index trong workspace."""
    workspace.ensure_initialized()
    return _load_index(workspace.artifact_index_path)


def read_artifact_content(workspace: Workspace, artifact_record: dict) -> str:
    """
    Đọc nội dung artifact từ content_ref (tương đối so với workspace root).
    """
    workspace.ensure_initialized()
    content_path = workspace.root / artifact_record["content_ref"]
    return content_path.read_text(encoding="utf-8")
