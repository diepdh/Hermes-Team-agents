# Hermes Phase 1 — Hướng dẫn triển khai

**Nguồn:** Hermes Engineering OS — Phase 1 implementation guide  
**Phiên bản:** 1.0  
**Ngày:** 05/07/2026

---

## Mục tiêu

Triển khai Phase 1 prototype: một crew nghiên cứu tài liệu học thuật (literature review) sử dụng CrewAI, với verification dựa trên rubric và retry logic.

---

## 13 mục checklist triển khai

| # | Hạng mục | Mô tả |
|---|---|---|
| 0 | `.env` cấu hình đúng, không lộ key vào git | File `.env` chứa API key không được commit. `OPENCODE_BASE_URL` không chứa `/chat/completions`. |
| 1 | `requirements.txt` đã tạo, cài được trên venv mới | `pip install -r requirements.txt` từ đầu trên venv sạch phải thành công. |
| 2 | Researcher Agent tạo artifact thật qua LLM | Agent gọi API thật và sinh ra file `.md` trong workspace artifact dir. |
| 3 | Verifier rule-based chấm đúng cả case pass và fail | `check_lit_review()` trả về `passed=True` với artifact tốt, `passed=False` với artifact thiếu. |
| 4 | Pipeline nối đúng Task→Artifact→Verify | `run_lit_review_pipeline()` điều phối đúng thứ tự researcher → file → verifier. |
| 5 | Retry hoạt động đúng, có ghi chú lỗi đưa vào lần sau | Khi fail, pipeline ghi log và tạo artifact version mới với feedback. |
| 6 | Retry dừng đúng ở `max_retries`, không lặp vô hạn | Pipeline không vượt quá số lần retry đã định. |
| 7 | Artifact versioning giữ đủ lịch sử qua các lần retry | Mỗi attempt tạo file `_v{N}.md` mới, không ghi đè. |
| 8 | Baseline token/thời gian đã đo với ≥3 lần chạy thật | `logs/phase1_baseline.json` ghi lại elapsed_seconds và retries cho ≥3 lần chạy. |
| 9 | 4 mục housekeeping tồn từ Phase 0.5 đã xử lý hoặc có lý do rõ ràng | Xem mục housekeeping bên dưới. |
| 10 | Toàn bộ unit test cũ (Phase 0 + 0.5) vẫn pass sau khi thêm code Phase 1 | `pytest` toàn bộ suite phải pass không regression. |
| 11 | Đã commit git với message rõ ràng | Mỗi phase/bộ feature commit riêng, message có tiền tố `feat/`, `fix/`, `test/`, `chore/`. |
| 12 | CrewAI cài đúng trên venv sẽ dùng cho Phase 1 trở đi | `crewai==1.15.1` được pin cứng trong requirements.txt. |

---

## Housekeeping Phase 0.5

4 việc cần xử lý trước khi đóng Phase 1:

1. **Dọn `artifacts/`/`tasks/` root cũ** — xóa thư mục rác từ trước khi có `Workspace`.
2. **Xác nhận nguồn gốc `hermes-agent`** — `hermes-agent` không có trong `requirements.txt`, không phải dependency của project này. Đây là package từ Hermes Agent (ứng dụng desktop đang chạy Coder Agent), không liên quan đến Hermes Engineering OS.
3. **Xác nhận version `pytest`** — `pytest==9.1.1` được ghi trong requirements.txt.
4. **Sửa lỗi hiển thị `\r`** — khi chạy trên Windows qua bash (git-bash/MSYS), output CLI có thể chứa `\r`. Khắc phục bằng cách dùng đúng newline handling của Python/pytest trên Windows.

---

## Cấu trúc thư mục

```
hermes/
├── agents/           # Researcher, Editor, Content Writer, Assessment Builder, Curriculum Designer
├── core/            # Workspace, Storage, TaskIndex, Validator, LLM Config, Verifier
├── pipeline/        # LitReviewPipeline, FlowOrchestrator
├── rubrics/         # Rubric JSON files
├── schemas/         # JSON Schema for Task, Artifact, Rubric
├── tests/           # test_phase0.py, test_phase1.py
├── docs/            # Phase guides
├── workspace_*/     # Ephemeral workspaces per run
└── .env             # API keys (NOT in git)
```

---

## Tiến độ các phase

- **Phase 0:** Storage + Workspace (local JSON, portable)
- **Phase 0.5:** TaskIndex + Validator + JSON Schema
- **Phase 1:** Researcher Agent + Verifier + Pipeline + Baseline ← ĐANG LÀM
- **Phase 2:** 4 subagent còn lại (Curriculum Designer, Content Writer, Assessment Builder, Editor)
- **Phase 3:** Production pipeline orchestration
