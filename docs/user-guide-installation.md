# Hermes Engineering OS — Hướng dẫn cài đặt (lần đầu)

Hướng dẫn từng bước cài đặt Hermes Engineering OS trên máy mới, chưa có gì.

---

## 1. Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu |
|---|---|
| **Python** | 3.10 – 3.13 |
| **pip** | ≥ 23.0 |
| **Git** | Bất kỳ phiên bản nào |
| **Hệ điều hành** | Windows 10+, macOS 12+, Ubuntu 20.04+ |
| **RAM** | ≥ 8GB (khuyến nghị 16GB cho pipeline đầy đủ) |
| **Ổ đĩa** | ≥ 2GB trống |
| **LLM Provider** | Ít nhất 1 trong: OpenAI API key, local server (OpenCode Go / vLLM), Anthropic API key |

> **Lưu ý:** Nếu dùng local LLM (không cần API key bên ngoài), máy cần GPU với ≥ 8GB VRAM hoặc CPU đủ mạnh cho inference.

---

## 2. Clone repository

```bash
git clone https://github.com/diepdh/Hermes-Team-agents.git
cd Hermes-Team-agents
```

---

## 3. Tạo môi trường ảo + cài dependencies

### Cách 1: Dùng `uv` (khuyến nghị — nhanh hơn)

```bash
# Cài uv nếu chưa có
pip install uv

# Tạo venv + cài tất cả dependencies chỉ 1 lệnh
uv sync
```

### Cách 2: Dùng `pip` + `venv` truyền thống

```bash
# Tạo virtual environment
python -m venv .venv

# Kích hoạt
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Cài dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 4. Cấu hình LLM Provider

Hermes cần ít nhất 1 LLM provider để chạy. Mở file `.env` trong thư mục gốc (tạo mới nếu chưa có).

### Option A: Dùng local server (OpenCode Go — không cần API key)

```bash
# .env
HERMES_LLM_PROVIDER=opencode_go
OPENCODE_MODEL=deepseek-v4-pro
OPENCODE_BASE_URL=http://localhost:8080/v1
OPENCODE_API_KEY=not-needed
```

### Option B: Dùng OpenAI

```bash
# .env
HERMES_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
```

### Option C: Dùng Anthropic Claude

```bash
# .env
HERMES_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### Option D: Custom provider qua OpenAI-compatible API

```bash
# .env
HERMES_LLM_PROVIDER=local_cx
HERMES_LOCAL_CX_MODEL=cx/gpt-5.4-mini
HERMES_LOCAL_CX_BASE_URL=http://100.90.2.127:20128/v1
HERMES_LOCAL_CX_API_KEY=not-needed
```

---

## 5. Kiểm tra cài đặt

```bash
# Kiểm tra import
python -c "import hermes; print('Hermes OK')"

# Kiểm tra LLM provider
python -c "from hermes.core.llm_config import get_llm_config; c = get_llm_config(); print('Provider:', c['provider'], '| Model:', c['model'])"

# Chạy toàn bộ test suite
uv run pytest tests/ -q
# Kỳ vọng: 88 passed (tính đến P5.7b)
```

---

## 6. Cấu trúc thư mục sau cài đặt

```
Hermes-Team-agents/
  ├── .env                    ← Bạn tạo file này (LLM config)
  ├── .venv/                  ← Virtual environment
  ├── hermes/                 ← Code chính
  │   ├── agents/             ← 15+ subagent
  │   ├── core/               ← storage, verifier, risk, sandbox...
  │   ├── pipeline/           ← lecture + paper pipelines
  │   ├── rubrics/            ← 10+ rubric JSON
  │   └── schemas/            ← JSON schema
  ├── tests/                  ← 88+ unit tests
  ├── docs/                   ← Tài liệu hướng dẫn
  └── scripts/                ← Script demo + test LLM thật
```

---

## 7. Xử lý sự cố cài đặt

### `ModuleNotFoundError: No module named 'hermes'`

Chạy `pip install -e .` từ thư mục gốc để cài package ở chế độ editable.

### `ImportError: No module named 'crewai'`

CrewAI chưa được cài. Chạy `pip install crewai` hoặc `uv sync`.

### LLM không gọi được

1. Kiểm tra file `.env` đã đúng tên biến chưa (phân biệt hoa/thường)
2. Provider đã được chọn qua `HERMES_LLM_PROVIDER`
3. Test kết nối:
   ```bash
   python -c "
   from hermes.core.llm_config import get_llm
   llm = get_llm()
   print(llm.call('Say hello in one word'))
   "
   ```

### `RuntimeError: Missing env var` khi chạy pipeline

Một số provider cần biến môi trường cụ thể. Xem danh sách trong `hermes/core/llm_config.py` → `PROVIDER_REGISTRY`.

---

## 8. Cài đặt Hermes Desktop (tuỳ chọn — khuyến nghị)

Hermes Engineering OS chạy trên nền **Hermes Agent** — 1 AI agent framework mạnh mẽ. Bạn có thể dùng qua CLI hoặc qua Hermes Desktop (ứng dụng giao diện Electron).

### Cài Hermes Agent

```bash
# Cài qua script chính thức (tự động cài uv, Python, venv, launcher)
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Hoặc cài qua pip
pip install hermes-agent
```

### Chạy Hermes Desktop

```bash
# Khởi động desktop app
hermes desktop

# Alias ngắn hơn
hermes gui
```

Tính năng của Hermes Desktop:
- **Chat streaming** — giao diện chat với AI agent, thấy tool call realtime
- **Session list** — quản lý nhiều phiên làm việc song song
- **Drag & drop** — kéo thả file, ảnh vào chat
- **Cmd+K palette** — tìm lệnh nhanh
- **Model picker** trên thanh trạng thái
- **Subagent watch-window** — theo dõi agent con đang chạy

### Tích hợp Engineering OS với Hermes Desktop

Sau khi cài Hermes Agent, mở Desktop và clone repo Engineering OS:

```bash
# Trong terminal của Hermes Desktop (hoặc terminal thường)
git clone https://github.com/diepdh/Hermes-Team-agents.git
cd Hermes-Team-agents

# Cài dependencies của Engineering OS
uv sync

# Tạo file .env cấu hình LLM (xem mục 4)
```

Sau đó, mở thư mục `Hermes-Team-agents` trong Hermes Desktop — agent sẽ tự động đọc `AGENTS.md` / `CLAUDE.md` và có sẵn toàn bộ pipeline.

> **Mẹo:** Dùng **profiles** của Hermes để tách biệt môi trường: 1 profile cho soạn bài giảng, 1 profile cho viết paper. Xem thêm tại [Hermes docs](https://hermes-agent.nousresearch.com/docs/).

## 9. Bước tiếp theo

- **[Hướng dẫn soạn bài giảng](./user-guide-lecture.md)** — Dùng pipeline tạo giáo trình tự động
- **[Hướng dẫn viết bài báo khoa học](./user-guide-paper.md)** — Dùng pipeline P5.7 viết/cải thiện research paper
