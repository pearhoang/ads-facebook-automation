# Decisions Index

| ID | Decision | Status | Scope | Impact |
|----|----------|--------|-------|--------|
| DEC-001 | Dùng FastAPI control plane + outbound Python worker | Active | toàn hệ thống | High |
| DEC-002 | Dùng Hermes làm AI orchestrator, không làm source of truth | Active | agent/backend | High |
| DEC-003 | Happy path dùng deterministic browser state machine; AI chỉ lập kế hoạch/recovery | Active | worker/agent | High |
| DEC-004 | Vertical slice đầu tiên là Account Session qua Chrome profile + noVNC | Active | phase 01 | High |
| DEC-005 | Action rủi ro mặc định DRAFT và cần approval | Active | campaigns/guardrails | High |
| DEC-006 | Tạo repo sạch và trích reusable modules từ Youtube app, không fork toàn bộ domain cũ | Active | bootstrap | Medium |
| DEC-007 | Test deployment dùng systemd trên host và Caddy container dùng chung | Active | infra | High |
| DEC-008 | noVNC/websockify bind localhost và đi qua backend proxy | Active | browser security | High |
| DEC-009 | Dùng Argon2 + opaque server-side session + membership-derived tenant | Active | auth/tenant | High |
| DEC-010 | Production dùng dedicated PostgreSQL 17 + Alembic; SQLite chỉ local/test/rollback | Active | database/infra | High |
| DEC-011 | Approval nội bộ tách khỏi publish; approved không tạo side effect lên Meta | Active | campaigns/guardrails | High |
| DEC-012 | Execution đầu tiên là deterministic read-only preflight; không click/publish | Active | worker/execution | High |
| DEC-013 | Phase 4 chỉ tạo/sửa unpublished Meta draft bằng state machine có checkpoint; không publish | Active | worker/execution | High |
| DEC-014 | Objective automation dùng catalog adapter canonical và chỉ mở default path đã khảo sát | Active | backend/UI/worker | High |
| DEC-015 | Field filling dùng declarative stage plan và chỉ công nhận kết quả đã xác minh trên DOM | Active | backend/UI/worker | High |
| DEC-016 | Resource exact-match, asset digest và human handoff là boundary bắt buộc trước Review | Active | backend/UI/worker | High |
| DEC-017 | Snap Chromium phải chạy direct binary và chứng minh profile path riêng | Active | worker/browser runtime | High |
| DEC-018 | Reporting dùng read-only worker job và immutable snapshot; Telegram delivery fail-soft | Active | backend/UI/worker | High |
| DEC-019 | Fleet dùng one-time enrollment, per-node credential và worker durable state | Active | backend/worker/infra | High |
| DEC-020 | Remote SSH/Telegram bootstrap secret transient; AI provider config mã hóa và scope theo worker | Superseded in part by DEC-027 | backend/UI/agent | High |
| DEC-021 | Source/worker bootstrap dùng public GitHub checkout tracking main | Active | repo/infra/worker | High |
| DEC-022 | Telegram dùng Hermes conversational gateway và MCP typed tools scope theo worker | Superseded in part by DEC-029 | agent/backend/worker | High |
| DEC-023 | AI Copilot session bridge được giữ như legacy rollback, không còn là UI chính | Superseded by DEC-025 | backend/UI/worker/agent | High |
| DEC-024 | Hermes permission mode theo worker, safe mặc định và experimental full chỉ opt-in | Active | backend/UI/worker/agent | High |
| DEC-025 | Chat Web dùng native Hermes Dashboard; Telegram vẫn là kênh lệnh chính | Active | backend/UI/infra/agent | High |
| DEC-026 | Search/vision fallback dùng per-worker Codex OAuth device login và Hermes MCP read-only | Active | backend/UI/worker/agent | High |
| DEC-027 | Lưu SSH credential mã hóa theo worker để tái sử dụng remote operation | Active | backend/UI/infra | High |
| DEC-028 | Chọn Meta Light Focus làm visual canonical cho toàn bộ app chính | Active | UI/templates/static | Medium |
| DEC-029 | Agent-orchestrated ad work; control-plane chỉ setup và theo dõi | Active | backend/UI/worker/agent | High |
| DEC-030 | Gộp UI theo hai vai trò: thiết lập tài khoản và vận hành quảng cáo | Superseded in part by DEC-032 | backend/UI/reporting | Medium |
| DEC-031 | Gỡ setup dùng deactivation có kiểm soát và cleanup profile từ xa | Active | backend/UI/worker | High |
| DEC-032 | Control-plane không hiển thị work queue hoặc review artifact cho người dùng | Active | backend/UI/agent | Medium |
