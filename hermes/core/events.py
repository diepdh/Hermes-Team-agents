"""Append-only event log cho toàn bộ Task/Artifact/Verification lifecycle."""

import json
from datetime import datetime, timezone

from .workspace import Workspace

# ── Allowed event types ──────────────────────────────────────────────
EVENT_TYPES = {
    "task_created",
    "task_status_changed",
    "artifact_created",
    "artifact_version_created",
    "verification_result",        # pass / fail / escalated
    "debate_started",
    "debate_round_completed",
    "debate_resolved",
    "human_approval",
}


def log_event(workspace: Workspace, event_type: str, payload: dict) -> dict:
    """Ghi một sự kiện nghiệp vụ vào workspace event log (JSONL append-only).

    Args:
        workspace: Workspace instance.
        event_type: Một trong EVENT_TYPES.
        payload: Dict chứa dữ liệu riêng của sự kiện (artifact_id, status, ...).

    Returns:
        Dict event đã được ghi (có timestamp).

    Raises:
        ValueError: nếu event_type không nằm trong EVENT_TYPES.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event_type}")

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }

    workspace.ensure_initialized()
    log_path = workspace.log_dir / "events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def read_events(workspace: Workspace, event_type: str | None = None) -> list[dict]:
    """Đọc tất cả event từ workspace event log (JSONL).

    Args:
        workspace: Workspace instance.
        event_type: Nếu được truyền, chỉ trả về event có event_type này.

    Returns:
        List các dict event, sắp xếp theo thứ tự ghi.
    """
    log_path = workspace.log_dir / "events.jsonl"
    if not log_path.exists():
        return []

    events = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if event_type:
        events = [e for e in events if e["event_type"] == event_type]

    return events
