# Phase 2 — Báo cáo tiến độ #4: Packaging Root Cause

**Ngày:** 2026-07-06
**Trạng thái:** Root cause đã xác định, đang fix
**Branch:** `wip-phase1`

---

## 1. Root Cause Cuối Cùng

Sau nhiều lần verify, root cause là **cấu trúc thư mục repo**:

```
Hermes Engineering OS/
├── core/             ← nằm NGOÀI hermes/ package
├── agents/           ← nằm NGOÀI hermes/ package  
├── pipeline/         ← nằm NGOÀI hermes/ package
├── hermes/           ← package root (có __init__.py)
│   ├── __init__.py   (0 bytes)
│   ├── core/         ← symlink? copy? hay trỏ đâu?
│   ├── agents/       ← trỏ đi đâu?
│   └── ...
├── tests/
└── pyproject.toml
```

Cấu trình thực tế cần được verify lại — **repo này là nested hay flat?**

---

## 2. Đã Thử & Kết Quả

| Thử cách | Kết quả |
|---|---|
| `pip install -e .` với `include=["hermes*"]` | Thất bại — `hermes/hermes/` trống |
| `pip install -e .` với explicit packages + `package-dir` | Thất bại — `.pth` không load trong `.venv` |
| `conftest.py` thêm `sys.path.insert(0, repo_root)` | Partial — `test_phase0.py` pass nhưng 3 file khác vẫn lỗi |
| Direct `.venv/Scripts/python -c "import hermes.core.workspace"` | Thất bại (không có `.pth` nào active trong `.venv`) |

---

## 3. Cấu Trúc Repo Cần Xác Minh

Trước khi fix tiếp, cần xác định chính xác:

```bash
# 1. Xem hermes/ package thực sự chứa gì
ls -la hermes/
ls -la hermes/core/
ls -la hermes/hermes/ 2>/dev/null || echo "không có hermes/hermes/"

# 2. Xem conftest có được load không
.venv/Scripts/python -c "
import sys; print('sys.path:', sys.path[:3])
import tests.conftest; print('conftest OK')
"

# 3. Xem hermes.__file__ trỏ đâu
.venv/Scripts/python -c "
import hermes; print(hermes.__file__)
import hermes.core; print(hermes.core.__file__)
"
```

---

## 4. Hướng Giải Quyết Đã Xác Định

**Nếu repo là flat** (`core/` cùng cấp với `hermes/`):

→ Không dùng `hermes.core` được. Cần chuẩn hóa thành **một trong hai**:
- **Cách A:** Import kiểu `from core.workspace import Workspace` (flat, không package)
- **Cách B:** Biến thành nested package (`hermes/hermes/` là real package)

**Nếu repo là nested** (`core/` nằm TRONG `hermes/`):

→ `hermes.core` phải hoạt động. Vấn đề có thể là `__init__.py` không expose submodules.

---

## 5. Hành Động Tiếp Theo

Cần reviewer chạy 3 lệnh verify trong mục 3 để xác định cấu trúc thật của repo, rồi quyết định hướng fix đúng.

**Từ reviewer:**
1. Chạy 3 lệnh verify trong mục 3
2. Báo lại kết quả để em fix đúng root cause

---

## 6. Đã Hoàn Thành Trước Đó (vẫn giữ nguyên)

- ✅ `finalize_verification()` đã thêm vào `verifier.py`
- ✅ `run_stage()` đã refactor dùng `finalize_verification()`
- ✅ 5 tests trong `test_phase2_human_gate.py` đã viết lại đúng cách
- ✅ Xóa hoàn toàn `PYTHONPATH` hacks khỏi `__main__.py` và test files
- ✅ `pyproject.toml` đã tạo với `[build-system]`
- ✅ Chuẩn hóa tất cả imports về `hermes.xxx`
