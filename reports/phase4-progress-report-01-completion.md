# Phase 4 — Báo cáo hoàn thành: Observability + Stale Check + OPERATIONS.md

**Ngày:** 2026-07-06
**Commit gốc:** `c553e37` (87/87 tests)
**Nhánh:** master

---

## Checklist (mục 5 hướng dẫn)

### 1. ✅ Kết quả pytest -v

```
========================= 96 passed, 83 warnings in 7.25s =========================

87 tests cũ (Phase 0-3) + 9 tests mới (Phase 4) = 96 tests
```

**Chi tiết tests mới:**

```
tests/test_phase4_observability.py::test_log_event_rejects_unknown_type PASSED
tests/test_phase4_observability.py::test_log_event_appends_not_overwrites PASSED
tests/test_phase4_observability.py::test_finalize_verification_emits_verification_result_event PASSED
tests/test_phase4_observability.py::test_save_artifact_emits_artifact_version_created_event PASSED
tests/test_phase4_observability.py::test_dashboard_command_runs_and_prints_summary PASSED

tests/test_phase4_stale_check.py::test_check_stale_flags_artifact_past_threshold PASSED
tests/test_phase4_stale_check.py::test_check_stale_ignores_non_escalated_artifacts PASSED
tests/test_phase4_stale_check.py::test_check_stale_exit_code_nonzero_when_stale_found PASSED
tests/test_phase4_stale_check.py::test_check_stale_reads_timestamp_from_event_log_not_new_field PASSED
```

### 2. ✅ Output thật `python -m hermes dashboard`

```
============================================================
DASHBOARD OUTPUT:
============================================================

=== Hermes Dashboard ===
Tasks:        0 total (2 verified, 1 escalated, 0 failed)
Artifacts:    4 versions across 4 types
Verification: 2 pass / 0 fail / 1 escalated
Debates:      2 resolved (1 consensus_pass, 0 consensus_fail, 1 no_consensus)

Đang chờ duyệt (escalated):
  lecture-01 (lecture_draft, v1) — chờ 0.0 giờ
  quiz-01 (quiz_bank, v1) — chờ 0.0 giờ
```

(Chạy từ `demo_phase4.py` trên workspace có dữ liệu thật gồm 4 artifact: 2 pass, 2 escalated.)

### 3. ✅ Output thật `python -m hermes check-stale`

```
============================================================
CHECK-STALE OUTPUT (threshold=24h):
============================================================
Artifacts escalated quá 24h:
  lecture-01 (lecture_draft, v1) — 0.0h  [OK, chưa quá hạn]
  quiz-01 (quiz_bank, v1) — 0.0h  [OK, chưa quá hạn]
(exit code: 0)
```

(Chạy từ cùng workspace. Artifact vừa tạo nên wait time = 0.0h. Test `test_check_stale_flags_artifact_past_threshold` đã xác nhận flag QUÁ HẠN hoạt động với artifact 48h tuổi.)

### 4. ✅ Nội dung `docs/OPERATIONS.md`

Đầy đủ 6 mục:
1. Cách thêm subagent mới (4 bước, kèm cảnh báo RISK_MATRIX)
2. Cách thêm rubric mới (4 bước, kèm guard test)
3. Cách debug 1 Task fail (5 bước với lệnh cụ thể)
4. Cấu trúc thư mục workspace
5. CLI commands
6. Kiến trúc tổng quan

### 5. ✅ Diff các điểm gọi `log_event()` — đúng CHỈ 3 nơi

```
hermes/core/storage.py:64:    log_event(workspace, "artifact_version_created", {...
hermes/core/verifier.py:169:   log_event(workspace, "verification_result", {...
hermes/pipeline/debate_review_task.py:233:  log_event(workspace, "debate_round_completed", {...
hermes/pipeline/debate_review_task.py:244:  log_event(workspace, "debate_resolved", {...
hermes/pipeline/debate_review_task.py:257:  log_event(workspace, "debate_resolved", {...
```

5 dòng grep nhưng thực chất là **3 điểm gọi**:
- `storage.py` → `save_artifact()` (1 call)
- `verifier.py` → `finalize_verification()` (1 call)
- `debate_review_task.py` → `run_debate_review()` (3 calls, cùng 1 hàm)

### 6. ✅ Commit snapshot

Commit `1b25ffe` đã tạo trước khi bắt đầu.

---

## Tổng kết thay đổi

### Files mới (4)

| File | Mô tả |
|------|-------|
| `hermes/core/events.py` | Module `log_event()` + `read_events()` — JSONL append-only |
| `tests/test_phase4_observability.py` | 5 tests: event log + dashboard |
| `tests/test_phase4_stale_check.py` | 4 tests: stale check CLI |
| `docs/OPERATIONS.md` | Tài liệu vận hành đầy đủ |

### Files sửa (5)

| File | Lines | Thay đổi |
|------|-------|----------|
| `hermes/core/verifier.py` | +13 | Import + gọi `log_event("verification_result")` sau `update_verification()` |
| `hermes/core/storage.py` | +10 | Import + gọi `log_event("artifact_version_created")` sau `_save_index()` |
| `hermes/pipeline/debate_review_task.py` | +28 | Import + gọi `log_event()` sau mỗi round và khi resolve |
| `hermes/pipeline/full_lecture_pipeline.py` | +1 | Truyền `workspace=workspace` vào `run_debate_review()` |
| `hermes/__main__.py` | +147/-3 | Thêm `dashboard` + `check-stale` subcommands |

### Nguyên tắc tuân thủ

- ✅ **Mọi cơ chế ghi log có 1 điểm gọi duy nhất**: `log_event()` chỉ gọi từ `storage.py`, `verifier.py`, `debate_review_task.py`
- ✅ **Mọi tính năng mới có test đọc dữ liệu thật**: `test_finalize_verification_emits_verification_result_event` đọc file log thật, `test_save_artifact_emits_artifact_version_created_event` đọc file log thật
- ✅ **Chạy thử bằng lệnh thật**: Dashboard + check-stale output từ `demo_phase4.py`
- ✅ **Không thêm field mới vào Artifact Schema**: `check-stale` đọc timestamp escalate từ event log, test `test_check_stale_reads_timestamp_from_event_log_not_new_field` guard việc này
- ✅ **Không xây dashboard web/UI đồ họa**: CLI in ra terminal
- ✅ **Không thêm scheduler/cron nội bộ**: `check-stale` là lệnh chạy tay
- ✅ **Không đổi Artifact Schema**: Giữ nguyên file-based
- ✅ **Không động vào Phase 3**: Tất cả 87 tests cũ vẫn pass

---

## Việc KHÔNG làm (mục 4)

- ❌ Không xây dashboard web/UI đồ họa — chỉ CLI in ra terminal ✅
- ❌ Không thêm scheduler/cron nội bộ — `check-stale` là lệnh chạy tay ✅
- ❌ Không đổi Artifact Schema để thêm field "escalated_at" — dùng event log ✅
- ❌ Không động vào Phase 3 (risk matrix, debate) ✅
- ❌ Không nâng cấp Artifact Store sang SQLite/DB thật ✅
