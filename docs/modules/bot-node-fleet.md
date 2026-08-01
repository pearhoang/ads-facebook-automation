# Bot Node Fleet

## Responsibility

- Quản lý danh sách worker, remote install qua SSH, one-time enrollment, per-node credential và lifecycle `active/draining/revoked`.
- Worker giữ local SQLite state cho credential, assignment cache và outbox để không phụ thuộc uptime liên tục của control-plane.

## Entry Points

- API/UI: `backend/app/api/bot_nodes.py`, `backend/app/templates/bot_nodes.html`, `backend/app/static/bot_nodes.js`.
- Service: `backend/app/services/fleet.py`, `backend/app/services/remote_ops.py`.
- Runtime: `workers/agent/control_plane.py`, `workers/agent/local_state.py`.
- Packaging: `infra/bootstrap/install_bot_node.sh`, `infra/bootstrap/decommission_bot_node.sh`.

## Invariants

- SSH password và Telegram Bot Token không được persist; operation chỉ lưu host, user, status và message đã scrub.
- Remote install chuyển Telegram token/allowlist bằng file tạm `0600`, xóa ở cả installer và control-plane cleanup; secret không nằm trong process arguments.
- Enrollment token one-time chỉ lưu digest; worker credential cũng chỉ lưu digest ở control-plane.
- Decommission yêu cầu worker đã `draining`; nếu có fingerprint thì SSH host key phải khớp.
- Không hard-delete worker row hoặc browser profile từ UI mặc định.
- Worker service không phụ thuộc local web service.

## Current State

- Production migration mục tiêu `20260801_0007`; một worker hiện hữu đã gắn host và trạng thái installed.
- Canonical public repo là `https://github.com/pearhoang/ads-facebook-automation.git`, branch `main`; popup điền sẵn và cho phép thay bằng fork khác.
- Popup Add Bot là one-shot setup: SSH, Git checkout, initial Hermes provider, Telegram Bot Token và allowlist user ID; worker tự cài browser/noVNC/Hermes rồi kết nối control-plane.
- Installer cài sẵn unit native Hermes Dashboard nhưng không tự public hoặc start khi chưa có dashboard env/auth và reverse proxy riêng của node.
- Production source là Git checkout sạch tracking `origin/main`.
