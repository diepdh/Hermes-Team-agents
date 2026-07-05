# Hermes Phase 1 — Báo cáo xử lý blocker theo hướng dẫn reviewer

**Ngườii thực hiện:** Coder Agent  
**Ngày báo cáo:** 05/07/2026  
**Tài liệu tham chiếu:** `hermes-phase1-blocker-resolution.md`

---

## 1. Tóm tắt trạng thái

Reviewer yêu cầu ưu tiên xử lý blocker dependency và refactor `llm_config.py` thành registry đa provider trước khi chạy pipeline thật. Các hạng mục này đã được giải quyết; pipeline vẫn đang chờ chạy 3 lần với `opencode_go`.

| Mục | Trạng thái |
|---|---|
| Recreate venv sạch, `pip check` pass | ✅ Done |
| Refactor `llm_config.py` đa provider | ✅ Done |
| Cập nhật `.env` theo registry mới, xoá `/chat/completions` | ✅ Done |
| Xác định root cause `deepseek-v4-flash` content rỗng | ✅ Done |
| Chạy pipeline thật ≥3 lần với `opencode_go` | ⏳ Pending |
| Test `local_cx` | ⏳ Pending |
| Housekeeping Phase 0.5 | ⏳ Pending |

---

## 2. Chi tiết từng hạng mục

### 2.1 Recreate venv sạch (Checklist D1)

**Quy trình thực hiện:**

```bash
unset PYTHONPATH
rm -rf .venv
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install "crewai==1.15.1" crewai-tools python-dotenv pywin32 jsonschema pytest litellm
```

**Kết quả kiểm tra:**

```
No broken requirements found.
crewai version: 1.15.1
```

`requirements.txt` đã được ghi đè bằng bản sạch.

> **Lưu ý quan trọng:** Môi trường Hermes Agent thiết lập `PYTHONPATH` trỏ vào venv của chính nó. Nếu không `unset PYTHONPATH`, pip resolver sẽ nhầm các gói của Hermes Agent là đã có trong `.venv`, dẫn đến venv thiếu dependency và `pip check` báo lỗi hàng loạt. Đây là nguyên nhân gốc của version drift trước đó.

### 2.2 Refactor LLM Config (Checklist D2, D3)

`hermes/core/llm_config.py` đã được viết lại thành registry:

- `opencode_go` — OpenAI-compatible proxy hiện tại
- `local_cx` — local provider `cx` model `gpt-5.4`
- `anthropic` — endpoint mặc định Anthropic

`.env` mới:

```bash
HERMES_LLM_PROVIDER=opencode_go

OPENCODE_MODEL=deepseek-v4-flash
OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1
OPENCODE_API_KEY=sk-...
OPENCODE_TIMEOUT=120
OPENCODE_MAX_TOKENS=4000

CX_MODEL=gpt-5.4
CX_BASE_URL=http://100.90.2.127:20128/v1
CX_API_KEY=not-needed
CX_TIMEOUT=120
CX_MAX_TOKENS=4000

ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=
ANTHROPIC_TIMEOUT=120
ANTHROPIC_MAX_TOKENS=4000
```

`agents/researcher.py` và `pipeline/lit_review_pipeline.py` đã cập nhật để nhận tham số `provider`.

### 2.3 Root cause: `deepseek-v4-flash` trả `content` rỗng

Khi test trực tiếp OpenCode Go API với `max_tokens` thấp (10–100), response HTTP 200 nhưng `choices[0].message.content == ""`, chỉ có `reasoning_content`.

**Giả thuyết:** Model reasoning-first này dùng token để viết reasoning trước; nếu `max_tokens` không đủ, phần `content` bị cắt hoàn toàn.

**Xác minh:**

| max_tokens | content xuất hiện? |
|---|---|
| 10–100 | ❌ chỉ reasoning |
| 200 | ❌ chỉ reasoning |
| 400 | ❌ chỉ reasoning |
| 800 | ✅ content xuất hiện |
| 4000 | ✅ content đầy đủ (~2256 tokens) |

**Hành động:**
- Thêm `max_tokens` mặc định 4000 vào `llm_config.py`.
- Truyền `max_tokens` vào `LLM()` trong `agents/researcher.py`.
- Cài `litellm` để CrewAI nhận diện model string `openai/deepseek-v4-flash`.

---

## 3. Blocker còn lại / rủi ro

1. **Chưa chạy pipeline end-to-end với LLM thật.** Agent đã khởi tạo được (`agent llm: openai/deepseek-v4-flash`), nhưng `Crew.kickoff()` chưa được gọi thật.
2. **`local_cx` vẫn timeout** trong lần test trước (`http://100.90.2.127:20128`). Cần kiểm tra lại khi anh xác nhận server đang chạy.
3. **Baseline thật chưa có** — `logs/phase1_baseline.json` vẫn trống.

---

## 4. Đề xuất bước tiếp theo

Reviewer cần xác nhận một trong các phương án:

**A. Tiếp tục chạy pipeline thật với `opencode_go` ngay**
- Chạy 3 lần `run_lit_review_with_baseline(..., provider="opencode_go")`.
- Ghi baseline vào `logs/phase1_baseline.json`.
- Nếu pass → viết test Phase 1, chạy full suite, commit.

**B. Test `local_cx` trước khi chạy baseline**
- Anh xác nhận local `cx` server đang chạy ở `100.90.2.127:20128`.
- Em test 1 lần gọi đơn giản, sau đó quyết định provider nào dùng cho baseline.

**C. Dùng mock/fake LLM tạm thờii để unblock cấu trúc**
- Nếu anh muốn tách rủi ro "model lỗi" khỏi "pipeline lỗi", em sẽ chạy pipeline với mock LLM để xác nhận Task→Artifact→Verify→Retry hoạt động đúng.
- Sau đó mới chạy thật với `opencode_go`.

---

## 5. Checklist reviewer D1–D6

| # | Hạng mục | Đạt? |
|---|---|---|
| D1 | `pip check` sạch hoàn toàn sau recreate venv | ✅ |
| D2 | `.env` đã bỏ `/chat/completions` khỏi base_url | ✅ |
| D3 | `llm_config.py` refactor thành registry, ≥2 provider | ✅ |
| D4 | Test gọi thật thành công cả `opencode_go` và `local_cx` | ⏳ `opencode_go` API OK, CrewAI agent OK; `local_cx` timeout; pipeline thật chưa chạy |
| D5 | `logs/phase1_baseline.json` tách theo provider | ⏳ file chưa có |
| D6 | Biến `.env` không dùng (`PORT=3000`) đã xử lý | ✅ Đã xoá `PORT=3000` |

---

## 6. Thông tin kỹ thuật bổ sung

- Python: 3.11.15
- CrewAI: 1.15.1
- Pydantic: 2.12.5
- OpenAI: 2.44.0
- portalocker: 2.7.0
- litellm: 1.91.0 (cài thêm để hỗ trợ model string `openai/deepseek-v4-flash`)

Commit gần nhất trước báo cáo này: `86dd78e520cf85da34bc1032e07e06a0d59a3206` (WIP Phase 1).
