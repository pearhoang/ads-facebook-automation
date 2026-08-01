# AI Provider Settings

## Responsibility

- Lưu OpenAI-compatible provider, thinking/reasoning cho từng worker và đồng bộ sang Hermes.
- Hỗ trợ provider trực tiếp, 9router, OpenRouter hoặc CLIProxyAPI thông qua `base_url`, `model`, `api_key`.
- Nạp Telegram conversational gateway, localhost Hermes API Server và MCP bridge tới typed tools của control-plane.

## Entry Points

- API/UI: `backend/app/api/ai.py`, `backend/app/templates/hermes_agents.html`, `backend/app/static/hermes_agents.js`.
- Encryption: `backend/app/services/ai_settings.py`.
- Worker sync: `workers/agent/hermes_config.py` và endpoint runtime theo per-node credential.
- MCP bridge: `workers/agent/control_plane_mcp.py`; typed facade: `backend/app/services/agent_tools.py`.

## Invariants

- API key mã hóa bằng Fernet và không trả raw value cho user API.
- Config `execution_scope=worker` phải có worker thuộc đúng tenant.
- Remote non-localhost endpoint cần API key; localhost proxy được phép để trống.
- Hermes config và managed hash có mode `0600`; service chỉ start sau lần sync config hợp lệ.
- Hermes API Server chỉ bind `127.0.0.1:8642`; bearer key riêng nằm trên worker mode `0600` và không đi qua browser/control-plane.
- Telegram phải có `TELEGRAM_ALLOWED_USERS`; không dùng `GATEWAY_ALLOW_ALL_USERS`. Add Bot yêu cầu token và allowlist ngay từ đầu để gateway dùng được mà không cần SSH cấu hình tay.
- Telegram Bot Token chỉ được bootstrap vào worker env mode `0600`; không lưu trong database, audit, operation response hoặc command line.
- Agent tools chỉ nhận per-node credential và chỉ thấy ad account thuộc worker đó.
- `ads_create_campaign_draft` chỉ tạo control-plane `DRAFT`; không submit/publish.

## Current State

- Hermes Agent `v0.19.1` có trên worker production hiện tại và gateway đang active.
- Preset mặc định hiển thị DeepSeek V4 Flash 0731; OpenAI-compatible endpoint là `https://api.deepseek.com` và API model ID canonical là `deepseek-v4-flash`.
- Production API key đã lưu encrypted; `/models` và Chat Completions đều trả `200`, Hermes gateway đang active.
- UI hỗ trợ `auto|enabled|disabled` và effort `provider_default|minimal|low|medium|high|xhigh|max|ultra`.
- Provider/model có một canonical UI tại `Hermes Agents`; popup sửa Bot VPS chỉ sửa identity/SSH, còn popup cài mới vẫn nhận initial provider bootstrap.
