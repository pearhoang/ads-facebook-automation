# Phase 11 — Codex Search & Vision fallback

## Goal

- Cho Hermes/DeepSeek gọi search và vision qua Codex OAuth theo từng worker mà không cần noVNC hoặc ChatGPT browser cookie.

## Contract

- UI: `Hermes Agents` → `Codex Search & Vision` → `Kết nối Codex`.
- Auth: `codex login --device-auth`, token chỉ ở `<WORKER_DATA_DIR>/codex/auth.json` mode `0600`.
- Runtime: MCP stdio `workers.agent.codex_capabilities_mcp` có `codex_search`, `codex_vision`.
- Status: heartbeat `capabilities_json.codex`; control-plane không nhận raw OAuth token.
- Safety: search/vision read-only; vision chỉ đọc ảnh dưới allowed worker roots; Meta publish/budget boundary giữ nguyên.

## Remaining production check

- Deploy source/installer/service env lên worker hiện tại.
- User hoàn tất device login bằng link/code.
- Smoke `codex_search` với truy vấn có nguồn và `codex_vision` với một ảnh test; xác nhận DeepSeek gọi đúng tool từ Telegram/Hermes Dashboard.
