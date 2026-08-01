# Phase 02 Campaign Foundation

## Goal

- Hoàn thiện vertical slice `Ad Account → Campaign Draft → Submit → Approve/Reject → Audit` trên web control plane.

## Scope

- Multi-tenant models và Alembic revision.
- API/service state machine với CSRF và role guard.
- Campaign workspace UI có review snapshot.
- Local regression test và production deployment.

## Safety Boundary

- Không gọi Meta API.
- Không điều khiển Facebook Ads Manager qua browser.
- Không có publish job, budget mutation thật hoặc worker campaign contract.
- Approval ở phase này chỉ là quyết định nội bộ.

## Current State

- Models/service/API/UI đã triển khai cục bộ.
- Local suite: `9 passed`.
- Alembic head: `20260731_0002`; schema drift check sạch.
- Playwright đã xác minh route `/campaigns`, auth redirect, Vietnamese copy và empty states.
- Đã deploy production trên `https://ads.lushmedia.net/campaigns`.
- PostgreSQL production ở `20260731_0002 (head)`; web/worker active và database healthy.
- Authenticated smoke: page và toàn bộ read API trả `200`, safety copy đúng, không tạo demo record.
- Post-deploy state: `0` ad account, `0` campaign, `0` approval, `0` audit và `0` active browser session.
- Final dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase2-final-20260731-142709.dump`.

## Next Step After Completion

- Phase 3 chỉ bắt đầu sau khi chốt job contract và preview payload: deterministic browser executor hoặc Meta Marketing API adapter.
- Publish phải là action/job riêng, không được suy diễn từ trạng thái `approved`.
