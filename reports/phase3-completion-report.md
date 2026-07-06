# Hermes Engineering OS — Phase 3 Completion Report

**Date:** 2026-07-06
**Status:** ✅ HOÀN TẤT
**Commit:** `e5f9774`
**Tests:** 86/86 pass

---

## 1. Tổng quan

Phase 3 triển khai thành công **Ma trận rủi ro tự động** và **Debate Review Agent** cho Hermes Engineering OS. Toàn bộ thay đổi nằm trong `finalize_verification()` (single source of truth), không thêm if/else rải rác ở pipeline hay agent.

### Commit history

```
e5f9774 fix(phase3): persist debate_verdict to Artifact Store + 3 standalone tests
62b979b feat(phase3): risk matrix + debate review agent
7d47254 chore(phase3): snapshot before Phase 3
c2637f5 chore(phase2): add baseline measurements
```

---

## 2. Kết quả test (86/86 pass)

```
tests/test_phase0.py — 11 passed
tests/test_phase1.py — 10 passed
tests/test_phase2.py — 24 passed
tests/test_phase2_human_gate.py — 6 passed
tests/test_phase3_risk.py — 16 passed
tests/test_phase3_debate.py — 19 passed
======================= 86 passed in 13.47s =======================
```

---

## 3. File thay đổi

### File mới (10)

| File | Vai trò |
|---|---|
| `hermes/core/risk.py` | Ma trận rủi ro + `SKIP_DEBATE_TYPES` + `should_trigger_debate()` |
| `hermes/agents/debate_proponent.py` | CrewAI Agent — bảo vệ artifact |
| `hermes/agents/debate_opponent.py` | CrewAI Agent — phản biện artifact |
| `hermes/pipeline/debate_review_task.py` | Loop debate (max 3 rounds) + `judge_consensus()` pure function |
| `hermes/rubrics/R-debate-verdict-v1.json` | Rubric cho debate_verdict (threshold 0.9) |
| `tests/test_phase3_risk.py` | 16 tests cho ma trận rủi ro |
| `tests/test_phase3_debate.py` | 19 tests cho debate agent + pipeline |
| `run_debate_real.py` | Script tái lập debate thật qua LLM |
| `check_bug.py` | Script chẩn đoán bug (đã migrate thành test tự động) |
| 3 báo cáo `.md` trong `reports/` | Báo cáo Phase 3 + 2 follow-up |

### File sửa (5)

| File | Thay đổi |
|---|---|
| `hermes/core/verifier.py` | Tích hợp risk matrix vào `finalize_verification()`; thêm `check_debate_verdict`; `_build_result` nhận `extra`; xử lý `final_decision` cho debate_verdict standalone |
| `hermes/pipeline/full_lecture_pipeline.py` | `_maybe_run_debate()` helper; persist verdict vào store; gọi từ attempt 1 + retry |
| `hermes/pipeline/debate_review_task.py` | Guard `SKIP_DEBATE_TYPES` |
| `schemas/artifact.schema.json` | Thêm `debate_verdict` |
| `schemas/task.schema.json` | Thêm subagent debate + `max_rounds` |

---

## 4. Ma trận rủi ro

### RISK_MATRIX (7 types)

| Artifact Type | Risk |
|---|---|
| `lit_review_md` | low |
| `verified_content` | low |
| `course_outline` | medium |
| `final_content` | medium |
| `lecture_draft` | **high** |
| `quiz_bank` | **high** |
| `debate_verdict` | **critical** |

### RISK_ADJUSTED_FLOOR

| Risk Level | Floor |
|---|---|
| low | 0.0 |
| medium | 0.0 |
| **high** | **0.85** |
| **critical** | **0.90** |

- Unknown type → `"medium"` (không `"low"`)
- `effective_threshold = max(rubric_base, floor)` — chỉ nâng, không hạ

---

## 5. Debate Review Agent

### Kiến trúc

```
hermes/agents/debate_proponent.py   → bảo vệ artifact
hermes/agents/debate_opponent.py    → phản biện artifact
hermes/pipeline/debate_review_task.py → loop 3 rounds + judge_consensus()
```

### judge_consensus() — PURE FUNCTION

Không gọi LLM, không network. Pattern matching trên text argument:

- Opponent: "không có lỗi", "no errors found", "i agree" → `consensus_pass`
- Proponent: "thừa nhận sai sót", "i concede", "không thể bảo vệ" → `consensus_fail`
- Mặc định → `continue`

### Kích hoạt

- Chỉ khi `risk_level ∈ {high, critical}` **VÀ** `rubric_pass = True`
- `debate_verdict` nằm trong `SKIP_DEBATE_TYPES` → không tự kích hoạt đệ quy
- `no_consensus` → `escalated` (người duyệt)
- `consensus_fail` → `fail` (bác bỏ học thuật)
- `consensus_pass` + human gate → `escalated`

### Persist vào Artifact Store

`_maybe_run_debate()` lưu `debate_verdict` dưới dạng artifact có version, với metadata `target_artifact_id`/`target_artifact_version`. Người duyệt có thể xem toàn bộ lập luận proponent/opponent khi approve artifact bị escalate.

### Chạy thật qua LLM

Đã chạy thành công với `HERMES_LLM_PROVIDER=opencode_go`, `deepseek-v4-flash`. Kết quả:

```json
{
  "final_decision": "no_consensus",
  "rounds": [{
    "round": 1,
    "proponent_argument": "Lập luận bảo vệ...",
    "opponent_argument": "Phản biện chỉ ra 5 lỗi: citation sai năm, RL thiếu MDP, nhập nhằng ML/AI..."
  }]
}
```

---

## 6. Các bug đã phát hiện & sửa trong quá trình review

| Bug | Phát hiện | Fix |
|---|---|---|
| `debate_verdict` no_consensus → fail (đáng lẽ escalated) | Review vòng 2 | `finalize_verification()` check `final_decision` từ checker |
| `debate_verdict` không persist vào store | Review vòng 3 | `_maybe_run_debate()` gọi `save_artifact()` |
| Code lặp ở attempt 1 & retry path | Review vòng 2 | Refactor `_maybe_run_debate()` helper |
| Thiếu test tự động cho fix | Review vòng 3 | 3 test `standalone_*` |

---

## 7. Việc KHÔNG làm (đúng hướng dẫn)

- Không đổi CrewAI — debate dùng CrewAI local crew
- Không sửa `R-quiz-bank-v1.json` — giữ nguyên threshold 0.8
- Không động `local_cx` provider
- Không đếm token bằng tiktoken

---

## 8. Checklist bàn giao

- [x] Ma trận rủi ro: `risk.py` + tích hợp `finalize_verification()`
- [x] Debate Review Agent: agents + pipeline + schema + rubric
- [x] `judge_consensus()` pure function — test được không cần mock CrewAI
- [x] Guard chống đệ quy `debate_verdict` (double guard)
- [x] Pipeline tự động gọi debate cho high/critical artifacts
- [x] `debate_verdict` persist vào Artifact Store
- [x] Debate thật chạy qua LLM (`opencode_go`)
- [x] `no_consensus` → `escalated` (không fail, không retry)
- [x] 86/86 tests pass, không regression Phase 0-2
- [x] Commit snapshot `7d47254` → hoàn chỉnh `e5f9774`

---

**Chờ reviewer hướng dẫn tiếp.**
