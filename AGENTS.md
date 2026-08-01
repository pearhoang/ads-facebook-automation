# Working Agreements

- Giao tiếp, walkthrough, checklist và hướng dẫn triển khai bằng tiếng Việt.
- Giữ nguyên tiếng Anh cho code identifiers, command, config key, API field và log lỗi.
- Luôn phân loại task thành `Quick Task` hoặc `Project Task`.

## Project Task Bootstrap

- Trước khi sửa code, đọc `AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/MEMORY_INDEX.md`.
- Chỉ đọc module memory, decision hoặc active task liên quan trực tiếp.
- Với thay đổi UI, đọc `docs/UI_SYSTEM.md` và dùng các UI skill được quy định ở workspace.
- Sau mỗi Project Task, append một entry ngắn vào `docs/CHANGELOG.md`.
- Quyết định kiến trúc còn hiệu lực phải cập nhật `docs/DECISIONS_INDEX.md` và `docs/DECISIONS.md`.

## Boundaries

- `backend/` là control plane và source of truth cho auth, tenant, job, approval, audit.
- `workers/` là outbound runtime; browser profile và noVNC luôn chạy trên worker sở hữu profile.
- `agent/` chỉ điều phối qua typed tools; không truy cập trực tiếp database hoặc tự publish/tăng budget.
- `infra/` chỉ chứa packaging/deploy, không chứa business logic.
- Không thay đổi API/worker contract khi chưa đánh giá migration và cập nhật decision.

## Safety

- Mọi action có thể tiêu tiền mặc định tạo `DRAFT` hoặc yêu cầu explicit approval.
- Không lưu password hoặc mã 2FA; user nhập trực tiếp trong phiên noVNC.
- Không để noVNC, CDP hoặc browser debug port public trực tiếp.
- Không cho phép hai actor cùng điều khiển một browser profile.
- Không để agent tự sửa production skill/code khi chưa review và kiểm thử.
