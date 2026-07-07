# Phase 2 — Báo cáo Forensics #7: Bằng chứng đầy đủ trước khi hợp nhất

**Ngày:** 2026-07-06
**Trạng thái:** Forensics hoàn tất, chờ reviewer quyết định
**Branch:** `wip-phase1`

---

## Bước 0 — Backup ✅

```
File: hermes-backup-20260706-101947.tar.gz
Size: 39 MB
Vị trí: C:/Users/dohuy/Downloads/03. Source code/Hermes Engineerig OS/
```

---

## Bước 1 — Diff toàn bộ cặp file trùng tên

### core/ vs hermes/core/ (8 files)

| File | Kết quả | Chi tiết |
|------|---------|----------|
| `__init__.py` | IDENTICAL | |
| `state_machine.py` | IDENTICAL | |
| `llm_config.py` | CRLF→LF only | Cùng nội dung, chỉ khác line ending |
| `validator.py` | CRLF→LF only | Cùng nội dung, chỉ khác line ending |
| `workspace.py` | CRLF→LF only | Cùng nội dung, chỉ khác line ending |
| `storage.py` | **DIFF import** | `from core.workspace` → `from .workspace` (relative import) |
| `task_index.py` | **DIFF import** | `from core.workspace` → `from .workspace` (relative import) |
| **`verifier.py`** | **BẢN MỚI 3X** | `core/`: 71 dòng (Phase 1 — chỉ 1 checker `check_lit_review`). `hermes/core/`: **274 dòng** (Phase 2 — `CHECKER_REGISTRY`, `finalize_verification()`, `HUMAN_GATE_TYPES`, 4 checkers: `lit_review_md`, `course_outline`, `lecture_draft`, `quiz_bank`) |

⏱️ Mtime: `hermes/core/verifier.py` = **Jul 6 09:33** (sáng nay, session này), `core/verifier.py` = **Jul 5** (hôm qua)

### agents/ vs hermes/agents/ (6 files)

| File | Kết quả |
|------|---------|
| `__init__.py` | IDENTICAL |
| `assessment_builder.py` | IDENTICAL |
| `content_writer.py` | IDENTICAL |
| `curriculum_designer.py` | IDENTICAL |
| `editor.py` | IDENTICAL |
| `researcher.py` | CRLF→LF only |

### pipeline/ vs hermes/pipeline/

| File | Kết quả |
|------|---------|
| `__init__.py` | **CHỈ có ở pipeline/**, `hermes/pipeline/` thiếu |
| `full_lecture_pipeline.py` | IDENTICAL |
| `lit_review_pipeline.py` | DIFF: `from core.xxx` → `from hermes.core.xxx` |

---

## Bước 2 — Git tracking cho `hermes/`

```
git log --all --oneline -- hermes/       → KHÔNG có commit nào
git status --porcelain=v2 -- hermes/     → ? hermes/  (toàn bộ untracked)
git ls-files hermes/                     → KHÔNG file nào
```

**Kết luận quan trọng:** Toàn bộ code Phase 2 trong `hermes/` **chưa từng được commit**. Chúng là UNTRACKED — chỉ tồn tại trên đĩa, không có lịch sử git. Nếu dùng `git reset --hard`, tất cả sẽ **mất vĩnh viễn**.

---

## Bước 3 — Git reflog

Không có `reset`, `checkout`, `rebase` bất thường nào. Tất cả reflog là `commit` hoặc `commit (amend)`:

```
66f35b1 HEAD@{0}: commit: docs(phase1): add final verification report
fd09db4 HEAD@{1}: commit: chore(phase0.5): housekeeping cleanup
...
e675231 HEAD@{11}: commit (initial): chore(phase0): bootstrap repo structure
```

---

## Trả lời câu hỏi reviewer

### 1. Coder Agent có tự tạo file nào trong `hermes/` không?

**Có.** Các file có mtime **sáng nay** (Jul 6) là do Coder Agent tạo trong session trước:
- `hermes/core/storage.py` (09:33)
- `hermes/core/task_index.py` (09:33)
- `hermes/core/verifier.py` (09:33)
- `hermes/agents/assessment_builder.py` (09:43)
- `hermes/agents/content_writer.py` (09:43)
- `hermes/agents/curriculum_designer.py` (09:43)
- `hermes/agents/editor.py` (09:43)
- `hermes/pipeline/full_lecture_pipeline.py` (09:43)

Các file còn lại (mtime Jul 5) là bản sao do `cp` từ root vào `hermes/` trong session trước.

### 2. Lệnh `rm -rf hermes/` bị chặn như thế nào?

Trình tự:
1. Coder Agent tạo `hermes/` trong session trước (sáng nay) qua `git mv` + `cp` để thử hợp nhất code
2. Sau đó phát hiện cấu trúc lộn xộn (cả `core/` root lẫn `hermes/core/` trùng code)
3. Để reset sạch, Coder Agent đề xuất `rm -rf hermes/` 
4. **Cơ chế security của terminal đã block** lệnh này vì phát hiện `rm -rf` trên thư mục quan trọng
5. User thấy block, hỏi ngược lại "lệnh này nguy hiểm, em xác nhận xem đúng không"
6. Sau khi diff `validator.py`, Coder Agent phát hiện `hermes/` có code **mới hơn**, hủy ý định xóa

---

## Tóm tắt bằng chứng

1. **`hermes/` = bản đầy đủ, mới hơn** Phase 2 — có `finalize_verification()`, `CHECKER_REGISTRY`, 4 checkers, human gate
2. **`core/` root = bản cũ** Phase 1 — chỉ 1 checker `check_lit_review()`, 71 dòng
3. **`hermes/` chưa commit** — toàn bộ untracked, dễ mất nếu thao tác destructive
4. **Không có git bất thường** trong reflog

**Khuyến nghị:** `git add hermes/` trước khi làm gì khác — để bảo vệ code chưa commit, sau đó tiếp tục hợp nhất theo reviewer chỉ đạo.
