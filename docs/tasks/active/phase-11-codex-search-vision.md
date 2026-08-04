# Phase 11 — Codex Search & Vision fallback

## Goal

- Cho Hermes/DeepSeek gọi search và vision qua Codex OAuth theo từng worker mà không cần noVNC hoặc ChatGPT browser cookie.

## Contract

- UI: `Hermes Agents` → `Codex Search & Vision` → `Kết nối Codex`.
- Auth: `codex login --device-auth`, token chỉ ở `<WORKER_DATA_DIR>/codex/auth.json` mode `0600`.
- Runtime: MCP stdio `workers.agent.codex_capabilities_mcp` có `codex_search`, `codex_vision`.
- Upgrade: managed Hermes config schema phải tăng khi MCP contract đổi để node hiện hữu không bị short-circuit bởi provider hash cũ.
- Status: heartbeat `capabilities_json.codex`; control-plane không nhận raw OAuth token.
- Device prompt: parser chấp nhận code Codex CLI hiện tại dạng `XXXX-XXXXX` và legacy `XXXX-XXXX`; dialog hiển thị code riêng kèm action sao chép.
- Account lifecycle: `Ngắt kết nối` chạy `codex logout`, xóa exact `auth.json`, giữ disconnect marker chống refresh race; sau đó có thể device login bằng account khác.
- Remote access: device login/disconnect dùng SSH credential đã mã hóa theo worker; UI không hỏi lại password và API không trả secret.
- Safety: search/vision read-only; vision chỉ đọc ảnh dưới allowed worker roots; Meta publish/budget boundary giữ nguyên.

## Production verification 2026-08-04

- Worker heartbeat báo Codex `configured=true`, nhận diện account và plan `plus`; MCP test khám phá đủ `codex_search`, `codex_vision`.
- Search smoke dùng `deepseek-v4-flash`: DeepSeek tự gọi `mcp__codex_capabilities__codex_search` hai lần, trả lời có ba URL nguồn truy cập được. Session smoke source `tool` đã xóa sau kiểm thử.
- Vision smoke đi đúng Telegram session `20260801_190044_4241613b`: ảnh được lưu vào Hermes cache, DeepSeek mô tả schema rồi gọi `mcp__codex_capabilities__codex_vision` một lần và trả đúng nội dung ảnh cùng marker `KIEMTHU-VISION-804`.
- Hai follow-up Telegram không kèm ảnh vẫn nhớ vai trò Meta Ads, workspace, marker và cảnh ảnh; `vision` call count giữ nguyên một, chứng minh dùng context thay vì đọc lại ảnh.
- Bốn service giữ `active`, Hermes PID/start timestamp không đổi và public health vẫn `ok`. DeepSeek có `503 Service is too busy` ngắn hạn nhưng Hermes retry thành công, không mất session/tool result.
