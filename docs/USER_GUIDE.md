# Hermes Engineering OS — Hướng dẫn sử dụng

Hệ thống sinh bài giảng đa tác tử (multi-agent), dùng CrewAI để tự động tạo tài liệu học thuật: tổng quan tài liệu → đề cương → bài giảng → câu hỏi kiểm tra → biên tập, kèm rubric chấm điểm và cơ chế phản biện cho các artifact có rủi ro cao.

---

## Mục lục

1. [Cài đặt](#1-cài-đặt)
2. [Kiến trúc tổng quan](#2-kiến-trúc-tổng-quan)
3. [CLI cơ bản](#3-cli-cơ-bản)
4. [Chạy pipeline sinh bài giảng](#4-chạy-pipeline-sinh-bài-giảng)
5. [Duyệt artifact thủ công](#5-duyệt-artifact-thủ-công)
6. [Giám sát hệ thống](#6-giám-sát-hệ-thống)
7. [Cấu trúc workspace](#7-cấu-trúc-workspace)
8. [Xử lý sự cố thường gặp](#8-xử-lý-sự-cố-thường-gặp)

---

## 1. Cài đặt

### Yêu cầu

- **Python:** 3.10 – 3.13
- **Hệ điều hành:** Windows / macOS / Linux
- **LLM provider:** Cần ít nhất 1 provider LLM được cấu hình (xem `hermes/core/llm_config.py`)

### Các bước cài đặt

```bash
# 1. Clone repo
git clone https://github.com/diepdh/Hermes-Team-agents.git
cd Hermes-Team-agents

# 2. Tạo virtual environment
python -m venv .venv

# 3. Kích hoạt venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Cài dependencies
pip install -r requirements.txt

# 5. Cài package hermes ở chế độ editable
pip install -e .

# 6. Kiểm tra cài đặt
python -c "import hermes; print('Hermes version:', hermes.__version__)"
```

### Cấu hình LLM provider

Mở `hermes/core/llm_config.py` để đăng ký provider. Hệ thống hỗ trợ:
- **OpenAI** — cần `OPENAI_API_KEY`
- **OpenCode Go** (local) — chạy local không cần API key
- **Custom provider** — thêm vào registry

Ví dụ cấu hình OpenAI:
```bash
export OPENAI_API_KEY="sk-..."
```

---

## 2. Kiến trúc tổng quan

```
Bạn (User)
  │  research_question + learning_objectives
  ▼
┌─────────────────────────────────────────────┐
│  Pipeline (full_lecture_pipeline.py)         │
│                                              │
│  Stage 1: Researcher ──► lit_review_md      │
│  Stage 2: Curriculum Designer ──► outline   │
│  Stage 3: Content Writer ──► lecture_draft  │ ← Human Gate
│  Stage 4: Assessment Builder ──► quiz_bank  │ ← Human Gate
│  Stage 5: Editor ──► final_lecture          │
│                                              │
│  Mỗi stage: Agent → Task → Verify → Retry   │
│  High-risk artifact: tự động Debate Review  │
└─────────────────────────────────────────────┘
  │
  ▼
Workspace (thư mục trên ổ đĩa)
  ├── artifacts/   ← file .md + index.json
  ├── logs/        ← events.jsonl (lịch sử)
  └── tasks/       ← task index
```

### Các artifact type

| Type | Risk | Mô tả |
|------|------|-------|
| `lit_review_md` | Low | Tổng quan tài liệu nghiên cứu |
| `course_outline` | Medium | Đề cương khóa học |
| `lecture_draft` | **High** | Bản thảo bài giảng — cần duyệt tay |
| `quiz_bank` | **High** | Ngân hàng câu hỏi — cần duyệt tay |
| `verified_content` | Low | Nội dung đã qua biên tập |
| `final_content` | Medium | Bài giảng hoàn chỉnh |
| `debate_verdict` | Critical | Kết quả phản biện (tự động) |

### Cơ chế kiểm soát chất lượng

1. **Rubric scoring** — mỗi artifact type có 1 rubric JSON chấm điểm tự động (rule-based, không LLM)
2. **Risk-adjusted threshold** — artifact high-risk bị nâng ngưỡng đạt (ví dụ: lecture_draft từ 0.70 → 0.85)
3. **Human Gate** — `lecture_draft` và `quiz_bank` luôn cần người duyệt thủ công dù rubric pass
4. **Debate Review** — artifact high/critical tự động được 2 agent (Proponent + Opponent) tranh luận 3 vòng
5. **Escalation** — nếu debate không đạt đồng thuận, artifact được gửi lên người quyết định

---

## 3. CLI cơ bản

Hệ thống cung cấp 4 lệnh CLI qua `python -m hermes`:

### 3.1 Khởi tạo workspace

```bash
python -m hermes init --workspace /path/to/my/workspace
```

Tạo cấu trúc thư mục `.hermes/` với `artifacts/`, `tasks/`, `rubrics/`, `logs/`.

### 3.2 Duyệt artifact thủ công

```bash
python -m hermes approve \
  --workspace /path/to/workspace \
  --artifact lecture-lecture \
  --version 1
```

Chuyển artifact từ trạng thái `escalated` → `pass`.

### 3.3 Dashboard giám sát

```bash
python -m hermes dashboard --workspace /path/to/workspace
```

Output ví dụ:
```
=== Hermes Dashboard ===
Artifacts:    8 versions across 5 types (4 pass, 1 fail, 3 escalated)
Debates:      2 resolved (1 consensus_pass, 0 consensus_fail, 1 no_consensus)

Đang chờ duyệt (escalated):
  lecture-lecture (lecture_draft, v1) — chờ 14.2 giờ
  lecture-quiz (quiz_bank, v1) — chờ 8.5 giờ
  lecture-outline (course_outline, v2) — chờ 2.1 giờ
```

### 3.4 Kiểm tra artifact treo quá hạn

```bash
python -m hermes check-stale \
  --workspace /path/to/workspace \
  --threshold-hours 24
```

Output ví dụ:
```
Artifacts escalated quá 24h:
  lecture-lecture (lecture_draft, v1) — 14.2h  [OK, chưa quá hạn]
  old-quiz (quiz_bank, v1) — 31.7h  [QUÁ HẠN]
```

Exit code: `1` nếu có artifact quá hạn (dùng được trong CI/cron).

---

## 4. Chạy pipeline sinh bài giảng

### 4.1 Pipeline đầy đủ (Phase 2+)

```python
from hermes.core.workspace import Workspace
from hermes.pipeline.full_lecture_pipeline import run_full_lecture_pipeline

result = run_full_lecture_pipeline(
    workspace_root="/path/to/workspace",
    research_question="Phương pháp đánh giá năng lực tự học của sinh viên đại học là gì?",
    learning_objectives="Hiểu các mô hình tự học; Phân tích công cụ đánh giá; Thiết kế rubric",
    task_id_prefix="bai-giang-01",
    provider="opencode_go",  # hoặc "openai", None = default
)

print(result["status"])   # "complete" | "escalated"
print(result["stages"])   # list các stage đã chạy
```

Pipeline tạo ra 4-5 artifact tuần tự: `lit_review_md` → `course_outline` → `lecture_draft` → `quiz_bank` → `final_lecture`. Mỗi artifact được lưu vào workspace với version tự động tăng.

### 4.2 Pipeline rút gọn (chỉ Literature Review)

```python
from hermes.pipeline.lit_review_pipeline import run_lit_review_pipeline

artifact, result, metrics = run_lit_review_pipeline(
    workspace_root="/path/to/workspace",
    research_question="Câu hỏi nghiên cứu của bạn",
    task_id="T1",
    artifact_id="A1",
    rubric=my_rubric_dict,
    provider="opencode_go",
)
```

### 4.3 Chạy baseline có sẵn

Repo có 2 script baseline:

```bash
# Phase 1 baseline — chỉ Literature Review (3 câu hỏi)
python run_baseline.py

# Phase 2 baseline — full pipeline (3 câu hỏi, 5 stage mỗi câu)
python run_p2_baseline.py
```

Kết quả lưu vào `logs/phase1_baseline.json` hoặc `logs/phase2_baseline.json`.

---

## 5. Duyệt artifact thủ công

### Khi nào cần duyệt?

Pipeline dừng ở trạng thái `escalated` trong 2 trường hợp:
1. **Human Gate** — artifact loại `lecture_draft` hoặc `quiz_bank` pass rubric → tự động escalate
2. **Debate không đồng thuận** — artifact high-risk qua debate 3 vòng không đạt consensus → escalate

### Các bước duyệt

1. **Xem dashboard** để biết artifact nào đang chờ:
   ```bash
   python -m hermes dashboard --workspace /path/to/workspace
   ```

2. **Đọc nội dung artifact**:
   ```bash
   # Cách 1: Đọc file trực tiếp
   cat /path/to/workspace/.hermes/artifacts/<artifact_id>_v<version>.md

   # Cách 2: Đọc qua Python
   python -c "
   from hermes.core.workspace import Workspace
   from hermes.core.storage import get_artifact, read_artifact_content
   ws = Workspace('/path/to/workspace')
   art = get_artifact(ws, 'lecture-lecture')
   print(read_artifact_content(ws, art))
   "
   ```

3. **Nếu artifact đã qua debate**, đọc verdict để xem lập luận 2 bên:
   ```bash
   python -c "
   from hermes.core.workspace import Workspace
   from hermes.core.storage import get_artifact, read_artifact_content
   ws = Workspace('/path/to/workspace')
   verdict = get_artifact(ws, 'lecture-lecture-debate')
   if verdict:
       print(read_artifact_content(ws, verdict))
   "
   ```

4. **Duyệt (approve)**:
   ```bash
   python -m hermes approve \
     --workspace /path/to/workspace \
     --artifact lecture-lecture \
     --version 1
   ```

5. **Từ chối (reject)**: Hiện tại chưa có lệnh reject riêng — artifact fail sẽ được retry tự động bởi pipeline. Nếu muốn bỏ qua, chỉ cần không approve và để pipeline chạy lại.

---

## 6. Giám sát hệ thống

### 6.1 Dashboard nhanh

```bash
python -m hermes dashboard --workspace /path/to/workspace
```

Hiển thị: tổng artifact, phân bố pass/fail/escalated, danh sách chờ duyệt, thống kê debate.

### 6.2 Cảnh báo artifact treo

```bash
# Kiểm tra thủ công
python -m hermes check-stale --workspace /path/to/workspace --threshold-hours 24

# Tự động hóa với cron (Linux/macOS):
# Thêm vào crontab:
# 0 9 * * * cd /path/to/hermes && python -m hermes check-stale --workspace /path/to/workspace --threshold-hours 24 || echo "Có artifact quá hạn!" | mail -s "Hermes Alert" admin@example.com
```

### 6.3 Đọc event log trực tiếp

Mọi sự kiện được ghi vào `workspace/.hermes/logs/events.jsonl` (định dạng JSONL):

```bash
# Xem toàn bộ
cat /path/to/workspace/.hermes/logs/events.jsonl

# Lọc theo artifact
grep "lecture-lecture" /path/to/workspace/.hermes/logs/events.jsonl

# Lọc theo loại sự kiện
grep '"verification_result"' /path/to/workspace/.hermes/logs/events.jsonl
```

Các loại sự kiện: `artifact_version_created`, `verification_result`, `debate_round_completed`, `debate_resolved`, `human_approval`.

---

## 7. Cấu trúc workspace

```
my-workspace/
  .hermes/
    config.json              # metadata workspace
    artifacts/
      index.json             # registry (id → bản ghi)
      bai-giang-01-lit_v1.md # artifact file
      bai-giang-01-outline_v1.md
      bai-giang-01-lecture_v1.md
      bai-giang-01-quiz_v1.md
      bai-giang-01-final_v1.md
    tasks/
      index.json             # task registry
    rubrics/                 # bản sao rubric (optional)
    logs/
      events.jsonl           # event log (append-only)
```

Mỗi workspace là độc lập — có thể có nhiều workspace cho các dự án khác nhau.

---

## 8. Xử lý sự cố thường gặp

### Pipeline dừng ở "escalated"

**Nguyên nhân:** Artifact high-risk qua rubric nhưng chưa được duyệt thủ công (human gate).

**Cách xử lý:** Duyệt thủ công bằng `python -m hermes approve` (xem mục 5).

### Artifact liên tục fail

1. Đọc `verification_notes`:
   ```bash
   python -c "
   from hermes.core.workspace import Workspace
   from hermes.core.storage import get_artifact
   ws = Workspace('/path/to/workspace')
   art = get_artifact(ws, '<artifact_id>')
   print(art['verification_notes'])
   "
   ```
2. Đọc event log để xem lịch sử trạng thái (mục 6.3)
3. Kiểm tra rubric — có thể cần điều chỉnh `pass_threshold` trong file `R-*.json`

### LLM provider không hoạt động

1. Kiểm tra provider đã đăng ký trong `hermes/core/llm_config.py`
2. Kiểm tra API key / kết nối local
3. Chạy thử:
   ```bash
   python -c "from hermes.core.llm_config import list_providers; print(list_providers())"
   ```

### Không tìm thấy rubric

Pipeline tự động load rubric từ package `hermes/rubrics/`. Nếu báo lỗi, kiểm tra:
```bash
ls hermes/rubrics/
# Phải có: R-lit-review-v2.json, R-course-outline-v1.json, R-lecture-draft-v1.json, R-quiz-bank-v1.json, R-debate-verdict-v1.json
```

### Test fail sau khi sửa code

```bash
# Chạy toàn bộ test
pytest tests/ -v

# Chạy test theo phase
pytest tests/test_phase4_observability.py -v

# Chạy 1 test cụ thể
pytest tests/test_phase4_observability.py::test_dashboard_counts_are_internally_consistent -v
```

---

## Phụ lục: Danh sách file quan trọng

| File | Chức năng |
|------|-----------|
| `hermes/core/workspace.py` | Quản lý workspace (thư mục dữ liệu) |
| `hermes/core/storage.py` | CRUD artifact (save, get, update, list) |
| `hermes/core/verifier.py` | Chấm điểm artifact theo rubric |
| `hermes/core/risk.py` | Risk matrix + ngưỡng điều chỉnh |
| `hermes/core/events.py` | Ghi log sự kiện nghiệp vụ |
| `hermes/pipeline/full_lecture_pipeline.py` | Pipeline đầy đủ 5 stage |
| `hermes/pipeline/lit_review_pipeline.py` | Pipeline rút gọn (literature review) |
| `hermes/pipeline/debate_review_task.py` | Debate review cho artifact high-risk |
| `hermes/agents/*.py` | 7 CrewAI agent |
| `hermes/rubrics/*.json` | 5 rubric chấm điểm |
| `hermes/schemas/*.json` | 3 JSON schema |
| `docs/OPERATIONS.md` | Tài liệu cho developer (thêm agent, rubric, debug) |
