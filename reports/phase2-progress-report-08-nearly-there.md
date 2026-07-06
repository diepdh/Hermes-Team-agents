# Phase 2 — Báo cáo tiến độ #8: 47/51 pass, 4 test còn lại do content quá ngắn

**Ngày:** 2026-07-06
**Trạng thái:** Đã đạt ALL IMPORTS OK, 47/51 test pass — còn 4 test fail do content quá ngắn
**Branch:** `master`
**Commit bảo vệ:** `6e762f2` (28 files, hermes/ đã an toàn trong git)

---

## Tiến độ 9 bước reviewer

| Bước | Nội dung | Trạng thái |
|-------|----------|------------|
| 0 | Cleanup + backup (39MB tar.gz) | ✅ |
| 1 | Safety commit `6e762f2` (28 files) | ✅ |
| 2 | Bổ sung `hermes/pipeline/__init__.py` | ✅ |
| 3 | `git rm -r core agents pipeline` + `git rm __main__.py __init__.py` | ✅ |
| 4 | Sửa 13 imports trong `main.py`, `run_baseline.py`, `tests/` → `from hermes.xxx` | ✅ |
| 5 | `pyproject.toml`: `include = ["hermes*"]` | ✅ |
| 6 | `pip uninstall hermes -y && pip install -e .` thành công | ✅ |
| **7** | **ALL IMPORTS OK** — 12 modules, 1 path duy nhất `hermes/` | ✅ |
| **8** | `pytest -v --tb=short` | ⚠️ 47/51 pass |
| 9 | Commit merge kết quả | ⬜ chờ bước 8 xong |

---

## Bước 7 — ALL IMPORTS OK (nguyên văn)

```
hermes.__path__ = ['C:\\Users\\dohuy\\Downloads\\03. Source code\\Hermes Engineerig OS\\hermes\\hermes']
ALL IMPORTS OK
```

✅ Chỉ 1 đường dẫn duy nhất, không còn `hermes/hermes/` trống.

---

## Bước 8 — Pytest: 47/51 pass

### Đã pass (47/51)

| File | Số test | Kết quả |
|------|---------|---------|
| `test_phase0.py` | 11 | **11/11 PASS** (bao gồm `test_cli_init` đã từng fail!) |
| `test_phase1.py` | 9 | **9/9 PASS** (đã fix 3 `patch("pipeline.")` → `patch("hermes.pipeline.")`) |
| `test_phase2.py` | 26 | **26/26 PASS** (toàn bộ verifier, checker, agent tests) |
| `test_phase2_human_gate.py` | 5 | **1/5 PASS** |

### Còn fail (4/51)

Tất cả 4 test cùng 1 root cause: content quá ngắn → rubric fail → `finalize_verification` trả về `"fail"` thay vì `"escalated"`.

```
FAILED test_escalated_to_pass_via_update_verification
    assert rec["verification_status"] == "escalated"
    → got "fail" (rubric score too low)
    
FAILED test_find_verification_record
FAILED test_approve_command_updates_to_pass  
FAILED test_approve_warns_on_already_pass
```

### Các lỗi ĐÃ fix trong session này

| Lỗi | File/line | Fix |
|------|-----------|-----|
| `ModuleNotFoundError: No module named 'pipeline'` | test_phase1.py:95,134,161 | `patch("pipeline.")` → `patch("hermes.pipeline.")` |
| `FileNotFoundError: lecture-lecture.md` | test_phase2_human_gate.py:59,127,156,191 | `"lecture-lecture.md"` → `f"lecture-lecture_v{vid}.md"` |
| `AttributeError: 'Workspace' object has no attribute 'artifact_index'` | hermes/__main__.py:31 | `_find_verification_record` → dùng `list_artifacts()` |
| `ModuleNotFoundError: No module named 'hermes.core.workspace'` (test_cli_init) | Đã fix khi đồng nhất cấu trúc | |

---

## Hướng fix 4 test còn lại

### Root cause

4 test (`test_escalated_to_pass_via_update_verification`, `test_find_verification_record`, `test_approve_command_updates_to_pass`, `test_approve_warns_on_already_pass`) lưu artifact với content:

```python
content="# Test Lecture\n\nContent."
```

Content này ~4 từ, không pass rubric `lecture_draft` (cần >300 từ cho `covers_all_outline_sections`, >500 từ cho `length_adequate`, có "for example" cho `examples_included`).

Kết quả: `verify_artifact` trả về `passed=False` → `finalize_verification` **đúng** set status `"fail"` (không escalate).  

Nhưng test kỳ vọng status `"escalated"` — tức là test cần content **pass rubric** để `finalize_verification` escalate qua human gate.

### Fix

Thay content ngắn thành content dài pass rubric:

```python
# Hiện tại (SAI):
content="# Test Lecture\n\nContent."

# Cần sửa thành (đủ dài, có "for example", có citations):
content=("# Lecture Draft\\n\\nFormative assessment is important. "
         "For example teachers use exit tickets. "
         "Research shows positive effects (Black, 1998).\\n\\n" * 60)
```

Với `* 60`: ~1140 từ, pass cả 4 tiêu chí rubric (score ≥ 0.80).  
→ `finalize_verification` sẽ escalate đúng → test pass.

### Trở ngại kỹ thuật

File `tests/test_phase2_human_gate.py` đã bị write sai format trong lần sửa cuối (multiline string bị vỡ thành actual newlines thay vì escaped `\\n`). Cần:
1. **`git checkout tests/test_phase2_human_gate.py`** — file này chưa commit, nhưng có thể cần viết lại từ đầu thay vì checkout
2. **Hoặc viết lại toàn bộ file** — copy từ commit cũ + sửa 4 dòng content

Đây là bước cuối cùng trước khi đạt **51/51**. Sau khi fix, cần chạy lại:

```bash
pytest tests/test_phase2_human_gate.py -v --tb=short
# Kỳ vọng: 5 passed
pytest tests/ -v --tb=short
# Kỳ vọng: 51 passed
```

---

## Câu hỏi cho reviewer

1. **Cho phép checkout `tests/test_phase2_human_gate.py` không?** File đã bị hỏng format. Có thể:
   - (a) `git checkout tests/test_phase2_human_gate.py` → quay về bản commit gốc, rồi sửa lại nội dung đúng cách
   - (b) Viết lại toàn bộ file từ đầu với content đúng

2. **Sau khi 51/51 pass** → tiếp tục **Bước 9 (commit merge)** rồi chuyển sang baseline (p2-7) + 7 commits (p2-8) như lộ trình?

---

## Checklist reviewer (từ hướng dẫn trước)

| # | Yêu cầu | Trạng thái |
|---|---------|------------|
| 1 | Commit bảo vệ Bước 1 | ✅ `6e762f2` |
| 2 | `find core agents pipeline` rỗng | ✅ |
| 3 | Danh sách import đã sửa | ✅ 13 imports (chi tiết trong báo cáo #7) |
| 4 | `ALL IMPORTS OK` thật | ✅ |
| 5 | Full pytest output | ⚠️ 47/51 — cần fix 4 test cuối |
| 6 | Commit hash Bước 9 | ⬜ chờ |
