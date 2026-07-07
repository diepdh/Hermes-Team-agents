# Hermes Engineering OS — Phase 3 Review Round 2 Final Report

**Date:** 2026-07-06
**Responding to:** Reviewer round 2 feedback
**Test:** 83/83 pass

---

## Mục 1 — Làm rõ mâu thuẫn commit

```
$ git status
On branch master
Changes not staged for commit:
    modified:   hermes/core/risk.py
    modified:   hermes/core/verifier.py
    modified:   hermes/pipeline/debate_review_task.py
    modified:   hermes/pipeline/full_lecture_pipeline.py
    modified:   tests/test_phase3_debate.py
    modified:   tests/test_phase3_risk.py

Untracked files:
    reports/phase3-final-report.md
    reports/phase3-review-followup.md
    run_debate_real.py
    check_bug.py

$ git log --oneline -3
62b979b feat(phase3): risk matrix + debate review agent
7d47254 chore(phase3): snapshot before Phase 3
c2637f5 chore(phase2): add baseline measurements
```

**Kết luận:** `run_debate_real.py` là **untracked** — câu "đã commit" trong báo cáo follow-up là **sai**. Tất cả thay đổi follow-up đều chưa commit. Commit cuối cùng vẫn là `62b979b` (Phase 3 gốc).

---

## Mục 2a — Test pipeline end-to-end (ĐÃ CÓ)

### `test_pipeline_triggers_debate_for_high_risk_artifact_end_to_end` — PASS

Test mock `run_debate_review` (không mock `should_trigger_debate`), chạy `run_stage()` với `lecture_draft`, xác nhận:

1. `run_debate_review` được gọi đúng 1 lần với `artifact_id="pipeline-debate-test"`, `artifact_type="lecture_draft"`
2. Kết quả stage: `escalated=True` (consensus_pass + human gate)

### `test_pipeline_skips_debate_for_low_risk_artifact` — PASS

Test xác nhận `lit_review_md` (low risk) không trigger debate. `run_debate_review.assert_not_called()`.

---

## Mục 2b — Refactor retry path (ĐÃ LÀM)

Trích xuất `_maybe_run_debate()` helper:

```python
def _maybe_run_debate(workspace, artifact, artifact_type, content, result, rubric, provider, notes):
    if not (should_trigger_debate(artifact_type) and result["passed"]):
        return None
    debate_verdict = run_debate_review(...)
    return finalize_verification(..., debate_verdict=debate_verdict)
```

Gọi ở 2 nơi (attempt 1 và retry loop) với cùng 1 hàm — **một nguồn sự thật**.

---

## Mục 3 — Bug `debate_verdict` no_consensus (ĐÃ SỬA)

### Bằng chứng bug (trước fix)

```
$ python check_bug.py
verify_artifact: passed=False, score=0.5
detail: {"consensus_reached": 0.0, "rounds_completed": 1.0, "arguments_present": 1.0}
>>> finalize_verification status: 'fail' <<<
BUG: no_consensus → fail (should be escalated)
```

### Phân tích

- `consensus_reached=0.0` (vì `no_consensus`) × weight 0.5 = 0.0
- `rounds_completed=1.0` × 0.25 = 0.25
- `arguments_present=1.0` × 0.25 = 0.25
- **Score = 0.50**, effective_threshold = 0.90 → **fail**

Nhưng `no_consensus` nghĩa là "cần người quyết định", không phải "verdict sai".

### Trong pipeline hiện tại, bug KHÔNG trigger vì:

`run_stage()` truyền `debate_verdict` thẳng vào `finalize_verification()` làm tham số, không lưu verdict như artifact riêng. `finalize_verification()` dùng `debate_verdict["final_decision"]` để quyết định status của artifact GỐC (lecture_draft). Nhưng nếu ai đó lưu verdict như artifact độc lập rồi verify, bug sẽ xảy ra.

### Fix (2 thay đổi)

**1. `_build_result()` + `check_debate_verdict()`:** Trả về `final_decision` trong result:

```python
return _build_result(scores, rubric, extra={"final_decision": verdict.get("final_decision", "")})
```

**2. `finalize_verification()`:** Check `final_decision` khi verify debate_verdict standalone:

```python
verdict_decision = rubric_result.get("final_decision", "")
if artifact_type == "debate_verdict" and debate_verdict is None and verdict_decision:
    if verdict_decision == "no_consensus":
        status = "escalated"
    elif verdict_decision == "consensus_fail":
        status = "fail"  # academic rejection — no retry
    else:
        # consensus_pass — use normal rubric scoring
        ...
```

### Bằng chứng sau fix

```
$ python check_bug.py
>>> finalize_verification status: 'escalated' <<<
OK: no_consensus → escalated
```

---

## Mục 4 — Rubric `R-debate-verdict-v1.json` (đã dán)

```json
{
  "rubric_id": "R-debate-verdict-v1",
  "name": "Debate Verdict Rubric",
  "pass_threshold": 0.9,
  "criteria": [
    {"name": "consensus_reached", "weight": 0.5, "check": "final_decision is consensus_pass or consensus_fail"},
    {"name": "rounds_completed", "weight": 0.25, "check": "At least 1 round"},
    {"name": "arguments_present", "weight": 0.25, "check": "Arguments non-empty for all rounds"}
  ]
}
```

---

## Mục 5 — Tổng kết test (83/83 pass)

```
tests/test_phase0.py — 11 passed
tests/test_phase1.py — 10 passed
tests/test_phase2.py — 24 passed
tests/test_phase2_human_gate.py — 6 passed
tests/test_phase3_risk.py — 13 passed (9 gốc + 4 guard)
tests/test_phase3_debate.py — 19 passed (16 gốc + 2 pipeline + 1 guard)
======================= 83 passed, 83 warnings in 7.10s =======================
```

---

## Checklist hoàn chỉnh

- [x] **Mục 1:** Git status + git log — xác nhận untracked, chưa commit
- [x] **Mục 2a:** `test_pipeline_triggers_debate_for_high_risk_artifact_end_to_end` — PASS
- [x] **Mục 2b:** `_maybe_run_debate()` helper — refactored, single source of truth
- [x] **Mục 3:** Bug xác nhận + fix + chạy lại xác nhận escalated
- [x] **Mục 4:** Rubric JSON đã dán
- [x] **Mục 5:** Không cần làm lại (guard, pattern)
- [x] **Test:** 83/83 pass, số liệu khớp

---

**Chờ reviewer duyệt để commit chính thức đóng Phase 3.**
