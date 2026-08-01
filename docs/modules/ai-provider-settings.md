# AI Provider Settings

## Responsibility

- Lưu OpenAI-compatible provider cho từng worker và đồng bộ sang Hermes `config.yaml`.
- Hỗ trợ provider trực tiếp, 9router, OpenRouter hoặc CLIProxyAPI thông qua `base_url`, `model`, `api_key`.

## Entry Points

- API/UI: `backend/app/api/ai.py`, `backend/app/templates/ai_copilot.html`, `backend/app/static/ai_copilot.js`.
- Encryption: `backend/app/services/ai_settings.py`.
- Worker sync: `workers/agent/hermes_config.py` và endpoint runtime theo per-node credential.

## Invariants

- API key mã hóa bằng Fernet và không trả raw value cho user API.
- Config `execution_scope=worker` phải có worker thuộc đúng tenant.
- Remote non-localhost endpoint cần API key; localhost proxy được phép để trống.
- Hermes config và managed hash có mode `0600`; service chỉ start sau lần sync config hợp lệ.

## Current State

- Hermes Agent `v0.19.1` có trên worker production hiện tại nhưng đang inactive cho tới khi cấu hình provider.
- Preset mặc định hiển thị DeepSeek V4 Flash 0731; OpenAI-compatible endpoint là `https://api.deepseek.com` và API model ID canonical là `deepseek-v4-flash`.
- Production API key đã lưu encrypted; `/models` và Chat Completions đều trả `200`, Hermes gateway đang active.
