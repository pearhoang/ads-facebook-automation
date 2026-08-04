# Phase 12 - Canonical UI rollout

## Status

- Complete locally; chờ user duyệt preview trước khi push/deploy.

## Goal

- Áp dụng visual đã chốt ở `meta-dark-sidebar-glass.html` sang toàn bộ app chính mà không thay đổi API hoặc business flow.

## Scope

- `backend/app/templates/**`
- `backend/app/static/**`
- UI regression tests và tài liệu design system liên quan.

## Constraints

- Giữ nguyên server routes, API fields, form names và JavaScript behavior hiện có.
- Danger/destructive vẫn dùng red; primary action dùng indigo đã chốt; status giữ semantic colors.
- Các màn và dialog chưa có trong prototype phải dùng cùng token, density, radius, typography và interaction.
- UI tiếng Việt phải giữ UTF-8 và không tạo mojibake mới.
- Chỉ preview local; chưa push hoặc deploy khi chưa được user duyệt.

## Current State

- Prototype `meta-dark-sidebar-glass.html` đã được user chốt.
- Shared sidebar, token, app shell, KPI, panel, dialog, dropdown và login đã được chuyển sang production templates/static assets.
- Các route nghiệp vụ và form/API contract được giữ nguyên; đang chạy regression test và browser audit trước khi bàn giao local preview.

## Next Steps

- User duyệt app chính tại `http://127.0.0.1:8040/`.
- Chỉ push/deploy sau khi có yêu cầu tiếp theo.

## Verification

- `76 passed` với full pytest suite; `node --check` cho shared UI/login scripts và `git diff --check` đều sạch.
- Browser audit xác nhận Workspace, Campaigns, Reports, Bot VPS, Hermes Agents và Login không overflow viewport ngoài table scroller có chủ đích.
- Custom select đạt gap `4px`, radius `10px`, option `31px`; long dialog có radius `12px`, sticky header/footer và scrollbar nằm trong surface.
- Responsive audit ở `390×844` xác nhận login không horizontal overflow và KPI chuyển đúng lưới `2×2`.

## Risks

- CSS cũ phân tán giữa nhiều file có thể tạo specificity conflict hoặc làm lệch responsive layout.
- Dialog/JS phụ thuộc selector và form field hiện có; chỉ được đổi presentation, không đổi contract.
