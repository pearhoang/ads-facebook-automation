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

## Remaining production check

- Deploy source/installer/service env lên worker hiện tại.
- User hoàn tất device login bằng link/code.
- Smoke `codex_search` với truy vấn có nguồn và `codex_vision` với một ảnh test; xác nhận DeepSeek gọi đúng tool từ Telegram/Hermes Dashboard.
