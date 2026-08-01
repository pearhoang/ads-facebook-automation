# AI Provider Settings

## Responsibility

- Lưu OpenAI-compatible provider, thinking/reasoning và permission mode cho từng worker rồi đồng bộ sang Hermes.
- Hỗ trợ provider trực tiếp, 9router, OpenRouter hoặc CLIProxyAPI thông qua `base_url`, `model`, `api_key`.
- Nạp Telegram conversational gateway, localhost Hermes API Server và MCP bridge tới typed tools của control-plane.

## Entry Points

- API/UI: `backend/app/api/ai.py`, `backend/app/templates/hermes_agents.html`, `backend/app/static/hermes_agents.js`.
- Encryption: `backend/app/services/ai_settings.py`.
- Worker sync: `workers/agent/hermes_config.py` và endpoint runtime theo per-node credential.
- MCP bridge: `workers/agent/control_plane_mcp.py`; typed facade: `backend/app/services/agent_tools.py`.
- Native dashboard: `infra/systemd/meta-ads-copilot-hermes-dashboard.service`, bind nội bộ và reverse proxy HTTPS riêng.
- Dashboard credential rotation: `POST /api/bot-nodes/{worker_id}/hermes-dashboard/password` và `backend/app/services/remote_ops.py`.

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
- `agent_permission_mode=ads_safe` là mặc định. `experimental_full` chỉ được bật chủ động theo từng worker và chỉ gỡ sáu toolset block do Ads Lush quản lý.
- Experimental Full Access không mở thêm typed tool publish/budget và không thay approval boundary của control-plane.
- Dashboard dùng auth provider chính chủ của Hermes; password chỉ lưu dạng scrypt hash và signing secret nằm trong env mode `0600`.
- Đổi Dashboard password yêu cầu owner session + CSRF + SSH password dùng một lần; thao tác xoay cả signing secret để revoke phiên cũ và không restart gateway/worker.
- Port dashboard không bind public interface. Caddy chỉ truy cập qua Docker host interface và HTTPS subdomain.

## Current State

- Hermes Agent `v0.19.1` có trên worker production hiện tại và gateway đang active.
- Preset mặc định hiển thị DeepSeek V4 Flash 0731; OpenAI-compatible endpoint là `https://api.deepseek.com` và API model ID canonical là `deepseek-v4-flash`.
- Production API key đã lưu encrypted; `/models` và Chat Completions đều trả `200`, Hermes gateway đang active.
- UI hỗ trợ `auto|enabled|disabled` và effort `provider_default|minimal|low|medium|high|xhigh|max|ultra`.
- UI hỗ trợ `Ads Safe` và `Experimental Full Access`; cảnh báo rõ quyền terminal/file/code/browser/computer/delegation của service trên VPS và yêu cầu session mới hoặc `/reset`.
- Provider/model có một canonical UI tại `Hermes Agents`; popup sửa Bot VPS chỉ sửa identity/SSH, còn popup cài mới vẫn nhận initial provider bootstrap.
- Worker production `Ads Browser VPS 82` hiện được owner bật `experimental_full`; smoke chỉ đọc đã chứng minh Hermes gọi được `terminal` và `read_file`. Các worker mới vẫn bắt đầu ở `ads_safe`.
- Chat Web chính chuyển sang native Hermes Dashboard; `Hermes Agents` chỉ giữ provider/model/permission settings và action mở dashboard.
- `Hermes Agents` có dialog đổi mật khẩu Dashboard theo worker; SSH password và password mới không persist trong database/audit/operation response.
