# Phase 2 — Báo cáo tiến độ #5: Ground-truth & Giải pháp đồng nhất

**Ngày:** 2026-07-06
**Trạng thái:** Ground-truth thu thập xong, hướng fix đã rõ
**Branch:** `wip-phase1`

---

## Mục 1: Ground-truth — 4 lệnh output nguyên văn

### Lệnh 1: Tất cả file `.py` trong repo

```
./__init__.py
./__main__.py
./agents/__init__.py
./agents/assessment_builder.py
./agents/content_writer.py
./agents/curriculum_designer.py
./agents/editor.py
./agents/researcher.py
./core/__init__.py
./core/llm_config.py
./core/state_machine.py
./core/storage.py
./core/task_index.py
./core/validator.py
./core/verifier.py
./core/workspace.py
./main.py
./pipeline/__init__.py
./pipeline/full_lecture_pipeline.py
./pipeline/lit_review_pipeline.py
./run_baseline.py
./tests/conftest.py
./tests/test_phase0.py
./tests/test_phase1.py
./tests/test_phase2.py
./tests/test_phase2_human_gate.py
```

**Quan sát:** Tất cả `.py` files nằm ở root level — flat, không có file nào bên trong `hermes/`.

---

### Lệnh 2: Tất cả directories

```
./hermes                        ← THƯ MỤC TRỐNG (không có .py bên trong)
./hermes.egg-info              ← artifact từ pip install -e cũ
./core/                        ← flat, cùng cấp với hermes/
./agents/                      ← flat, cùng cấp với hermes/
./pipeline/                    ← flat, cùng cấp với hermes/
./tests/                       ← flat, cùng cấp với hermes/
./rubrics/                     ← flat, cùng cấp với hermes/
./schemas/                     ← flat, cùng cấp với hermes/
```

**Quan sát:** `hermes/` directory tồn tại (trống, không chứa file .py). `hermes.egg-info/` là artifact cũ từ pip install.

---

### Lệnh 3: `cat pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes"
version = "0.1.0"
requires-python = ">=3.10,<3.14"

[tool.setuptools.packages.find]
where = ["."]
include = ["hermes", "core", "agents", "pipeline", "rubrics", "schemas"]
```

**Quan sát:** `include = ["hermes", "core", "agents", ...]` — setuptools được hướng dẫn tìm cả package `hermes` lẫn các packages `core`, `agents`... nhưng chúng nằm ở 2 vị trí khác nhau trong cây thư mục.

---

### Lệnh 4: `hermes.__path__`

```
hermes.__file__ = None
hermes.__path__ = ['C:\\Users\\dohuy\\Downloads\\03. Source code\\Hermes Engineerig OS\\hermes\\hermes',
                   'C:\\Users\\dohuy\\Downloads\\03. Source code\\Hermes Engineerig OS\\hermes\\hermes']
```

**Quan sát:** `hermes.__path__` trỏ vào `hermes/hermes/` (trống). `hermes.__file__ = None` vì `hermes/` là namespace package (PEP 420). Python không tìm thấy `core`, `agents`, `pipeline` qua `hermes.` vì chúng không nằm trong `hermes/hermes/`.

---

## Mục 2: Có khớp giả thuyết mục 2 trong hướng dẫn reviewer?

**CÓ — khớp hoàn toàn.**

Bằng chứng:
- Tất cả code nằm ở root level (`./core/`, `./agents/`, `./pipeline/`)
- `hermes/` directory tồn tại (trống) — đây là package "hụt" từ Phase 0.5
- `hermes.__path__` trỏ vào `hermes/hermes/` (trống) — không có code thật bên trong
- `pyproject.toml` liệt kê cả `hermes` lẫn `core`, `agents` nhưng chúng nằm ở 2 nơi khác nhau

---

## Mục 3: Thực hiện hướng fix theo 2.1 của reviewer

### Bước 3.1: Hợp nhất code vào `hermes/` package

Dùng `git mv` giữ lịch sử:

```bash
git mv core/verifier.py hermes/core/verifier.py
git mv agents/curriculum_designer.py hermes/agents/curriculum_designer.py
git mv agents/content_writer.py hermes/agents/content_writer.py
git mv agents/assessment_builder.py hermes/agents/assessment_builder.py
git mv agents/editor.py hermes/agents/editor.py
git mv pipeline/full_lecture_pipeline.py hermes/pipeline/full_lecture_pipeline.py
git mv pipeline/lit_review_pipeline.py hermes/pipeline/lit_review_pipeline.py
git mv rubrics/ hermes/rubrics/
git mv schemas/ hermes/schemas/
git mv __main__.py hermes/__main__.py
git mv __init__.py hermes/__init__.py
git mv main.py hermes/main.py
git mv run_baseline.py hermes/run_baseline.py
```

### Bước 3.2: Xóa thư mục rỗng + egg-info

### Bước 3.3: Update imports trong toàn bộ file đã move

Tất cả imports sẽ tự động đúng vì cấu trúc mới:
- `from core.workspace` → `from hermes.core.workspace`
- `from agents.researcher` → `from hermes.agents.researcher`
- `from pipeline.lit_review_pipeline` → `from hermes.pipeline.lit_review_pipeline`

### Bước 3.4: `pip install -e .` sạch

```bash
pip uninstall hermes -y
pip install -e .
```

---

## Mục 4: `ALL IMPORTS OK` — Chờ sau khi thực hiện hướng fix

---

## Mục 5: `pytest -v --tb=short` output — Chờ sau khi ALL IMPORTS OK

---

## Mục 6: Số test pass/fail cuối cùng — Chờ pytest

---

**Đã reach max tool-calling iterations.** Hướng dẫn reviewer đã rõ: cần thực hiện git mv để hợp nhất code vào `hermes/` package. Tiếp theo cần chạy:
1. Tất cả `git mv` commands (mục 3.1)
2. `find core/ agents/ pipeline/ -type f` để xác nhận rỗng
3. `pip uninstall hermes -y && pip install -e .`
4. `python -c "import hermes.core.workspace; import hermes.agents.researcher; import hermes.pipeline.full_lecture_pipeline; print('ALL IMPORTS OK')"`
5. `pytest -v --tb=short`
