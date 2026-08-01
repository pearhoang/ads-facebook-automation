# Phase 06 Field-Filling Adapters

Status: completed

## Goal

- Nâng objective adapter từ catalog/validation thành deterministic field-filling tại Campaign, Ad Set và Ad cho các default path đã khảo sát.
- Luôn tạo unpublished draft, lưu bằng chứng từng field và dừng trước `Đăng`/`Publish`.

## Scope

- Xây stage plan từ approved snapshot và immutable `objective_adapter`.
- Điền/kiểm tra campaign budget, default conversion/performance, Page, app/form/messaging input và creative text/URL khi control khả dụng.
- Trả `field_results` rõ `applied`, `already_set`, `blocked`, `not_available`; không coi field chưa thật sự điền là hoàn tất.
- Discovery/smoke chỉ dùng exact-name draft tạm và phải cleanup ở Campaign level.

## Safety

- Không click `Đăng`/`Publish`.
- Không chọn bừa Page/form/app trong production job; mọi entity selector cần exact value từ approved snapshot.
- Không tiếp tục qua stage nếu required field bị thiếu hoặc control tương ứng không tồn tại.
- Chỉ resume exact campaign name và giữ browser profile lock.

## Verification Plan

- Unit test stage planner và DOM command result contract.
- Full local suite + compile/UTF-8.
- Production predeploy backup, zero-lock check và Alembic check.
- Exact discovery draft smoke; xác minh `published=false`, cleanup thành công và legitimate campaign còn nguyên.

## Delivered

- Objective catalog phát hành declarative `field_actions` theo stage Campaign/Ad Set/Ad; job giữ immutable adapter snapshot.
- Worker lập stage plan và trả `field_results` riêng cho từng field, gồm `applied`, `already_set`, `verified`, `skipped`, `blocked`, `not_available`, `failed`.
- DOM adapter tua/cuộn editor để tìm control lazy-rendered, điền campaign budget và URL, exact-match Page/form/app/dataset/event, creative text và CTA khi control khả dụng.
- Job detail hiển thị bảng kết quả field; mọi blocker vẫn dừng trước Review/Publish.

## Verification Result

- Local: Python compile sạch, JS syntax sạch, `24 passed`.
- Read-only production probe trên campaign hợp lệ `6982618414377`: không click, không publish, browser process đóng sạch.
- Discovery smoke Sales `6982633575177`: budget `applied`, default conversion/performance `verified`, URL `applied`, CTA `already_set`; Page giả exact-match `failed`, primary/headline `not_available` vì chưa có Page/media.
- Smoke dừng `awaiting_user` tại Ad, `published=false`; discovery draft được xác minh exact ID/name và xóa thành công.
- Campaign hợp lệ và draft Meta không thuộc discovery không bị xóa.
