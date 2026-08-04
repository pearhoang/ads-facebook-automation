# Memory Index

## Always Read For Project Task

- `AGENTS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/MEMORY_INDEX.md`

## Read By Task Type

### Account, browser profile hoặc noVNC

- `docs/modules/account-session.md`
- `docs/modules/control-plane-worker.md`
- `docs/DECISIONS_INDEX.md`

### Backend, API, job hoặc worker

- `docs/modules/control-plane-worker.md`
- `docs/DECISIONS_INDEX.md`

### Ad account, campaign, approval hoặc audit

- `docs/modules/campaign-approval.md`
- `docs/modules/auth-tenant.md`
- `docs/DECISIONS_INDEX.md`

### Telegram media -> agent -> worker ad execution

- `docs/modules/agent-ad-orchestration.md`
- `docs/modules/resource-asset-registry.md`
- `docs/modules/meta-draft-builder.md`
- `docs/modules/control-plane-worker.md`
- `docs/DECISIONS_INDEX.md`

### Execution job, preflight hoặc worker artifact

- `docs/modules/execution-preflight.md`
- `docs/modules/control-plane-worker.md`
- `docs/modules/account-session.md`
- `docs/DECISIONS_INDEX.md`

### Meta draft builder hoặc browser mutation

- `docs/modules/meta-draft-builder.md`
- `docs/modules/objective-adapters.md`
- `docs/modules/resource-asset-registry.md`
- `docs/modules/execution-preflight.md`
- `docs/modules/control-plane-worker.md`
- `docs/modules/account-session.md`
- `docs/DECISIONS_INDEX.md`

### Authentication, user hoặc tenant

- `docs/modules/auth-tenant.md`
- `docs/modules/control-plane-worker.md`
- `docs/DECISIONS_INDEX.md`

### Frontend hoặc UX

- `docs/UI_SYSTEM.md`
- Module memory của flow đang sửa.

### Hermes, Telegram hoặc AI recovery

- `docs/modules/bot-node-fleet.md`
- `docs/modules/ai-provider-settings.md`
- `docs/modules/agent-copilot.md`
- `docs/tasks/active/phase-09-telegram-hermes-tools.md`
- `docs/tasks/active/phase-11-codex-search-vision.md`
- `docs/DECISIONS_INDEX.md`

### Bot VPS, SSH install, drain hoặc decommission

- `docs/modules/bot-node-fleet.md`
- `docs/modules/control-plane-worker.md`
- `docs/modules/infra-runtime.md`
- `docs/DECISIONS_INDEX.md`

### Reporting, KPI hoặc lịch Telegram

- `docs/modules/reporting.md`
- `docs/modules/control-plane-worker.md`
- `docs/modules/account-session.md`
- `docs/DECISIONS_INDEX.md`

### Deploy hoặc VPS runtime

- `docs/modules/infra-runtime.md`
- `docs/DECISIONS_INDEX.md`

### Database, schema hoặc migration

- `docs/modules/database-migrations.md`
- `docs/modules/infra-runtime.md`
- `docs/DECISIONS_INDEX.md`

## Module Map

- `backend/**`, `workers/**` -> `docs/modules/control-plane-worker.md`
- account/profile/session/noVNC code -> `docs/modules/account-session.md`
- auth/user/tenant/session cookie code -> `docs/modules/auth-tenant.md`
- ad account/campaign/approval/audit code -> `docs/modules/campaign-approval.md`
- ad automation request/timeline/recovery/Telegram media -> `docs/modules/agent-ad-orchestration.md`
- execution job/preflight/artifact code -> `docs/modules/execution-preflight.md`
- Meta draft mutation/checkpoint/resume code -> `docs/modules/meta-draft-builder.md`
- objective catalog, conditional form, setup/default path -> `docs/modules/objective-adapters.md`
- Meta resource, creative asset, worker asset download -> `docs/modules/resource-asset-registry.md`
- Alembic/PostgreSQL/data cutover -> `docs/modules/database-migrations.md`
- `backend/app/templates/**`, `backend/app/static/**` -> `docs/UI_SYSTEM.md`
- reporting models/API/UI/worker -> `docs/modules/reporting.md`
- worker enrollment/operations/durable state -> `docs/modules/bot-node-fleet.md`
- AI provider/Hermes config -> `docs/modules/ai-provider-settings.md`
- AI Copilot conversation/session/job -> `docs/modules/agent-copilot.md`
- `infra/**`, systemd/Caddy/VPS deployment -> `docs/modules/infra-runtime.md`

## Task Notes

- Snap Chromium profile isolation đã sửa production: `docs/tasks/active/profile-isolation-snap-runtime.md`.
- Phase 7 đã có E2E Page/media thật đến Review và `published=false`: `docs/tasks/active/phase-07-resources-assets-handoff.md`.
- Phase 8 reporting/KPI đã deploy và có production snapshot: `docs/tasks/active/phase-08-reporting-kpi.md`.
- Phase 8 multi-VPS/AI settings đã deploy: `docs/tasks/active/phase-08-multi-vps-ai-settings.md`.
- Phase 6 hoàn tất: `docs/tasks/active/phase-06-field-filling-adapters.md`.
- Phase 5 hoàn tất: `docs/tasks/active/phase-05-objective-adapters.md`.

## Archives

- Không đọc mặc định `docs/archive/*` hoặc changelog đầy đủ.
