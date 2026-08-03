# Thiết kế branding Ads Meta Master

## Mục tiêu

- Đổi nhận diện hiển thị từ `Ads Lush` sang `Ads Meta Master`.
- Loại bỏ ngôn ngữ `Lush Media` khỏi giao diện control-plane trong khi vẫn giữ nguyên domain triển khai `ads.lushmedia.net`.
- Làm rõ sản phẩm phục vụ tự động hóa Meta Ads mà không dùng copy chung chung hoặc tạo cảm giác đây là sản phẩm chính thức của Meta.
- Dùng một biểu tượng nhất quán cho sidebar, login và favicon.

## Phạm vi giao diện

- Cập nhật brand block trên toàn bộ template thuộc control-plane:
  - `login.html`
  - `workspace.html`
  - `campaigns.html`
  - `reports.html`
  - `bot_nodes.html`
  - `hermes_agents.html`
  - `ai_copilot.html` legacy
- Brand name hiển thị là `Ads Meta Master`.
- Subtitle hiển thị là `Meta Ads Automation`.
- Mọi `<title>` bắt đầu bằng `Ads Meta Master` hoặc kết thúc bằng `— Ads Meta Master` trên login.
- Footer sidebar chỉ hiển thị:
  - trạng thái hiện có;
  - nhãn `Admin`;
  - action `Đổi mật khẩu` khi trang hiện hỗ trợ action này.
- Bỏ tenant name, role và module/session context khỏi footer hiển thị.

## Biểu tượng và favicon

- Tạo một SVG riêng cho sản phẩm, không sao chép nguyên logo Meta infinity hoặc Facebook `f`.
- Hình chính là monogram `M` tạo bởi hai nét liên kết, đủ rõ ở kích thước 16–32 px và gợi liên tưởng tới hệ sinh thái Meta Ads.
- Dùng nền xanh đậm, nét trắng và hình khối đơn giản; không dùng gradient, glow hoặc chi tiết trang trí nhỏ.
- Brand block dùng cùng SVG với favicon để nhận diện nhất quán.
- Khai báo favicon trong mọi template để tab trình duyệt không còn dùng biểu tượng globe mặc định.
- SVG phải có `viewBox` cố định, không chứa external resource, script hoặc embedded raster data.

## Ngôn ngữ hình ảnh

- Giữ nguyên cấu trúc điều hướng, mật độ table/form và hành vi responsive hiện tại.
- Giữ palette bề mặt trung tính đang hoạt động tốt; chỉ đổi brand mark từ accent cam sang màu xanh của nhận diện mới.
- Không chuyển toàn bộ action button sang xanh trong thay đổi này để tránh biến một branding task thành redesign rộng.
- Không dùng logo chính thức theo cách có thể khiến người dùng hiểu nhầm ứng dụng do Meta phát hành hoặc chứng thực.

## Ranh giới kỹ thuật

- Không đổi:
  - domain `ads.lushmedia.net` hoặc `hermes.ads.lushmedia.net`;
  - `SESSION_COOKIE_NAME`, `CSRF_COOKIE_NAME` và các cookie `ads_lush_*`;
  - marker, provider ID, script name, service name hoặc remote path chứa `ads-lush`;
  - tenant record trong database;
  - API, worker contract, route hoặc deployment topology.
- Chỉ đổi visible UI copy, document title và static brand asset.
- Không đưa tài sản logo lấy từ nguồn bên ngoài vào repository.

## Khả năng truy cập và UTF-8

- Brand SVG có accessible label thông qua link brand; favicon được đánh dấu như document icon.
- Giữ `<meta charset="UTF-8">` trên mọi template.
- Không dùng uppercase kéo dài cho tiếng Việt.
- Kiểm tra source bằng UTF-8 và chạy regression test chống mojibake hiện có.

## Kiểm thử và nghiệm thu

- Test source xác nhận không còn visible copy `Ads Lush`, `Automation workspace` hoặc footer `Lush Media` trong template.
- Test xác nhận mọi template có favicon và brand asset mới.
- Test hiện có cho auth/workspace được cập nhật theo visible copy mới; không thay assertion liên quan cookie/runtime identifiers.
- Render/smoke ít nhất login và workspace ở desktop; kiểm tra favicon, brand block và footer.
- Chạy test suite liên quan UI/auth, sau đó chạy toàn bộ `pytest` nếu không có blocker môi trường.

## Tiêu chí hoàn thành

- Sidebar hiển thị icon mới, `Ads Meta Master` và `Meta Ads Automation`.
- Footer hiển thị `Admin`, không còn `Lush Media` hoặc dòng `owner · <module>`.
- Tab trình duyệt hiển thị favicon mới và title mới.
- Không có thay đổi contract/runtime ngoài giao diện.
