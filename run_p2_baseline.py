"""Phase 2 baseline runner — runs full lecture pipeline 2-3 times and saves results."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from hermes.core.workspace import Workspace
from hermes.pipeline.full_lecture_pipeline import run_full_lecture_pipeline

RUNS = [
    {
        "run_id": "p2-run-1",
        "research_question": "Các phương pháp đánh giá năng lực tự học của sinh viên đại học là gì?",
        "learning_objectives": "Hiểu các mô hình tự học; Phân tích công cụ đánh giá; Thiết kế rubric",
    },
    {
        "run_id": "p2-run-2",
        "research_question": "Tác động của phản hồi tức thời (immediate feedback) đến kết quả học tập?",
        "learning_objectives": "Phân biệt các loại phản hồi; Đánh giá hiệu quả immediate feedback",
    },
    {
        "run_id": "p2-run-3",
        "research_question": "So sánh mô hình lớp học đảo ngược (flipped classroom) với mô hình truyền thống?",
        "learning_objectives": "Mô tả flipped classroom; So sánh ưu nhược điểm hai mô hình",
    },
]

results = {"runs": []}

for cfg in RUNS:
    ws_root = Path(f"/tmp/hermes_p2_{cfg['run_id']}")
    ws_root.mkdir(parents=True, exist_ok=True)

    ws = Workspace(str(ws_root))
    ws.ensure_initialized()

    print(f"\n=== {cfg['run_id']}: {cfg['research_question'][:60]}... ===")
    t0 = time.time()

    try:
        summary = run_full_lecture_pipeline(
            workspace_root=str(ws_root),
            research_question=cfg["research_question"],
            learning_objectives=cfg["learning_objectives"],
        )
        elapsed = round(time.time() - t0, 1)
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        summary = {"error": str(e)}

    run_result = {
        "run_id": cfg["run_id"],
        "research_question": cfg["research_question"],
        "elapsed_seconds": elapsed,
        "summary": summary,
    }
    results["runs"].append(run_result)
    print(f"  Elapsed: {elapsed}s, Summary: {summary}")

results["avg_elapsed_seconds"] = (
    round(sum(r["elapsed_seconds"] for r in results["runs"]) / len(results["runs"]), 1)
    if results["runs"]
    else 0
)
results["timestamp"] = datetime.now(timezone.utc).isoformat()

log_path = Path("logs/phase2_baseline.json")
log_path.parent.mkdir(parents=True, exist_ok=True)
log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved to {log_path}")
print(json.dumps(results, indent=2, ensure_ascii=False))
