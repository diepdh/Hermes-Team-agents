# Phase 2 — Báo cáo tiến độ #3

**Ngày:** 2026-07-06 (theo session)
**Trạng thái:** Packaging root cause identified & fixed
**Branch:** `wip-phase1`

---

## 1. Root cause phát hiện mới — cấu trúc thư mục ambiguous

Tất cả 6 test fail đều bắt nguồn từ **bug cấu trúc thư mục**, không phải import convention:

```
hermes/                          ← package root (có __init__.py, agents/, core/, pipeline/)
  hermes/                        ← THƯ MỤC TRỐNG tạo nhầm từ Phase trước
  core/verifier.py               ← nằm TRONG package root
  agents/                        ← nằm TRONG package root
```

`pip install -e .` với `include = ["hermes*"]` phát hiện `hermes/hermes/__init__.py` (file không tồn tại) trước → ánh xạ `hermes` → `hermes/hermes/` (thư mục trống). Kết quả: `import hermes.core` → ModuleNotFoundError.

---

## 2. Đã hoàn thành

| # | Hạng mục | Chi tiết |
|---|---|---|
| A | Chuẩn hóa imports | 17 files: `from core.` → `from hermes.core.`, `from agents.` → `from hermes.agents.` |
| B | Xóa PYTHONPATH hacks | `__main__.py` (sys.path), `test_phase0.py`, `test_phase2_human_gate.py` |
| C | Tạo `pyproject.toml` | `[build-system]` + `[project]` + explicit package-dir fix |
| D | Thêm `finalize_verification()` | `HUMAN_GATE_TYPES = {"lecture_draft", "quiz_bank"}`, logic tập trung trong 1 hàm |
| E | Refactor `run_stage()` | Thay inline if/else bằng `finalize_verification()`, xóa duplicate import block |
| F | Rewrite human gate tests | 5 tests đều qua `finalize_verification()`, dùng rubric thật |
| G | grep verification | 0 kết quả cho `from core.` / `import core.` / `PYTHONPATH` / `sys.path.insert` |

---

## 3. `pyproject.toml` fix — chưa verify

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes"
version = "0.1.0"
requires-python = ">=3.10,<3.14"

[tool.setuptools]
package-dir = {"" = "."}
packages = ["hermes", "hermes.agents", "hermes.core",
            "hermes.pipeline", "hermes.rubrics", "hermes.schemas"]
```

---

## 4. `finalize_verification()` — điểm duy nhất quyết định status

```python
HUMAN_GATE_TYPES = {"lecture_draft", "quiz_bank"}

def finalize_verification(workspace, artifact_id, version, artifact_type,
                          rubric_result, notes=""):
    if not rubric_result["passed"]:
        status = "fail"
    elif artifact_type in HUMAN_GATE_TYPES:
        status = "escalated"
    else:
        status = "pass"

    update_verification(workspace, artifact_id, version, status,
                         notes=json.dumps(rubric_result["detail"], ensure_ascii=False))
    return status
```

---

## 5. Còn phải làm

- [ ] **Bước 1:** Xóa `hermes/hermes/` (thư mục trống) — nguyên nhân ambiguous structure
- [ ] **Bước 2:** `pip install -e . --force-reinstall`
- [ ] **Bước 3:** `python -c "import hermes.core.workspace; print('OK')"` — xác nhận import được
- [ ] **Bước 4:** `pytest -v --tb=short` → ghi lại số pass/fail thật
- [ ] **Bước 5:** Fix `test_cli_init` subprocess env nếu còn fail
- [ ] **Bước 6:** Commit 7 cái theo thứ tự reviewer yêu cầu
- [ ] **Bước 7:** Baseline 2–3 lần → `logs/phase2_baseline.json`
- [ ] **Bước 8:** Báo cáo Phase 2 hoàn thành

---

## 6. 7 commits theo thứ tự reviewer yêu cầu

1. `fix(packaging): editable install, standardize imports, remove PYTHONPATH hacks`
2. `feat(phase2): verifier registry`
3. `feat(phase2): rubrics and checkers`
4. `feat(phase2): curriculum/content/assessment/editor agents`
5. `feat(phase2): full lecture pipeline + human gate + CLI approve`
6. `test(phase2): fix failing tests, full suite green`
7. `docs(phase2): completion report`

---

**Chờ:** Reviewer hướng dẫn sau khi chạy lại `pip install -e .` và xem kết quả `pytest`.
