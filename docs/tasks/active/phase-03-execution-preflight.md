# Phase 03 Execution Preflight

Status: completed

## Goal

- Hoàn thiện vertical slice `Approved Campaign → Execution Preview → Explicit Confirm → Worker Preflight → Artifact/Result`.

## Scope

- Execution job queue, lease và worker sync contract.
- Headless Chromium/CDP read-only runtime dùng persistent profile.
- Screenshot artifact upload/download theo tenant.
- UI preview, blockers, confirmation, job history, result và retry.
- Migration, regression tests và production deployment.

## Safety Boundary

- Không click Ads Manager.
- Không tạo Campaign/Ad Set/Ad thật.
- Không publish hoặc thay đổi budget.
- Không tự chạy khi campaign vừa được approve.

## Current State

- Backend, worker, UI và migration `0003` đã hoàn tất cục bộ.
- `13 passed`; compile, JS syntax và Alembic drift check đạt.
- Đã deploy production trên `https://ads.lushmedia.net/campaigns`.
- PostgreSQL production ở `20260731_0003 (head)`; web/worker active và database healthy.
- Worker poll execution endpoint ổn định; authenticated page/jobs API trả `200`.
- Draft chưa approve trả `409` ở execution preview đúng guardrail; không tạo job giả.
- Production giữ nguyên `1` ad account, `1` internal campaign draft, `0` execution job, `0` artifact và `0` active browser session.
- Final dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase3-final-20260731-150538.dump`.

## Next Step After Completion

- Production preflight thật đã đạt `ready` cho đúng profile/ad account và có screenshot artifact.
- Phase 4 draft builder kế thừa kết quả này; live publish vẫn là phase/decision riêng.
