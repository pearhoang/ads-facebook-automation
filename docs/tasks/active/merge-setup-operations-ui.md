# Gộp thiết lập tài khoản và vận hành quảng cáo

## Mục tiêu

- Gộp Facebook profile, ad account và Meta resource vào một màn hình thiết lập.
- Gộp hàng công việc, KPI, lịch báo cáo và lịch sử thu thập vào một màn hình vận hành.
- Giảm dữ liệu vận hành thô trên UI; lịch sử phải phân trang và có thể dọn an toàn.

## Phạm vi

- Route và sidebar của control-plane.
- Template/JavaScript/CSS cho hai màn hình chính.
- API phân trang và dọn lịch sử report job.
- Kiểm thử, tài liệu và triển khai production.

## Nguyên tắc

- Telegram/Hermes là nơi ra lệnh và xử lý chính.
- Control-plane chỉ thiết lập định tuyến, theo dõi tiến độ, KPI và ngoại lệ cần người dùng.
- Không xóa report job đang chạy; luôn giữ snapshot KPI mới nhất của từng ad account.
- Route cũ được chuyển hướng để bookmark không hỏng.

## Trạng thái

- [x] Khảo sát route, template và reporting model.
- [x] Gộp màn hình thiết lập tài khoản.
- [x] Gộp màn hình vận hành và báo cáo.
- [x] Thêm phân trang/xóa lịch sử an toàn.
- [x] Kiểm thử và triển khai production.

## Kết quả

- Commit triển khai: `42172c5`.
- `98 passed`; JavaScript syntax hợp lệ.
- Production web/worker active, health `ok`.
- Browser production xác nhận đúng thứ tự setup, dữ liệu vận hành thật, không có console error.
