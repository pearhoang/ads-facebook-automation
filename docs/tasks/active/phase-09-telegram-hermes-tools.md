# Phase 9 - Telegram, Hermes Và Typed Tools

## Goal

- Cho phép người dùng trò chuyện tự nhiên với Hermes trên Telegram.
- Hermes đọc KPI, ad account và campaign qua typed tools của control-plane.
- Thêm cấu hình thinking/reasoning theo worker và đồng bộ vào Hermes.

## Scope

- `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/api/*`, `backend/app/services/*`.
- `workers/agent/hermes_config.py`, MCP bridge và worker runtime config.
- UI `AI Copilot` và popup sửa/cài `Bot VPS`.
- Alembic, systemd/bootstrap, tests và production deployment.

## Constraints

- Telegram là chat tự nhiên; slash command chỉ là tiện ích.
- Agent không truy cập database hoặc worker browser trực tiếp.
- Tool có mutation chỉ tạo control-plane draft; không submit approval, không chạy browser và không publish.
- Telegram allowlist bắt buộc; token và worker credential không xuất hiện trong UI/log/API response.
- Cấu hình reasoning phải dùng giá trị Hermes hỗ trợ và không giả định mọi provider có cùng thinking wire format.

## Current State

- Hermes gateway đang active với DeepSeek V4 Flash 0731 nhưng chưa bật messaging platform.
- Provider config đã mã hóa theo worker; chưa có reasoning fields hoặc MCP control-plane tools.
- Reporting Telegram hiện dùng `sendMessage` deterministic và có thể dùng chung bot token với gateway polling.

## Next Steps

- Migration và UI reasoning.
- Typed tool facade + local MCP stdio bridge.
- Telegram token/allowlist sync vào Hermes `.env` và smoke test hội thoại/tool discovery.

## Risks

- Hai process cùng poll `getUpdates` trên một bot token sẽ xung đột; chỉ Hermes gateway được poll, reporter chỉ gọi `sendMessage`.
- DeepSeek thinking tool-call loop phải giữ `reasoning_content`; giao việc này cho Hermes runtime thay vì tự viết agent loop.
- Không bật full `hermes-telegram` terminal toolset cho production ads bot.
