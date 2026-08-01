# AI Copilot Conversation Bridge

## Responsibility

- Cung cấp chat Meta Ads trên web bằng đúng Hermes runtime/session đang dùng cho Telegram.
- Mirror conversation/message vào control-plane để áp tenant authorization, audit và UI history.
- Chuyển chat/sync thành outbound `AgentJob`; control-plane không gọi ngược vào localhost của worker.

## Entry Points

- User API: `backend/app/api/copilot.py`.
- State/service: `backend/app/services/agent_chat.py`.
- Worker API: `backend/app/api/worker.py` (`agent-jobs/poll|sync`).
- Worker bridge: `workers/agent/agent_bridge.py`.
- UI: `backend/app/templates/ai_copilot.html`, `backend/app/static/ai_copilot.js`, `backend/app/static/copilot.css`.
- Migration: `20260801_0008_agent_copilot_sessions`.

## Invariants

- Product chỉ có Ads Copilot; không nhúng VPS Copilot hoặc broad server administration vào SaaS Ads.
- `profile=ads` là giá trị duy nhất được user API chấp nhận.
- Worker gọi Hermes qua `127.0.0.1:8642` với key local mode `0600`; API không public và key không sync về control-plane.
- Telegram session được resume bằng exact `hermes_session_id`; không tạo transcript giả hoặc conversation context riêng.
- Natural language luôn dùng được. UI chỉ render tối đa hai shortcut khi assistant message có explicit `metadata_json.shortcuts`.
- Slash shortcut Web chỉ gồm `/help`, `/new`, `/sync`, `/status`; API session chat của Hermes không dispatch messaging slash command.
- Attachment Web chỉ nhận tối đa ba tệp TXT/MD/CSV/JSON/YAML UTF-8, 128 KB/tệp và 256 KB tổng. Binary không persist; transcript chỉ giữ metadata, còn nội dung gửi Hermes được đánh dấu untrusted reference data.
- Transcript user API/UI chỉ trả `user|assistant`; message Hermes role `tool|session_meta` là runtime nội bộ và không được render như câu trả lời.
- Assistant content render Markdown theo safe DOM subset; không đưa raw HTML từ model vào DOM.
- Agent vẫn chỉ có typed Ads tools. Action tiêu tiền giữ DRAFT/approval boundary của control-plane.
- Một conversation chỉ có một active `chat_turn`; job có lease, retry/outbox theo worker contract.
- Public job error không lộ localhost URL hoặc response nội bộ; chẩn đoán chi tiết chỉ ghi worker journal.

## Current State

- Web tạo chat mới, gửi turn, poll trạng thái và mirror assistant response.
- Session sync import title/source/messages từ Hermes, gồm session Telegram hiện hữu.
- UI có conversation list, source badge, composer natural-first và trạng thái Hermes đang xử lý.
- Sync nền không khóa composer/new chat; chat turn mới khóa riêng conversation cho đến khi terminal.
- Workspace khóa page scroll, chỉ message/session list được scroll; đổi session dùng request guard để response cũ không ghi đè selection mới.
- Composer có attachment queue và command palette chỉ hiện khi gõ `/`; DeepSeek V4 text-only nên chưa nhận image/PDF.
- Hermes systemd nạp cả `/etc/meta-ads-copilot/worker.env` và Hermes home `.env`, bảo đảm API Server thấy custom provider credential.
- Virtual model `ads-copilot` phải có `gateway.api_server.extra.model_routes` trỏ tới exact named provider/model của worker; không để session persist alias rồi Hermes tái phân giải thành bare `custom`.
