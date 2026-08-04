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
- `/ad-accounts` là setup surface cho ad account và Meta resource; `/campaigns` là work queue/timeline do Telegram/Hermes tạo, không phải trình dựng campaign thay Ads Manager.
- Ad account row có action sửa dùng chung dialog create/edit; structural fields phải hiện cảnh báo khóa khi account đã có dependency, còn label vẫn sửa được.
- Chi tiết work hiển thị request gốc, account/resource đã resolve, plan, timeline, recovery, artifact và handoff; không yêu cầu user bấm tiếp từng phase trên web.
- Execution jobs dùng table/history và detail dialog; artifact mở ở tab riêng, không nhúng ảnh lớn vào table.
- Spec Campaign/Ad Set/Ad được Hermes thu thập bằng hội thoại và đóng băng thành internal snapshot; web không render lại form nhập spec cho người dùng.
- Sáu objective vẫn dùng adapter/catalog nội bộ để resolve required field, conversion location và performance goal trước khi worker thao tác Ads Manager.
- Draft builder detail hiển thị phase dừng, số lần chạy, current URL, blockers và checkpoint `Campaign`, `Ad Set`, `Ad`, `Review`.
- Phase 6 hiển thị `field_results` bằng bảng nhỏ trong job detail: stage, field path, trạng thái áp dụng/xác minh và chi tiết lỗi; không giấu field chưa có control.
- `/ad-accounts` hiển thị Meta resource registry; resource mới phải có trạng thái `Chưa xác minh` và chỉ được dùng khi exact ownership đã rõ.
- Creative asset không có thư viện nhập tay trong primary UI. Worker ingest media từ Telegram/Hermes, lưu digest và gắn asset ID vào internal snapshot.
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
- `Bot VPS` nhận SSH password một lần khi Add Bot và cho phép thay đổi trong `Sửa thiết lập`; ô để trống giữ credential cũ. Danh sách chỉ hiển thị trạng thái đã/chưa lưu, không render secret.
- `Hermes Agents` có action `Đổi mật khẩu Dashboard` theo Bot VPS đang chọn. Dialog chỉ nhận password Dashboard mới từ 4 ký tự; thao tác dùng SSH credential đã mã hóa, xoay signing secret để đăng xuất phiên cũ và không restart gateway/Telegram/browser worker.
- `Hermes Agents` có section `Codex Search & Vision` theo worker: trạng thái/account/plan/tools, action `Kết nối Codex` và `Ngắt kết nối`. UI hiển thị riêng public verification URL, one-time code dạng `XXXX-XXXXX` và action sao chép mã; muốn đổi account phải ngắt kết nối để xóa credential cũ trước, không cần noVNC và cookie ChatGPT không phải credential của tool.
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
- Copy xác nhận hội thoại phải nói rõ đây là duyệt internal plan, chưa phải campaign đang chạy trên Meta.
- Timeline phải phân biệt `Preflight read-only`, `Tạo Meta draft`, `Cần người dùng` và `Dừng tại Review`; không gọi draft là campaign đang chạy.
