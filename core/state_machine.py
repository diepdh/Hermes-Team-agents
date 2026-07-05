"""
Task State Machine cho Hermes Phase 0.

Các trạng thái hợp lệ:
    pending -> in_progress
    in_progress -> verified | rejected | escalated
    rejected -> pending
    escalated -> verified | rejected
    verified -> (terminal)
"""

VALID_TRANSITIONS = {
    "pending": ["in_progress"],
    "in_progress": ["verified", "rejected", "escalated"],
    "rejected": ["pending"],
    "escalated": ["verified", "rejected"],
    "verified": [],
}


def transition(task: dict, new_status: str) -> dict:
    """
    Chuyển trạng thái task. Raise ValueError nếu transition không hợp lệ.
    """
    current = task["status"]
    if new_status not in VALID_TRANSITIONS.get(current, []):
        raise ValueError(
            f"Không thể chuyển Task {task['task_id']} "
            f"từ '{current}' sang '{new_status}'"
        )
    task["status"] = new_status
    return task


def can_transition(task: dict, new_status: str) -> bool:
    """Kiểm tra xem một transition có được phép không."""
    return new_status in VALID_TRANSITIONS.get(task["status"], [])
