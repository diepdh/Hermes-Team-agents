"""
Task index CRUD theo workspace pattern cho Hermes Phase 0.5.

Mỗi workspace có task index riêng tại .hermes/tasks/index.json.
"""

import json
from datetime import datetime, timezone

from core.workspace import Workspace


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_task(workspace: Workspace, task: dict) -> dict:
    """Lưu hoặc cập nhật task trong workspace."""
    workspace.ensure_initialized()
    index_path = workspace.task_index_path
    index = _load(index_path)
    task_id = task["task_id"]
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    index[task_id] = task
    _save(index_path, index)
    return task


def get_task(workspace: Workspace, task_id: str) -> dict | None:
    """Lấy task theo id trong workspace."""
    workspace.ensure_initialized()
    index = _load(workspace.task_index_path)
    return index.get(task_id)


def list_tasks(workspace: Workspace) -> dict:
    """Trả về toàn bộ task index trong workspace."""
    workspace.ensure_initialized()
    return _load(workspace.task_index_path)


def delete_task(workspace: Workspace, task_id: str) -> None:
    """Xóa task khỏi workspace."""
    workspace.ensure_initialized()
    index_path = workspace.task_index_path
    index = _load(index_path)
    if task_id in index:
        del index[task_id]
        _save(index_path, index)
