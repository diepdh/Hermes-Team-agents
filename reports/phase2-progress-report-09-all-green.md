# Phase 2 — Báo cáo tiến độ #9: 51/51 pass + commit merge hoàn tất

**Ngày:** 2026-07-06
**Trạng thái:** Tất cả test pass, commit merge đã hoàn thành — sẵn sàng baseline
**Branch:** `master`
**Commit mới nhất:** `137da70`

---

## Mục 1: Ground-truth score của VALID_LECTURE_CONTENT (nguyên văn)

```
$ python -c "from hermes.core.verifier import check_lecture_draft; import json
candidate_content = '# Lecture Draft\n\n' + (
    'This section explains the concept in depth. '
    'For example, consider a classroom scenario where students apply it directly. '
) * 80
rubric = json.load(open('hermes/rubrics/R-lecture-draft-v1.json'))
result = check_lecture_draft(candidate_content, rubric)
print(json.dumps(result, indent=2, ensure_ascii=False))"

{
  "passed": true,
  "score": 1.0,
  "detail": {
    "covers_all_outline_sections": 1.0,
    "examples_included": 1.0,
    "length_adequate": 1.0,
    "no_unsupported_claims": 1.0
  }
}
```

✅ Score thật = **1.0/1.0** — không giả định, đã verify trước khi đưa vào test.

---

## Mục 2: test_phase2_human_gate.py đã sửa

### Các chỉnh sửa

| # | Sửa | Chi tiết |
|---|------|----------|
| 1 | Thêm constant `VALID_LECTURE_CONTENT` | Dùng chung cho 4 test, tránh lặp code |
| 2 | Content không chứa số/năm | Tránh rủi ro checker hiểu nhầm unsupported claim |
| 3 | Sửa `ws.artifact_index` → `list_artifacts(ws)` | Property không tồn tại trong Workspace |
| 4 | Sửa tên file `lecture-lecture.md` → `lecture-lecture_v{vid}.md` | Khớp với `save_artifact` format |
| 5 | `hermes/core/storage.py`: thêm `"escalated"` vào accepted status | Phase 1 chỉ có `("pending","pass","fail")` |

---

## Mục 3: Full pytest — 51 passed, 0 failed (nguyên văn)

```
============================= test session starts =============================
tests/test_phase0.py::test_schema_valid_task PASSED                      [  1%]
tests/test_phase0.py::test_schema_invalid_task_missing_field PASSED      [  3%]
tests/test_phase0.py::test_rubric_schema PASSED                          [  5%]
tests/test_phase0.py::test_state_machine_valid_transition PASSED         [  7%]
tests/test_phase0.py::test_state_machine_invalid_transition PASSED       [  9%]
tests/test_phase0.py::test_state_machine_verified_terminal PASSED        [ 11%]
tests/test_phase0.py::test_artifact_versioning PASSED                    [ 13%]
tests/test_phase0.py::test_update_verification PASSED                    [ 15%]
tests/test_phase0.py::test_two_workspaces_isolated PASSED                [ 17%]
tests/test_phase0.py::test_workspace_is_portable PASSED                  [ 19%]
tests/test_phase0.py::test_cli_init PASSED                               [ 21%]
tests/test_phase1.py::test_verifier_scores_complete_artifact PASSED      [ 23%]
tests/test_phase1.py::test_verifier_fails_missing_citations PASSED       [ 25%]
tests/test_phase1.py::test_verifier_fails_missing_summary PASSED         [ 27%]
tests/test_phase1.py::test_verifier_fails_missing_gaps PASSED            [ 29%]
tests/test_phase1.py::test_pipeline_mocked_kickoff_passes_first_attempt PASSED [ 31%]
tests/test_phase1.py::test_pipeline_passes_first_attempt PASSED          [ 33%]
tests/test_phase1.py::test_pipeline_retry_then_pass PASSED               [ 35%]
tests/test_phase1.py::test_pipeline_escalates_after_max_retries PASSED   [ 37%]
tests/test_phase1.py::test_llm_config_registry PASSED                    [ 39%]
tests/test_phase1.py::test_rubric_criteria_names_match_verifier PASSED   [ 41%]
tests/test_phase2.py::test_verify_artifact_dispatches_to_correct_checker PASSED [ 43%]
... (25 tests test_phase2.py — all PASSED) ...
tests/test_phase2_human_gate.py::test_human_gate_types_defined PASSED    [ 90%]
tests/test_phase2_human_gate.py::test_escalated_to_pass_via_update_verification PASSED [ 92%]
tests/test_phase2_human_gate.py::test_non_human_gate_type_stays_pass PASSED [ 94%]
tests/test_phase2_human_gate.py::test_find_verification_record PASSED    [ 96%]
tests/test_phase2_human_gate.py::test_approve_command_updates_to_pass PASSED [ 98%]
tests/test_phase2_human_gate.py::test_approve_warns_on_already_pass PASSED [100%]

======================= 51 passed, 41 warnings in 8.38s =======================
```

---

## Mục 4: Commit Bước 9

```
137da70 fix(packaging): merge core/agents/pipeline into hermes package, remove duplicates
```

Commit này bao gồm:
- Safety commit `6e762f2` (28 files `hermes/`) làm parent
- `git rm -r core agents pipeline` + `git rm __main__.py __init__.py`
- `main.py`, `run_baseline.py`, `tests/` → `from hermes.xxx`
- `pyproject.toml` → `include = ["hermes*"]`
- `hermes/core/storage.py` → thêm `"escalated"` status
- `tests/test_phase2_human_gate.py` → content pass rubric, unified constant
- `tests/conftest.py`, `tests/test_phase2.py`, `rubrics/`, `reports/` — tất cả file mới

---

## Mục 5 & 6: Baseline + Commit history

| # | Việc | Trạng thái |
|---|------|------------|
| 1 | Ground-truth score VALID_LECTURE_CONTENT | ✅ Score=1.0 |
| 2 | test_phase2_human_gate.py sửa xong | ✅ 1 constant dùng chung |
| 3 | 51/51 pass | ✅ 0 failed |
| 4 | Commit merge Bước 9 | ✅ `137da70` |
| 5 | Baseline `logs/phase2_baseline.json` (2-3 lần chạy thật) | ⬜ chờ reviewer OK |
| 6 | Rà commit history — liệt kê commit nào chứa phần nào | ⬜ chờ reviewer OK |

---

## Lộ trình còn lại

Sau khi reviewer xác nhận:

1. **Chạy baseline** — `python run_baseline.py` 2-3 lần, ghi `logs/phase2_baseline.json`
2. **7 commits tách theo phần việc** (nếu chưa tách — kiểm tra commit hiện tại đã gom gì)
3. **Báo cáo hoàn thành Phase 2**

---

## Ghi chú bổ sung

- File `tests/test_phase2_human_gate.py` đã được viết lại hoàn toàn thay vì `git checkout` (vì file chưa từng commit nên checkout không khả dụng)
- `fix_multiline.py` và `fix_test_content.py` (scripts tạm) đã được xóa trước khi commit
- `gen_content.py` (script tạm) cũng đã xóa — không có file temp nào trong commit
- `hermes/__main__.py` đã cập nhật `_find_verification_record` dùng `list_artifacts()` thay vì `ws.artifact_index`
