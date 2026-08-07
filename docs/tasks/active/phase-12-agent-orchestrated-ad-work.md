# Phase 12 — Agent-Orchestrated Ad Work

## Goal

Chuyển primary workflow sang `Telegram/Hermes + media -> control-plane resolution -> worker Ads Manager -> Telegram/timeline`, đồng thời giữ control-plane là setup/source-of-truth thay vì bản sao Ads Manager.

## Scope

- `AdAutomationRequest`, event timeline và workflow learning.
- Typed tools resolve/prepare/confirm/status/learning và agent media ingest.
- Auto chain preflight -> draft builder -> Review, retry một lần từ checkpoint.
- Telegram progress delivery và noVNC chỉ cho challenge.
- Tách `/ad-accounts` setup surface khỏi `/campaigns` reporting surface; progress/artifact gửi qua Telegram/Hermes.

## Safety

- Không Publish, không tăng budget và không bypass tenant/approval boundary.
- Production smoke chỉ read-only; E2E spend cần ad account thật và explicit approval riêng.

## Verification

- Python compile, full pytest, Alembic fresh-head/check.
- Local browser smoke cho auth, `/ad-accounts`, `/campaigns` và responsive state.
- Production health, migration, service status, typed-tool discovery và Telegram/Hermes continuity.

## Delivery evidence

- Full suite: `95 passed` tại delivery Phase 12.
- Production: commit `8e62792`, migration `20260804_0011 (head)`, `alembic check` không có drift.
- Backfill: 2 work request và 2 timeline event từ campaign lịch sử; không tạo hoặc publish campaign mới.
- Live browser tại delivery Phase 12: `/campaigns` là work queue/timeline; trạng thái này đã được supersede bởi DEC-032, chuyển progress/artifact sang Telegram/Hermes và giữ `/campaigns` cho reporting.
- Runtime: web, worker, Hermes gateway và Hermes dashboard đều active; worker poll/heartbeat trả `200`.
