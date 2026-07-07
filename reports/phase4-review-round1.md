# Phase 4 — Báo cáo Review Round 1

**Ngày:** 2026-07-06
**Commit:** `eb6e0f4`
**Test:** 97/97 pass (87 cũ + 10 mới)

---

## 1. Root cause bug dashboard + fix

### Diagnostic output

```
=== Artifact Index (list_artifacts) ===
  lit-01_v1: type=lit_review_md status=pass
  outline-01_v1: type=course_outline status=pass
  lecture-01_v1: type=lecture_draft status=escalated
  quiz-01_v1: type=quiz_bank status=escalated

=== verification_result events ===
  lit-01 v1: pass (score=0.95)
  outline-01 v1: pass (score=0.85)
  lecture-01 v1: escalated (score=0.9)
  quiz-01 v1: escalated (score=0.88)

=== Dashboard counting logic ===
  verif_events count: 4
  pass_count: 2
  fail_count: 0
  escalated_count: 2

  escalated_artifacts (from index): 2
```

### Root cause: 3 bugs

**Bug 1 — "Tasks" line vô nghĩa**: `total_tasks` đếm từ task events (luôn = 0 vì không có event `task_created` nào được emit), nhưng breakdown `(pass_count verified, escalated_count escalated, fail_count failed)` lấy từ `verification_result` events — 2 nguồn dữ liệu khác nhau bị trộn vào 1 dòng.

**Bug 2 — Labels sai**: Format string `({pass_count} verified, {escalated_count} failed, {fail_count} failed)` có **2 chữ "failed"**.

**Bug 3 — 2 nguồn dữ liệu cho cùng 1 khái niệm**: Verification line đếm từ events, nhưng danh sách "Đang chờ duyệt" đếm từ artifact index. Nếu 1 artifact có nhiều version/event, 2 con số sẽ lệch nhau.

### Fix: Single source of truth

Sửa `cmd_dashboard()` trong `hermes/__main__.py`:

- **Bỏ dòng Tasks** (hệ thống chưa có Task Store thật)
- **Đếm tất cả artifact-level stats từ `list_artifacts(workspace)`** — cùng 1 nguồn với danh sách escalated bên dưới → luôn khớp
- **Debate stats vẫn từ events** (không có trong index)
- **Format labels đúng**: `(A pass, B fail, C escalated)`

### Test bổ sung: `test_dashboard_counts_are_internally_consistent`

Test tạo 5 artifact (2 pass, 1 fail, 2 escalated), chạy dashboard, assert:
- `pass + fail + escalated == total`
- Mỗi số trong summary khớp với output dashboard
- `escalated_count == len(danh_sách_chờ_duyệt)` (đếm "— chờ" trong output)

### Dashboard output sau fix

```
=== Hermes Dashboard ===
Artifacts:    4 versions across 4 types (2 pass, 0 fail, 2 escalated)
Debates:      2 resolved (1 consensus_pass, 0 consensus_fail, 1 no_consensus)

Đang chờ duyệt (escalated):
  lecture-01 (lecture_draft, v1) — chờ 0.0 giờ
  quiz-01 (quiz_bank, v1) — chờ 0.0 giờ
```

✅ 2 escalated trong summary = 2 artifact trong danh sách
✅ `2+0+2` = 4 total

---

## 2. "Tasks" trong dashboard phản ánh nguồn gì?

**Trả lời:** Hệ thống có `workspace.task_dir` + `tasks/index.json` (tạo bởi `ensure_initialized()`) nhưng **không có code nào ghi task thật** — pipeline chỉ tạo artifact qua `run_stage()`. Không event `task_created`/`task_status_changed` nào được emit. Dashboard cũ hiển thị sai: dùng artifact verification counts gắn nhãn "Tasks". **Đã bỏ dòng Tasks khỏi dashboard**, chỉ hiển thị artifact-level data.

---

## 3. Nội dung `docs/OPERATIONS.md` — mục 1 và 2

### Mục 1: Cách thêm subagent mới (tóm tắt)

1. Tạo file `hermes/agents/<ten>.py` theo pattern `build_<ten>_agent()` + `build_<ten>_task()` (mẫu: `editor.py`)
2. Nếu tạo artifact type mới:
   - Thêm vào `schemas/artifact.schema.json` enum
   - Tạo rubric `hermes/rubrics/R-<type>-v1.json`
   - Đăng ký checker `@checker_for("<type>")` trong `verifier.py`
   - **⚠️ Đăng ký vào `RISK_MATRIX`** trong `risk.py` — nếu quên, test `test_all_artifact_types_have_risk_level` fail
   - Cân nhắc `HUMAN_GATE_TYPES` nếu type high/critical
3. Nối vào pipeline qua `run_stage()`
4. Viết test tối thiểu

### Mục 2: Cách thêm rubric mới (tóm tắt)

1. Tạo file `R-<type>-v1.json` với `id`, `artifact_type`, `pass_threshold`, `criteria[]`
2. Đăng ký trong `load_rubric()` — glob fallback tự nhận nếu đặt tên đúng pattern
3. Thêm checker vào `CHECKER_REGISTRY`
4. **⚠️ Viết guard test** `test_rubric_criteria_names_match_verifier_<type>` — tên tiêu chí trong JSON và code chấm điểm phải khớp chính xác (bài học Phase 1 mục 6.3)

Nội dung đầy đủ: `docs/OPERATIONS.md` (298 lines).

---

## 4. Git status

```
$ git log --oneline -3
eb6e0f4 feat(phase4): observability layer — events, dashboard, check-stale, OPERATIONS.md
1b25ffe chore(phase4): safety snapshot before Phase 4 observability
c553e37 test(phase3): add debate_verdict persistence test

$ git status --short
(không có gì — working tree clean)
```

---

## 5. Log pytest -v

```
========================= 97 passed, 83 warnings in 11.57s =========================

87 tests cũ (Phase 0-3) + 10 tests mới (Phase 4) = 97

Tests Phase 4 (10):
  test_log_event_rejects_unknown_type
  test_log_event_appends_not_overwrites
  test_finalize_verification_emits_verification_result_event
  test_save_artifact_emits_artifact_version_created_event
  test_dashboard_command_runs_and_prints_summary
  test_dashboard_counts_are_internally_consistent        ← mới (round 1)
  test_check_stale_flags_artifact_past_threshold
  test_check_stale_ignores_non_escalated_artifacts
  test_check_stale_exit_code_nonzero_when_stale_found
  test_check_stale_reads_timestamp_from_event_log_not_new_field
```

---

## Tổng kết thay đổi round 1

| File | Thay đổi |
|------|----------|
| `hermes/__main__.py` | Fix `cmd_dashboard`: single source of truth từ artifact index, bỏ Tasks line, fix labels |
| `tests/test_phase4_observability.py` | Sửa test 5 (không assert Tasks/Verification), thêm test 6 (internal consistency) |
| `docs/OPERATIONS.md` | Đã có từ trước (298 dòng, 6 mục) |
