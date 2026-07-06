"""Run Phase 1 baseline with opencode_go and persist metrics."""
import json
from pathlib import Path
from hermes.pipeline.lit_review_pipeline import run_lit_review_with_baseline

questions = [
    "Cac phuong phap danh gia nang luc tu hoc cua sinh vien dai hoc la gi?",
    "Tac dong cua phan hoi tuc thoi (immediate feedback) den ket qua hoc tap?",
    "So sanh mo hinh lop hoc dao nguoc (flipped classroom) voi mo hinh truyen thong?",
]

rubric = {
    "name": "Literature Review Rubric",
    "pass_threshold": 0.7,
    "criteria": [
        {"name": "citation_completeness", "weight": 0.35, "check": "At least 3 APA-style citations"},
        {"name": "relevance_summary", "weight": 0.25, "check": "Summary answers the research question"},
        {"name": "gaps_section", "weight": 0.20, "check": "Explicit Gaps Identified section"},
        {"name": "formatting_clarity", "weight": 0.20, "check": "Markdown headers and clear structure"},
    ]
}

workspace = "workspace_phase1_baseline"
Path(workspace).mkdir(exist_ok=True)

for i, q in enumerate(questions, 1):
    print(f"\n=== Run {i}: {q[:60]}... ===")
    result = run_lit_review_with_baseline(
        workspace_root=workspace,
        research_question=q,
        task_id=f"T1-run{i}",
        artifact_id=f"A1-run{i}",
        rubric=rubric,
        run_id=f"run-{i}",
        provider="opencode_go",
        max_retries=2,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

print("\n=== Baseline file ===")
print(Path(workspace, ".hermes", "logs", "phase1_baseline.json").read_text(encoding="utf-8"))
