"""
Smoke test end-to-end thủ công cho Hermes Phase 0.

Mô phỏng vòng đời Task -> Artifact -> Verification (fail -> rejected)
bằng dữ liệu giả, không gọi LLM hay CrewAI Agent.
"""

from core.validator import validate_task, validate_artifact
from core.state_machine import transition
from core.storage import save_artifact, update_verification


def main():
    task = {
        "task_id": "T-20260705-001",
        "type": "literature_review",
        "assigned_subagent": "researcher",
        "input_refs": [],
        "instructions": "Test task giả lập Phase 0",
        "output_schema": {
            "artifact_type": "lit_review_md",
            "required_fields": ["summary"],
        },
        "verification": {
            "method": "rubric",
            "rubric_id": "R-lit-review-v2",
            "min_score": 0.8,
        },
        "status": "pending",
        "retry_count": 0,
        "max_retries": 2,
    }

    validate_task(task)
    print(f"[OK] Task {task['task_id']} validated")

    task = transition(task, "in_progress")
    print(f"[OK] Task transitioned to {task['status']}")

    artifact = save_artifact(
        artifact_id="A-0001",
        content="# Test lit review\n\nĐây là nội dung giả lập.",
        artifact_type="lit_review_md",
        produced_by_task=task["task_id"],
        metadata={"word_count": 12, "sources": 0, "subagent": "researcher"},
    )
    validate_artifact(artifact)
    print(f"[OK] Artifact {artifact['artifact_id']} v{artifact['version']} saved & validated")

    # Giả lập verifier chấm fail để test luồng retry
    update_verification("A-0001", 1, "fail", "Thiếu trích dẫn -- test giả lập")
    task = transition(task, "rejected")
    print(f"[OK] Artifact marked fail, Task transitioned to {task['status']}")

    print("\nPhase 0 smoke test: OK")


if __name__ == "__main__":
    main()
