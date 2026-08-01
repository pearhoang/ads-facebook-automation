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

- Production đã chạy Hermes gateway với Telegram allowlist chính xác, DeepSeek V4 Flash 0731 và reasoning theo worker.
- Hermes đã kết nối MCP stdio bridge, khám phá đủ 5 typed tools và gọi read-only `ads_workspace_context` thành công.
- Telegram outbound smoke đạt; message thường được gateway xử lý theo session hội thoại, slash command chỉ là tiện ích.
- Reporting Telegram vẫn dùng `sendMessage` deterministic; chỉ Hermes gateway poll inbound update.

## Next Steps

- User trả lời tin nhắn smoke trên Telegram để xác nhận inbound session và tiếp tục kiểm thử giữ ngữ cảnh qua nhiều lượt.
- Phase sau bổ sung conversational approval handoff và narrative KPI; vẫn không cấp tool publish hoặc budget mutation.

## Risks

- Hai process cùng poll `getUpdates` trên một bot token sẽ xung đột; chỉ Hermes gateway được poll, reporter chỉ gọi `sendMessage`.
- DeepSeek thinking tool-call loop phải giữ `reasoning_content`; giao việc này cho Hermes runtime thay vì tự viết agent loop.
- Không bật full toolset theo mặc định. Chỉ worker được owner chọn `Experimental Full Access` mới gỡ các block terminal/file/code/browser/computer/delegation; quyết định này có cảnh báo, audit và đảo ngược được về `Ads Safe`.
