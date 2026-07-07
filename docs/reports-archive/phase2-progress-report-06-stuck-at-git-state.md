# Phase 2 — Báo cáo tiến độ #6: Git state lộn xộn, cần hướng dẫn

**Ngày:** 2026-07-06
**Trạng thái:** Chờ reviewer quyết định trước khi thực thi tiếp
**Branch:** `wip-phase1`

---

## Tóm tình trạng

Sau khi chạy Bước 0–1 của 9-bước reviewer, git state hiện tại **lộn xộn** do các lần thử trước đó để lại:

```
Trạng thái git hiện tại:
- `core/` (7 files): bản CŨ Phase 0.5 — staged for delete (D)
- `hermes/` (đã có sẵn từ trước): chứa bản MỚI Phase 2 (unchanged/untracked)
- `agents/` (6 files): có cả staged (A) và modified (M) — staged là copies mới Phase 2
- `pipeline/lit_review_pipeline.py`: staged để mv
- `pipeline/full_lecture_pipeline.py`: staged như copy mới
- `__main__.py`: staged deleted (D) — nhưng hermes/__main__.py là bản mới
- `main.py`: modified — chưa update imports
- `run_baseline.py`: modified — chưa update imports
- `tests/test_phase0.py`, `tests/test_phase1.py`: modified — chưa update imports
```

**Phát hiện quan trọng khi diff:**
```
diff core/validator.py hermes/core/validator.py → DIFFERENT
```
- `core/validator.py` = bản Phase 0.5 (cũ, `_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent`)
- `hermes/core/validator.py` = bản Phase 2 (mới hơn)

**Tương tự các file khác trong `core/` và `agents/`**: bản mới đang ở `hermes/`, bản cũ ở `core/` và `agents/` root level.

---

## Hai lựa chọn

### Lựa chọn A: Hợp nhất kiểu "overwrite cũ bằng mới"

1. `git mv core/*.py hermes/core/` (move bản cũ vào hermes/core/ — git sẽ overwrite)
2. `git mv agents/*.py hermes/agents/` (tương tự)
3. `git mv pipeline/*.py hermes/pipeline/`
4. `git mv rubrics hermes/rubrics` (nếu rubrics/ ở root có bản mới hơn)
5. `git rm core/ agents/ pipeline/` (xóa thư mục rỗng sau khi move)
6. `git rm __main__.py` (đã có hermes/__main__.py)
7. Sửa imports trong `main.py`, `run_baseline.py` → `from hermes.xxx`
8. Sửa imports trong `tests/test_phase0.py`, `tests/test_phase1.py`
9. `pip install -e .`

**Ưu điểm:** Giữ nguyên git history của các file cũ
**Rủi ro:** Cần kiểm tra kỹ không có file nào bị mất nội dung mới

### Lựa chọn B: Reset hoàn toàn rồi làm lại từ đầu

1. `git reset --hard HEAD` (quay về commit cuối cùng clean)
2. Hoặc xóa toàn bộ repo rồi clone lại
3. Bắt đầu lại 9 bước từ đầu

**Ưu điểm:** Sạch sẽ, không có state lẫn lộn
**Rủi ro:** Mất tất cả thay đổi chưa commit (bao gồm cả bản Phase 2 trong `hermes/`)

---

## Câu hỏi cho reviewer

1. **Có cho phép `git reset --hard` không?** Nếu các thay đổi Phase 2 trong `hermes/` đã được commit hết (hoặc không cần giữ), thì reset là cách sạch nhất.

2. **Hay tiếp tục với Lựa chọn A?** Giữ history của file cũ, overwrite bằng bản mới.

3. **Lệnh `rm -rf hermes/` mà user block hôm nay — có nên thực hiện không?** Sau khi xác nhận Lựa chọn A hoặc B, nếu `hermes/` là bản trùng (không phải bản mới duy nhất), thì có thể xóa được.

---

## Cam kết

- **Không thực thi lệnh destructive nào** cho đến khi có xác nhận từ reviewer.
- Đã chạy được 2 bước đầu tiên của 9-bước reviewer:
  - ✅ Bước 0: Cleanup done (hermes.egg-info và __pycache__ đã xóa)
  - ✅ Bước 1: Grep schemas/ và rubrics/ — KHÔNG có relative path nào cần sửa
- Mọi lệnh tiếp theo sẽ chờ phản hồi từ reviewer.
