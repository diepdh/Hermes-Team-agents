# Hermes Engineering OS — Hướng dẫn soạn bài giảng

Dùng Hermes để tự động tạo giáo trình/bài giảng học thuật từ câu hỏi nghiên cứu.

**Pipeline:** Researcher → Curriculum Designer → Content Writer → Assessment Builder → Editor → Human Gate → Final

---

## 1. Quickstart — chạy pipeline đầy đủ

```python
from hermes.core.workspace import Workspace
from hermes.pipeline.full_lecture_pipeline import run_full_lecture_pipeline

result = run_full_lecture_pipeline(
    workspace_root="./my-lecture-workspace",
    research_question=(
        "Phương pháp đánh giá năng lực tự học của sinh viên đại học "
        "trong bối cảnh chuyển đổi số là gì?"
    ),
    learning_objectives=(
        "1. Hiểu các mô hình tự học phổ biến; "
        "2. Phân tích công cụ đánh giá năng lực tự học; "
        "3. Thiết kế rubric đánh giá phù hợp"
    ),
    task_id_prefix="bai-giang-01",
    provider="opencode_go",
)

print(result["status"])    # "complete" | "escalated"
for stage in result["stages"]:
    print(f"  {stage['name']}: {stage['status']}")
```

**Output:** 5 artifact được tạo trong workspace:
1. `lit_review_md` — Tổng quan tài liệu nghiên cứu
2. `course_outline` — Đề cương khóa học
3. `lecture_draft` — Bản thảo bài giảng (🛑 cần Human Gate)
4. `quiz_bank` — Ngân hàng câu hỏi (🛑 cần Human Gate)
5. `final_content` — Bài giảng hoàn chỉnh sau biên tập

---

## 2. Các bước pipeline chi tiết

### Stage 1: Researcher — Tổng quan tài liệu

- **Agent:** Researcher
- **Input:** `research_question`
- **Output:** `lit_review_md` — Markdown chứa: summary, gaps identified, references
- **Risk:** Low
- **Thời gian:** ~30-60s

### Stage 2: Curriculum Designer — Đề cương

- **Agent:** Curriculum Designer  
- **Input:** `lit_review_md` (đã verified)
- **Output:** `course_outline` — Learning objectives, session breakdown, assessment hooks
- **Risk:** Medium
- **Thời gian:** ~30-60s

### Stage 3: Content Writer — Bài giảng

- **Agent:** Content Writer
- **Input:** `lit_review_md` + `course_outline`
- **Output:** `lecture_draft` — Bài giảng đầy đủ ≥ 500 từ
- **Risk:** **High** → 🛑 Human Gate bắt buộc
- **Thời gian:** ~60-120s

### Stage 4: Assessment Builder — Câu hỏi

- **Agent:** Assessment Builder
- **Input:** `lecture_draft`
- **Output:** `quiz_bank` — ≥ 5 câu hỏi kèm đáp án
- **Risk:** **High** → 🛑 Human Gate bắt buộc
- **Thời gian:** ~30-60s

### Stage 5: Editor — Biên tập

- **Agent:** Editor
- **Input:** `lecture_draft` + `quiz_bank` (đã qua Human Gate)
- **Output:** `final_content` — Bài giảng hoàn chỉnh
- **Risk:** Medium
- **Thời gian:** ~30-60s

---

## 3. Human Gate — duyệt thủ công

2 artifact bắt buộc phải duyệt thủ công trước khi pipeline tiếp tục:

### Kiểm tra artifact nào đang chờ

```bash
python -m hermes dashboard --workspace ./my-lecture-workspace
```

Output ví dụ:
```
Đang chờ duyệt (escalated):
  bai-giang-01-lecture (lecture_draft, v1) — chờ 14.2 giờ
  bai-giang-01-quiz (quiz_bank, v1) — chờ 8.5 giờ
```

### Đọc nội dung artifact

```bash
# Cách 1: Đọc file trực tiếp
cat ./my-lecture-workspace/.hermes/artifacts/bai-giang-01-lecture_v1.md

# Cách 2: Dùng Python
python -c "
from hermes.core.workspace import Workspace
from hermes.core.storage import get_artifact, read_artifact_content
ws = Workspace('./my-lecture-workspace')
art = get_artifact(ws, 'bai-giang-01-lecture')
print(read_artifact_content(ws, art))
"
```

### Duyệt artifact

```bash
python -m hermes approve \
  --workspace ./my-lecture-workspace \
  --artifact bai-giang-01-lecture \
  --version 1
```

Sau khi duyệt, pipeline tự động tiếp tục sang stage tiếp theo.

---

## 4. Pipeline rút gọn (chỉ Literature Review)

```python
from hermes.pipeline.lit_review_pipeline import run_lit_review_pipeline

artifact, result, metrics = run_lit_review_pipeline(
    workspace_root="./my-lit-review",
    research_question="Phương pháp học tập kết hợp (blended learning) hiệu quả nhất là gì?",
    task_id="T1",
    artifact_id="A1",
    provider="opencode_go",
)

print(artifact["verification_status"])
print(f"Score: {result['score']}")
```

---

## 5. Giám sát + debug

### Dashboard

```bash
python -m hermes dashboard --workspace ./my-lecture-workspace
```

### Đọc event log

```bash
cat ./my-lecture-workspace/.hermes/logs/events.jsonl | python -m json.tool
```

### Chạy lại pipeline từ đầu

Xóa workspace cũ và chạy lại:
```bash
rm -rf ./my-lecture-workspace
# Chạy lại run_full_lecture_pipeline(...) như trên
```

---

## 6. Cấu trúc workspace sau khi chạy

```
my-lecture-workspace/
  .hermes/
    artifacts/
      bai-giang-01-lit_v1.md       ← Tổng quan tài liệu
      bai-giang-01-outline_v1.md   ← Đề cương
      bai-giang-01-lecture_v1.md   ← Bài giảng (pending human gate)
      bai-giang-01-quiz_v1.md      ← Câu hỏi (pending human gate)
      bai-giang-01-final_v1.md     ← Bài giảng hoàn chỉnh
      index.json                   ← Registry tất cả artifact
    logs/
      events.jsonl                 ← Toàn bộ lịch sử sự kiện
```

---

## 7. Dùng với Hermes Desktop (khuyến nghị)

Hermes Desktop cho phép bạn chạy pipeline qua giao diện chat thay vì viết code Python:

1. **Mở Hermes Desktop:** `hermes desktop` (hoặc `hermes gui`)
2. **Mở thư mục Engineering OS** trong Desktop (hoặc `cd` tới đó)
3. **Chat với agent:**
   > "Chạy pipeline soạn bài giảng với câu hỏi nghiên cứu: Phương pháp đánh giá năng lực tự học của sinh viên. Mục tiêu: Hiểu mô hình tự học, phân tích công cụ đánh giá, thiết kế rubric."

Agent sẽ tự động:
- Gọi `run_full_lecture_pipeline()` 
- Báo cáo tiến độ từng stage
- Thông báo khi có artifact cần Human Gate
- Chờ bạn duyệt trước khi tiếp tục

**Lợi ích khi dùng Desktop:**
- Không cần viết code Python thủ công
- Xem được tool call realtime (AI đang chạy stage nào)
- Kéo thả file dữ liệu vào chat
- Quản lý nhiều session: 1 session soạn bài giảng, 1 session khác viết paper

---

## 8. Tùy chỉnh rubric (nâng cao)

Muốn thay đổi tiêu chuẩn chấm điểm, sửa file trong `hermes/rubrics/`:

| Rubric file | Áp dụng cho |
|---|---|
| `R-lit-review-v2.json` | Literature review |
| `R-course-outline-v1.json` | Đề cương |
| `R-lecture-draft-v1.json` | Bài giảng |
| `R-quiz-bank-v1.json` | Câu hỏi |
| `R-debate-verdict-v1.json` | Debate review |

Ví dụ: tăng `pass_threshold` cho lecture_draft từ 0.85 lên 0.90:
```json
{
  "rubric_id": "R-lecture-draft-v1",
  "pass_threshold": 0.90,
  ...
}
```

---

**Xem thêm:**
- [Hướng dẫn cài đặt](./user-guide-installation.md)
- [Hướng dẫn viết bài báo khoa học](./user-guide-paper.md)
