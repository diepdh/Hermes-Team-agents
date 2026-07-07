# Hermes Engineering OS — Tài liệu vận hành

Tài liệu hướng dẫn mở rộng và vận hành hệ thống Hermes Engineering OS.
Viết dựa trên code thật hiện có, không giả định.

---

## 1. Cách thêm subagent mới

### 1.1 Tạo file agent mới

Tạo file `hermes/agents/<ten>.py`. Pattern cơ bản của một agent (tham khảo `hermes/agents/editor.py` làm mẫu):

```python
"""Agent description."""

from crewai import Agent, Task


def build_<ten>_agent(provider: str | None = None) -> Agent:
    """Build and return the agent."""
    from hermes.core.llm_config import _build_llm
    llm = _build_llm(provider) if provider else None
    return Agent(
        role="...",
        goal="...",
        backstory="...",
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )


def build_<ten>_task(
    agent: Agent,
    output_path: str,
    # ... input params specific to this agent
) -> Task:
    """Build the task for this agent."""
    return Task(
        description="...",
        expected_output="...",
        agent=agent,
        output_file=output_path,
    )
```

### 1.2 Nếu subagent tạo ra artifact type mới

Phải thực hiện đủ các bước sau, nếu không sẽ fail test hiện có:

1. **Thêm vào schema**: Thêm giá trị mới vào enum `type` trong `hermes/schemas/artifact.schema.json`.
   ```json
   "type": { "enum": ["lit_review_md", "course_outline", "lecture_draft", "quiz_bank", "debate_verdict", "<type_moi>"] }
   ```

2. **Thêm rubric**: Tạo file `hermes/rubrics/R-<type_moi>-v1.json` với cấu trúc:
   ```json
   {
     "id": "R-<type_moi>-v1",
     "artifact_type": "<type_moi>",
     "version": 1,
     "pass_threshold": 0.70,
     "criteria": [
       { "name": "...", "weight": 0.5, "description": "..." },
       { "name": "...", "weight": 0.5, "description": "..." }
     ]
   }
   ```

3. **Đăng ký checker**: Thêm hàm checker vào `hermes/core/verifier.py` và đăng ký bằng decorator `@checker_for("<type_moi>")`.
   ```python
   @checker_for("<type_moi>")
   def check_<type>(content: str, rubric: dict) -> dict:
       scores = {}
       # ... logic chấm điểm ...
       return _build_result(scores, rubric)
   ```

4. **⚠️ Đăng ký vào RISK_MATRIX (dễ quên nhất)**: Thêm entry vào `RISK_MATRIX` trong `hermes/core/risk.py`.
   ```python
   RISK_MATRIX = {
       # ... existing entries ...
       "<type_moi>": "medium",
   }
   ```
   Nếu quên bước này, test `test_all_artifact_types_have_risk_level` (Phase 3) sẽ fail ngay lập tức.

5. **Nếu type là high/critical**: Cân nhắc thêm vào `HUMAN_GATE_TYPES` trong `verifier.py` nếu cần duyệt thủ công.

### 1.3 Nối vào pipeline

Thêm stage mới vào pipeline tương ứng (VD `hermes/pipeline/full_lecture_pipeline.py`), sử dụng helper `run_stage()`:

```python
result = run_stage(
    workspace=ws,
    agent_builder=build_<ten>_agent,
    task_builder=lambda a, output_path: build_<ten>_task(a, ..., output_path=output_path),
    artifact_type="<type_moi>",
    rubric=rubric_<type>,
    produced_by_task=f"{task_id_prefix}-<slug>",
    provider=provider,
    max_retries=2,
)
```

### 1.4 Viết test tối thiểu

Trong `tests/test_phase2.py` (hoặc file test mới):
- Test agent khởi tạo được (không crash).
- Test task sinh đúng `output_schema` / `expected_output`.
- Test checker trả về đúng shape (`passed`, `score`, `detail`).

---

## 2. Cách thêm rubric mới

### 2.1 Tạo file rubric JSON

Tạo file `hermes/rubrics/R-<type>-v<version>.json`:

```json
{
  "id": "R-<type>-v1",
  "artifact_type": "<type>",
  "version": 1,
  "pass_threshold": 0.70,
  "criteria": [
    { "name": "criterion_1", "weight": 0.5, "description": "..." },
    { "name": "criterion_2", "weight": 0.5, "description": "..." }
  ]
}
```

Các rubric hiện có:
- `R-lit-review-v2.json`
- `R-course-outline-v1.json`
- `R-lecture-draft-v1.json`
- `R-quiz-bank-v1.json`
- `R-debate-verdict-v1.json`

### 2.2 Đăng ký trong `load_rubric()`

File `hermes/rubrics/__init__.py` đã có cơ chế glob fallback cho file `R-*.json`, nên nếu rubric mới tuân theo pattern đặt tên `R-<type>-v1.json`, nó sẽ tự động được load qua `load_rubric("<type>")`.

Nếu artifact type không khớp pattern, thêm entry vào mapping `_TYPE_TO_FILE`:

```python
_TYPE_TO_FILE = {
    "lit_review_md": "R-lit-review-v2.json",
    "course_outline": "R-course-outline-v1.json",
    "lecture_draft": "R-lecture-draft-v1.json",
    "quiz_bank": "R-quiz-bank-v1.json",
    "debate_verdict": "R-debate-verdict-v1.json",
    "<type_moi>": "R-<type_moi>-v1.json",
}
```

### 2.3 Thêm checker và đăng ký

Thêm hàm check vào `CHECKER_REGISTRY` trong `hermes/core/verifier.py` (xem mục 1.2 bước 3).

### 2.4 ⚠️ Viết test `test_rubric_criteria_names_match_verifier_<type>`

Bài học từ Phase 1 mục 6.3: tên tiêu chí trong rubric JSON và tên biến trong code chấm điểm **phải khớp chính xác**. Nếu không, tiêu chí sẽ bị bỏ qua thinh lặng (score = 0.0). Viết test guard:

```python
def test_rubric_criteria_names_match_verifier_<type>():
    rubric = load_rubric("<type_moi>")
    # Gọi checker với content hợp lệ, assert mọi criterion name có trong result['detail']
    result = check_<type>(valid_content, rubric)
    for c in rubric["criteria"]:
        assert c["name"] in result["detail"], f"Missing: {c['name']}"
```

---

## 3. Cách debug 1 Task fail

### 3.1 Đọc verification_notes của artifact

```bash
python -c "
from hermes.core.workspace import Workspace
from hermes.core.storage import get_artifact
ws = Workspace('/path/to/workspace')
art = get_artifact(ws, '<artifact_id>')
print('Status:', art['verification_status'])
print('Notes:', art['verification_notes'])
"
```

`verification_notes` chứa thông tin chi tiết về lý do pass/fail/escalated, bao gồm risk level, rubric score, và debate verdict nếu có.

### 3.2 Đọc event log (Phase 4)

```bash
python -m hermes dashboard --workspace /path/to/workspace
```

Hoặc đọc trực tiếp:

```bash
cat /path/to/workspace/.hermes/logs/events.jsonl | grep "<artifact_id>"
```

Event log (JSONL) chứa toàn bộ lịch sử trạng thái của artifact: khi nào được tạo (`artifact_version_created`), khi nào được verify (`verification_result`), và nếu có debate thì từng vòng (`debate_round_completed`) và kết quả cuối (`debate_resolved`).

### 3.3 Kiểm tra retry_count vs max_retries

Retry count được ghi nhận trong `verification_notes` dưới dạng `attempt N`. Nếu artifact vẫn fail sau `max_retries`, nó sẽ được escalated.

Logic retry nằm trong `run_stage()` (`hermes/pipeline/full_lecture_pipeline.py:179-243`).

### 3.4 Nếu liên quan debate

Nếu artifact là high/critical risk và đã trải qua debate, đọc verdict:

```bash
python -c "
from hermes.core.workspace import Workspace
from hermes.core.storage import get_artifact, read_artifact_content
ws = Workspace('/path/to/workspace')
verdict = get_artifact(ws, '<artifact_id>-debate')
if verdict:
    content = read_artifact_content(ws, verdict)
    print(content)
"
```

Debate verdict artifact được lưu với ID `{artifact_id}-debate`, chứa toàn bộ lập luận của proponent/opponent qua từng vòng và `final_decision`.

### 3.5 Kiểm tra artifact escalated quá lâu (Phase 4)

```bash
python -m hermes check-stale --workspace /path/to/workspace --threshold-hours 24
```

Lệnh này liệt kê mọi artifact đang ở trạng thái `escalated` kèm thời gian chờ. Exit code 1 nếu có artifact quá hạn → dùng được trong CI/cron.

---

## 4. Cấu trúc thư mục workspace

Mỗi Hermes workspace là một thư mục với cấu trúc:

```
<workspace>/
  .hermes/
    config.json           # workspace metadata
    artifacts/
      index.json          # artifact registry (id -> record)
      <id>_v<ver>.md      # versioned artifact files
    tasks/
      index.json          # task registry
    rubrics/              # local rubric copies (optional)
    logs/
      events.jsonl        # append-only event log (Phase 4)
```

---

## 5. Các CLI command

| Command | Mô tả |
|---------|-------|
| `python -m hermes init --workspace <path>` | Khởi tạo workspace mới |
| `python -m hermes approve --workspace <path> --artifact <id> --version <v>` | Duyệt thủ công artifact escalated |
| `python -m hermes dashboard --workspace <path>` | In bảng tổng quan observability |
| `python -m hermes check-stale --workspace <path> --threshold-hours <h>` | Kiểm tra artifact escalated quá hạn |

---

## 6. Kiến trúc tổng quan

```
User Request
    │
    ▼
main.py / run_baseline.py
    │
    ▼
hermes/pipeline/full_lecture_pipeline.py  ← run_stage() × 5 stages
    │
    ├── hermes/agents/*.py               ← CrewAI Agents
    ├── hermes/core/verifier.py          ← rule-based scoring + finalize_verification
    ├── hermes/core/storage.py           ← file-based artifact store
    ├── hermes/core/risk.py              ← risk matrix + debate trigger logic
    ├── hermes/core/events.py            ← append-only event log (Phase 4)
    ├── hermes/pipeline/debate_review_task.py  ← bounded debate for high-risk
    └── hermes/rubrics/*.json            ← scoring rubrics
```

**Nguyên tắc cốt lõi:**
- `finalize_verification()` là **single source of truth** cho mọi quyết định status.
- `log_event()` chỉ gọi ở **3 nơi**: `finalize_verification()`, `save_artifact()`, `run_debate_review()` — không rải thêm.
- Không thêm field mới vào Artifact Schema chỉ để lưu metadata thời gian — dùng event log.
