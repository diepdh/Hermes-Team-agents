# Hermes Engineering OS — Hướng dẫn viết bài báo khoa học

Dùng Hermes để viết bài báo khoa học từ dữ liệu thô, hoặc cải thiện bài báo `.docx` có sẵn.

---

## 1. Chọn pipeline phù hợp

| Bạn có... | Dùng pipeline | Mô tả |
|---|---|---|
| Chỉ có dữ liệu thô (.csv, .json, bảng số) | **P5.1–P5.6** | Analyzer → Writer → Reviewer → Publisher |
| Đã có bài `.docx` + muốn cải thiện | **P5.7a** (OPTION=2) | Đọc bài cũ → gợi ý thực nghiệm → viết lại |
| Đã có bài `.docx` + code mô phỏng đi kèm | **P5.7b** (OPTION=1) | Chạy code thật → sinh dữ liệu bổ sung → viết lại |

---

## 2. Pipeline P5.1–P5.6: Viết bài từ dữ liệu thô

### Chuẩn bị dữ liệu

Thư mục đầu vào:
```
my-paper-data/
  ├── data.csv           ← Dữ liệu thô (bắt buộc)
  ├── figures/           ← Biểu đồ, ảnh (tuỳ chọn)
  │   ├── chart1.png
  │   └── chart2.png
  └── notes.txt          ← Ghi chú nghiên cứu (tuỳ chọn)
```

### Chạy pipeline

```python
from hermes.pipeline.paper_review_pipeline import run_full_paper_pipeline

result = run_full_paper_pipeline(
    workspace_root="./my-paper-workspace",
    docx_path="./my-paper-data/data.docx",   # hoặc None nếu không có
    provider="opencode_go",
)

# Pipeline tự động:
# 1. Analyzer: đọc data.csv, mô tả biểu đồ → source_analysis
# 2. Literature Researcher: tìm citation thật từ Semantic Scholar
# 3. Writer: sinh paper_draft IMRaD từ source_analysis
# 4. Reviewer: kiểm tra data fidelity (số liệu trong bài khớp nguồn?)
# 5. Editor: sửa lỗi (nếu Reviewer phát hiện sai)
# 6. Debate: nếu risk=high, 2 agent tranh luận 3 rounds
# 7. Publisher: xuất .docx hoàn chỉnh
```

### Output

```
my-paper-workspace/
  .hermes/artifacts/
    source_analysis_v1.md       ← Phân tích dữ liệu nguồn
    literature_support_v1.md    ← Citations thật
    paper_draft_v1.md           ← Bản thảo IMRaD
    paper_draft_v2.md           ← Sau Editor sửa (nếu cần)
    final_paper_v1.md           ← Bài hoàn chỉnh → .docx
```

---

## 3. Pipeline P5.7a: Cải thiện bài `.docx` có sẵn (OPTION=2)

Dùng khi bạn đã có 1 bài báo `.docx` và muốn hệ thống gợi ý cải thiện.

### Chạy

```python
from hermes.pipeline.existing_paper_pipeline import (
    assess_existing_paper,
    run_existing_paper_to_publisher,
)
from hermes.agents.ingest_paper import ingest_existing_paper_as_draft

# Bước 1: Đánh giá bài hiện tại
with open("my-paper.docx", "rb") as f:
    from docx import Document
    doc = Document(f)
    paper_text = "\n".join(p.text for p in doc.paragraphs)

assessment = assess_existing_paper(paper_text, has_accompanying_data=False)

print("IMRaD sections present:", assessment["imrad_sections_present"])
print("Missing:", assessment["imrad_sections_missing"])
print("Suggestions:", assessment["option_2_suggestions"])

# Bước 2: Human Gate — chọn OPTION=2 (gợi ý bằng văn bản)
# Ghi OPTION=2 vào verification_notes của existing_paper_assessment artifact

# Bước 3: Chạy pipeline cải thiện
draft = ingest_existing_paper_as_draft(
    paper_text,
    suggestions=assessment["option_2_suggestions"],
)
result = run_existing_paper_to_publisher(
    workspace, draft, source_data, provider="local_cx"
)
```

---

## 4. Pipeline P5.7b: Chạy code mô phỏng thật + cải thiện bài (OPTION=1)

Dùng khi bạn có:
- 1 file `.docx` bản thảo
- Code Python mô phỏng + dữ liệu thô đi kèm

Hệ thống sẽ **thực thi code thật** trong sandbox, trích xuất kết quả, và ghép vào bài báo.

### Chuẩn bị

```
my-paper/
  ├── draft.docx              ← Bản thảo
  ├── simulation.py            ← Code mô phỏng Python
  ├── data.csv                 ← Dữ liệu đầu vào cho mô phỏng
  └── results/                 ← (tuỳ chọn) kết quả có sẵn
```

### Chạy

```python
from hermes.pipeline.existing_paper_pipeline import (
    assess_existing_paper,
    run_option1_code_runner,
)

# Bước 1: Đánh giá + xác nhận có data đi kèm
with open("my-paper/draft.docx", "rb") as f:
    from docx import Document
    paper_text = "\n".join(p.text for p in Document(f).paragraphs)

assessment = assess_existing_paper(paper_text, has_accompanying_data=True)

# Bước 2: Human Gate chọn OPTION=1
# Ghi OPTION=1 vào verification_notes

# Bước 3: Chạy code_runner (LLM sinh code → sandbox execute → extract)
# LƯU Ý: source_analysis phải verified trước khi chạy
result = run_option1_code_runner(
    workspace=ws,
    source_analysis_artifact=source_art,
    existing_paper_assessment_artifact=assessment_art,
    provider="local_cx",
    max_retries=3,  # retry nếu static scan fail
)

if result["verification_status"] == "pass":
    # generated_data.extracted_values đã được lưu
    # → ingest vào paper_draft như bình thường
    print("✅ Code chạy thành công, dữ liệu đã được trích xuất")
elif result["verification_status"] == "escalated":
    print("⚠ Cần Human Gate duyệt generated_data")
    # Dùng python -m hermes approve để duyệt
else:
    print("❌ Code_runner thất bại sau 3 lần retry")
```

### Cơ chế an toàn

Code LLM sinh ra được kiểm tra qua 3 lớp:
1. **AST static scan** — chặn import độc hại, eval, file I/O ngoài phạm vi
2. **Double-run reproducibility** — code chạy 2 lần trong sandbox độc lập, kết quả phải giống hệt
3. **Debate Review** (risk=critical) — 2 agent tranh luận về tính đúng đắn của code + kết quả

### Module được phép trong sandbox

`numpy`, `scipy.stats`, `scipy.optimize`, `statistics`, `math`, `json`, `csv`, `collections`, `itertools`, `re`, `datetime`, `typing`.

> **Lưu ý:** `pandas` hiện chưa được hỗ trợ trong sandbox. Dùng `csv` + `numpy` thay thế.

---

## 5. Cấu trúc artifact trong paper pipeline

| Artifact | Risk | Mô tả |
|---|---|---|
| `source_analysis` | Low | Dữ liệu đã phân tích (text + bảng + ảnh) |
| `literature_support` | High | Citations thật từ Semantic Scholar |
| `paper_draft` | High | Bản thảo IMRaD |
| `generated_data` | **Critical** | Dữ liệu từ code chạy thật (P5.7b) |
| `final_paper` | Critical | Bài hoàn chỉnh → Publisher xuất .docx |
| `existing_paper_assessment` | Medium | Đánh giá bài có sẵn (P5.7) |
| `debate_verdict` | Critical | Kết quả tranh luận (tự động) |

---

## 6. Xử lý sự cố thường gặp

### Code_runner static scan fail

Code LLM sinh ra bị chặn ở tầng AST scan. Pipeline tự retry tối đa 3 lần (mỗi lần LLM sinh code mới).

### Debate escalate (thường xuyên với risk=critical)

Với `generated_data` risk=critical, Debate rất kỹ và thường escalate. Đây là hành vi đúng — dùng `python -m hermes approve` để duyệt thủ công.

### `ModuleNotFoundError: No module named 'scipy'`

Scipy chưa được cài. Chạy:
```bash
uv add scipy
```

---

**Xem thêm:**
- [Hướng dẫn cài đặt](./user-guide-installation.md)
- [Hướng dẫn soạn bài giảng](./user-guide-lecture.md)
- [Tài liệu vận hành (OPERATIONS)](./OPERATIONS.md) — thêm agent, debug, mở rộng
