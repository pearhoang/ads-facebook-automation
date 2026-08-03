# UI System

## Product Surfaces

- Authentication.
- Dashboard tổng quan.
- Facebook accounts và ad accounts.
- Account detail/browser session.
- Campaigns, jobs, reports, approvals và AI copilot.

## Visual Direction

- Nhận diện sản phẩm là `Ads Meta Master`, dùng subtitle `Meta Ads Automation` và custom SVG monogram `M` màu xanh cho brand mark lẫn favicon; không dùng logo chính thức của Meta/Facebook.
- Sidebar cố định giữ dark neutral `#242321`, top bar gọn, white surfaces trên nền blue-gray rất nhạt.
- Tone `Meta Balanced`: action/focus dùng blue `#1877F2`, attention/safety dùng indigo `#4F46E5`, success/online dùng green `#16865F`; error, blocker và destructive action giữ red `#B83A3A`.

## Shared Patterns

- KPI strip chỉ hiển thị số có ý nghĩa vận hành.
- Tables/lists hỗ trợ search, filter, status badge và row action rõ ràng.
- Action có rủi ro dùng review drawer/modal trước khi confirm.
- Browser session có state panel riêng; không nhúng URL noVNC vào DOM trước khi được cấp quyền.
- Loading, empty, error và waiting-for-user là các trạng thái bắt buộc.
- Auth dùng một form gọn, error inline và recovery path rõ; không biến login thành dashboard.
- Workspace header hiển thị user/tenant hiện tại và action đăng xuất.
- Campaign workspace dùng table-first layout: ad accounts, campaign drafts, pending approvals và audit.
- Ad account row có action sửa dùng chung dialog create/edit; structural fields phải hiện cảnh báo khóa khi account đã có dependency, còn label vẫn sửa được.
- Approval modal luôn hiển thị snapshot version, ad account, objective, budget, schedule, targeting và creative.
- Execution preview hiển thị profile, worker, browser lock, blockers và safety scope trước khi enqueue.
- Execution jobs dùng table/history và detail dialog; artifact mở ở tab riêng, không nhúng ảnh lớn vào table.
- Form campaign thu thập spec có cấu trúc cho Page, quốc gia, độ tuổi, placements, primary text, headline, destination URL và CTA; `note` chỉ là phần bổ sung.
- Form campaign lấy sáu objective từ API catalog, hiển thị conversion location/performance goal read-only và chỉ mở field liên quan: messaging destination, Instant Form, app/store hoặc dataset/event.
- Destination URL chỉ hiện cho Traffic và Sales; phần tóm tắt phải nói rõ default path và Traffic manual setup.
- Execution preview phân biệt rõ `Preflight read-only` và `Meta draft builder`, hiển thị blockers/warnings và confirmation riêng.
- Draft builder detail hiển thị phase dừng, số lần chạy, current URL, blockers và checkpoint `Campaign`, `Ad Set`, `Ad`, `Review`.
- Phase 6 hiển thị `field_results` bằng bảng nhỏ trong job detail: stage, field path, trạng thái áp dụng/xác minh và chi tiết lỗi; không giấu field chưa có control.
- Phase 7 đặt `Meta resources` và `Creative assets` thành hai registry table riêng; resource mới phải hiển thị `Chưa xác minh`, asset hiển thị loại, dung lượng và SHA-256.
- Campaign form chọn Page/Dataset/Form/App/asset từ registry theo ad account, không cho nhập label rời rạc rồi suy đoán.
- Job `Cần người dùng` có action `Mở noVNC xử lý` tại exact Ads Manager URL do worker trả về; action này không retry hoặc publish job.
- Safety banner luôn nói rõ draft builder có thể click/điền nhưng không tự `Publish`.
- Trang Báo cáo dùng table-first layout: ad account filter, bốn KPI gần nhất, snapshot history, schedule và report job history.
- Manual report dialog luôn yêu cầu `THU THẬP KPI`; schedule nói rõ timezone, lookback và Telegram token không được nhập trên UI.
- Report job tách trạng thái thu thập khỏi trạng thái Telegram để lỗi gửi tin không làm mất snapshot.
- Trang `Bot VPS` dùng một table duy nhất; mỗi worker có action `Sửa`, `Drain/Kích hoạt`, `Gỡ khỏi VPS`, `Xóa kết nối`, và action rủi ro luôn mở popup xác nhận.
- Popup cài worker nhóm rõ `SSH`, `Source`, `Hermes Agent` và `Telegram`; password/API key/token dùng password input, không render lại sau submit và operation chỉ hiển thị tiến độ không chứa secret.
- Add Bot yêu cầu Telegram Bot Token cùng allowlist user ID; copy phải nói rõ token chỉ truyền một lần, nhiều user ID phân tách bằng dấu phẩy và không có chế độ allow-all.
- Trang `Hermes Agents` bắt buộc chọn worker trước khi sửa provider; API key luôn masked và để trống nghĩa là giữ key hiện tại.
- Popup cài worker điền sẵn canonical GitHub repo nhưng vẫn là input sửa được; DeepSeek V4 Flash 0731 là preset đầu tiên, còn model API canonical giữ `deepseek-v4-flash`.
- Hermes Agents và popup cài Bot VPS dùng cùng hai control `Thinking` và `Reasoning effort`; popup sửa Bot VPS không lặp lại provider settings.
- Hermes Agents có control `Quyền Agent` theo worker. `Ads Safe` là mặc định; `Experimental Full Access` hiển thị cảnh báo inline về quyền terminal/file/code/browser/computer/delegation và nói rõ session mới hoặc `/reset` mới nhận bộ quyền.
- Footer sidebar chỉ hiển thị `Admin` và action chữ `Đổi mật khẩu`; không hiển thị tenant name, role hoặc module/session context. Dialog dùng chung xác minh mật khẩu hiện tại, yêu cầu tối thiểu 4 ký tự và báo rõ các phiên khác sẽ bị đăng xuất.
- Login dùng nhãn `Tài khoản` với text input và `autocomplete=username`; không ép identifier phải có định dạng email.
- Copy DeepSeek phải nói rõ default thinking High và Low/Medium được provider ánh xạ lên High; không hứa mức suy luận mà endpoint không hỗ trợ.
- Native Hermes Dashboard là Web chat/agent surface. Control-plane không tái tạo chat workspace; route legacy `/ai-copilot` chỉ chuyển hướng sau khi kiểm tra đăng nhập.
- Navigation dùng nhãn `Hermes Dashboard` mở tab mới; `Hermes Agents` có action `Mở Hermes Dashboard` cạnh trạng thái provider.
- `Hermes Agents` có action `Đổi mật khẩu Dashboard` theo Bot VPS đang chọn. Dialog chấp nhận password từ 4 ký tự, giải thích SSH password chỉ dùng một lần, xoay signing secret sẽ đăng xuất phiên cũ và gateway/Telegram/browser worker không bị restart.
- Natural language là primary interaction. Không hiện generic menu button sau mọi câu trả lời.
- Shortcut chỉ render khi có action preview/resource cụ thể, tối đa hai chip nhẹ; composer luôn hoạt động và user có thể trả lời bằng lời.
- Conversation list phân biệt Web/Telegram; chọn Telegram phải tiếp tục exact Hermes session, không tạo context mới.
- AI Copilot không hiển thị raw MCP schema, tool result hoặc `session_meta`; nội dung assistant render safe Markdown cho bold, list, table và code.
- Chat workspace phải giữ topbar/session list cố định trong viewport; focus composer không được cuộn cả page và response đổi session cũ không được ghi đè session mới.
- Composer AI Copilot chỉ mở slash palette khi user gõ `/`; hỗ trợ `/help`, `/new`, `/sync`, `/status` như shortcut Web, không ngụ ý mọi Hermes messaging command đều chạy trên web.
- Attachment queue nằm sát composer, hiện tên/kích thước và cho bỏ từng tệp. Copy phải nói rõ chỉ hỗ trợ tối đa ba tệp text/data UTF-8, 128 KB/tệp; không hiện image/PDF khi chưa có pipeline thật.
- Trigger attachment của AI Copilot là dấu `+` nằm trong mép trái ô nhập; không dùng nút chữ đứng riêng ngoài composer.

## Consistency Rules

- Không dùng dashboard card tràn lan nếu table hoặc status row rõ hơn.
- Không dùng màu thương hiệu Meta như cách giả mạo giao diện chính thức.
- Vietnamese copy phải UTF-8, rõ hành động và không mơ hồ về trạng thái tiêu tiền.
- Frontend source/response phải khai báo UTF-8 và regression test chặn các chuỗi mojibake phổ biến.
- Publish/budget action luôn hiển thị account, campaign và số tiền trước confirm.
- Copy `Đã duyệt nội bộ` phải được dùng trong Phase 2 để không tạo ấn tượng campaign đã chạy trên Meta.
- Copy Phase 3 phải nói rõ `preflight read-only`, `không click` và `không publish`.
- Copy Phase 4 phải dùng `Tạo Meta draft`, `Cần người dùng` và `Không tự publish`; không gọi draft là campaign đang chạy.

## Candidate Prototype Directions

- Ba prototype so sánh tại `docs/ui-prototypes/`: `Meta Gradient Vibrant`, `Meta Balanced Elevated` và bản user đang chọn để tinh chỉnh `Meta Light Focus`.
- Cả ba giữ sidebar-left/main-content, dùng cùng component anatomy cho Dashboard, Login, native dialogs, tables, empty state, search/filter, popovers và campaign checkpoint progress.
- `Meta Light Focus` dùng sidebar trắng, canvas `#F5F7FA`, logo tile `#0866FF`, action xanh solid và login lấy identity gradient xanh–tím–hồng từ phương án A; slug cũ `meta-dark-sidebar-glass` được giữ để URL review không đổi.
- Đây là candidate để user chọn, chưa phải canonical production styling. Không áp dụng token, layout hoặc interaction prototype vào Jinja templates cho đến khi có lựa chọn rõ ràng.
- Prototype không gọi API, không dùng production data và không nhúng password mẫu; danger/destructive giữ `#B83A3A` ở cả ba hướng.
