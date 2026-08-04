# Phase 12 - Canonical UI rollout

## Status

- Complete locally sau fidelity correction; chờ user duyệt preview trước khi push/deploy.

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
- Shared sidebar, token, app shell, breadcrumb, search, notification popover, KPI semantic icon, panel, dialog, dropdown và login đã được chuyển sang production templates/static assets; logo, Lucide path, KPI anatomy và section header geometry đã được đối chiếu trực tiếp với prototype ở cùng viewport.
- Các route nghiệp vụ và form/API contract được giữ nguyên; đang chạy regression test và browser audit trước khi bàn giao local preview.

## Next Steps

- User duyệt app chính tại `http://127.0.0.1:8040/`.
- Chỉ push/deploy sau khi có yêu cầu tiếp theo.

## Verification

- `77 passed` với full pytest suite; `node --check` cho shared UI script và `git diff --check` đều sạch sau vòng fidelity logo/sidebar/KPI/section header.
- Browser audit xác nhận Workspace, Campaigns, Reports, Bot VPS, Hermes Agents và Login không overflow viewport ngoài table scroller có chủ đích.
- Search cập nhật số kết quả theo input; notification popover render trạng thái KPI thật và hiển thị empty state khi không có cảnh báo.
- Custom select đạt gap `4px`, radius `10px`, option `31px`; long dialog có radius `12px`, sticky header/footer và scrollbar nằm trong surface.
- Responsive audit ở `390×844` xác nhận login không horizontal overflow và KPI chuyển đúng lưới `2×2`.
- Desktop parity ở `1212×910` xác nhận sidebar `248px`, brand `40×30`, nav icon `17px`, KPI strip `126px`, metric cell `124px`, KPI icon `14px` và section icon container `22px` khớp geometry prototype.

## Typography parity follow-up

- Browser comparison confirms `Inter` for body/navigation, breadcrumb `12px`, page title `20px/1.25`, search input `13px`, button label `12px/650`, section heading `15px/1.45`, and matching sidebar icon stroke/footer loop mark colors.

## Risks

- CSS cũ phân tán giữa nhiều file có thể tạo specificity conflict hoặc làm lệch responsive layout.
- Dialog/JS phụ thuộc selector và form field hiện có; chỉ được đổi presentation, không đổi contract.
