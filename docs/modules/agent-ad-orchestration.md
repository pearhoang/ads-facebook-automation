# Agent Ad Orchestration

## Responsibility

- Điều phối yêu cầu quảng cáo từ Telegram/Hermes thành một `AdAutomationRequest` có account/resource resolution, internal plan, timeline và artifact.
- Ingest media do user gửi, tạo internal campaign snapshot, xin xác nhận bằng ngôn ngữ tự nhiên rồi tự nối preflight sang draft builder.
- Theo dõi lỗi, retry một lần từ checkpoint, handoff đúng URL khi Meta cần login/2FA/challenge và lưu verified workflow learning sau recovery thành công.

## Entry Points

- Models: `AdAutomationRequest`, `AdAutomationEvent`, `AgentWorkflowLearning` trong `backend/app/models.py`.
- Service: `backend/app/services/automation.py`.
- Agent API: `/api/worker/agent/*` trong `backend/app/api/worker.py`.
- Typed tools: `workers/agent/control_plane_mcp.py`.
- Telegram progress: `workers/agent/execution.py`.
- Monitoring UI: `/campaigns`, `backend/app/templates/campaigns.html`, `backend/app/static/campaigns.js`.

## State Flow

- `planning -> awaiting_approval -> queued -> preflight -> draft_build -> completed`.
- User có thể cancel khi đang chờ xác nhận.
- Lỗi lần đầu tạo recovery event và enqueue lại đúng job từ checkpoint.
- Lỗi lặp lại hoặc challenge chuyển `awaiting_user`; noVNC chỉ là handoff, không phải đường điều khiển bình thường.
- Thành công của draft builder nghĩa là đã tới Review, không đồng nghĩa Publish hoặc đang spend.

## Boundaries

- Control-plane resolve exact worker, Facebook profile, ad account, Page/Instagram/Dataset/Form/App và creative asset theo tenant.
- Hermes có thể dùng terminal/file/code/browser/delegation khi owner bật `Experimental Full Access`, nhưng Meta mutation vẫn qua typed tools và worker-owned browser profile.
- `allow_publish=false` là invariant của phase này. Không có tool Publish, tăng budget hoặc bypass approval.
- Workflow learning chỉ được đánh dấu `verified` sau một recovery đã chạy thành công; source production không tự sửa mà không review/test.

## Verification

- `tests/test_agent_orchestrated_work.py` kiểm tra exact resource resolution, prepare/confirm, auto chaining, retry một lần và verified learning.
- `tests/test_bot_fleet_ai_settings.py` kiểm tra đủ typed tool catalog và Hermes managed config.
- Browser smoke phải xác nhận `/campaigns` không còn campaign form/asset uploader và `/ad-accounts` giữ đúng setup surface.

## Related Decisions

- `DEC-022`
- `DEC-024`
- `DEC-028`
