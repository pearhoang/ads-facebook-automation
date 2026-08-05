# UI System

## Product Surfaces

- Authentication.
- Dashboard tổng quan.
- Facebook accounts và ad accounts.
- Account detail/browser session.
- Campaigns, jobs, reports, approvals và AI copilot.

## Visual Direction

- Nhận diện sản phẩm là `Ads Meta Master`, dùng subtitle `Meta Ads Automation` và custom SVG loop/infinity mark màu xanh cho sidebar, account mark và favicon; brand trong sidebar không dùng tile nền, footer account dùng cùng biểu tượng ở kích thước nhỏ và màu indigo dịu. Đây là biểu tượng riêng, không dùng logo chính thức của Meta/Facebook.
- Sidebar cố định dùng nền trắng với warm-peach glow rất nhẹ nối sang topbar; navigation được chọn là điểm neo indigo duy nhất trong sidebar.
- Tone `Meta Light Focus`: brand/data accent dùng Meta blue `#0866FF`, primary action và selected navigation dùng indigo `#4F46E5`, success/online dùng green `#16865F`, pending dùng amber `#A76513`; error, blocker và destructive action giữ red `#B83A3A`.

## Shared Patterns

- KPI strip chỉ hiển thị số có ý nghĩa vận hành.
- Tables/lists hỗ trợ search, filter, status badge và row action rõ ràng.
- Action có rủi ro dùng review drawer/modal trước khi confirm.
- Browser session có state panel riêng; không nhúng URL noVNC vào DOM trước khi được cấp quyền.
- Loading, empty, error và waiting-for-user là các trạng thái bắt buộc.
- Feedback cấp trang dùng toast cố định ở góc phải, không chiếm layout; có nút đóng và tự ẩn sau khoảng 5 giây. Cảnh báo cần đọc hoặc thao tác lâu bên trong form/dialog vẫn giữ inline.
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
- Không dùng persistent safety banner trên page hoặc form dialog. Ý nghĩa an toàn phải nằm trong tên action và workflow cụ thể như `Tạo bản nháp`, `Dừng ở Review`; confirm publish/budget thật vẫn phải hiển thị account, campaign và số tiền trước khi thực thi.
- Trang Báo cáo dùng table-first layout: ad account filter, bốn KPI gần nhất, snapshot history, schedule và report job history.
- Manual report dialog luôn yêu cầu `THU THẬP KPI`; schedule nói rõ timezone, lookback và Telegram token không được nhập trên UI.
- Report job tách trạng thái thu thập khỏi trạng thái Telegram để lỗi gửi tin không làm mất snapshot.
- Trang `Bot VPS` dùng một table duy nhất; mỗi worker có action `Sửa`, `Drain/Kích hoạt`, `Gỡ khỏi VPS`, `Xóa kết nối`, và action rủi ro luôn mở popup xác nhận.
- Operation log của `Bot VPS` phân trang ở server theo 10 entry; `Xóa trang` có confirm, chỉ xóa entry terminal (`succeeded`/`failed`) và luôn giữ thao tác đang chờ/chạy.
- Popup cài worker nhóm rõ `SSH`, `Source`, `Hermes Agent` và `Telegram`; password/API key/token dùng password input, không render lại sau submit và operation chỉ hiển thị tiến độ không chứa secret.
- Add Bot yêu cầu Telegram Bot Token cùng allowlist user ID; copy phải nói rõ token chỉ truyền một lần, nhiều user ID phân tách bằng dấu phẩy và không có chế độ allow-all.
- Trang `Hermes Agents` bắt buộc chọn worker trước khi sửa provider; API key luôn masked và để trống nghĩa là giữ key hiện tại.
- Popup cài worker điền sẵn canonical GitHub repo nhưng vẫn là input sửa được; DeepSeek V4 Flash 0731 là preset đầu tiên, còn model API canonical giữ `deepseek-v4-flash`.
- Hermes Agents và popup cài Bot VPS dùng cùng hai control `Thinking` và `Reasoning effort`; popup sửa Bot VPS không lặp lại provider settings.
- Hermes Agents có control `Quyền Agent` theo worker. `Ads Safe` là mặc định; `Experimental Full Access` hiển thị cảnh báo inline về quyền terminal/file/code/browser/computer/delegation và nói rõ session mới hoặc `/reset` mới nhận bộ quyền.
- Footer sidebar dùng account button `Admin` mở menu tài khoản; không hiển thị tenant name, role hoặc module/session context. Menu chứa action đăng nhập preview, đổi mật khẩu và đăng xuất; dialog đổi mật khẩu dùng chung phải xác minh mật khẩu hiện tại, yêu cầu tối thiểu 4 ký tự và báo rõ các phiên khác sẽ bị đăng xuất.
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

## Canonical Meta Light Focus

- Ba prototype so sánh tại `docs/ui-prototypes/` được giữ làm lịch sử thiết kế; `Meta Light Focus` là visual canonical của app chính.
- Cả ba giữ sidebar-left/main-content, dùng cùng component anatomy cho Dashboard, Login, native dialogs, tables, empty state, search/filter, popovers và campaign checkpoint progress.
- `Meta Light Focus` dùng sidebar trắng, canvas `#F1F4F8`, custom loop mark `#0866FF`, primary action `#4F46E5` và login lấy identity gradient xanh–tím–hồng từ phương án A; slug cũ `meta-dark-sidebar-glass` được giữ để URL review không đổi.
- Typography canonical dùng `Inter` cho body/navigation/data và `Be Vietnam Pro` cho display headings/values; topbar breadcrumb là `12px`, page title `20px/1.25`, search input `13px`, button label `12px/650`, còn section heading `15px/1.45`.
- Brand và footer sidebar dùng nền trắng trung tính để navigation là vùng điều hướng chính. Custom loop mark đứng độc lập, không có tile; footer dùng cùng mark với màu indigo dịu, không tạo thêm mảng màu cạnh tranh với selected navigation.
- Workspace của `Meta Light Focus` không giới hạn `max-width`; panel giãn theo toàn bộ main column với gutter `20px` ở desktop/tablet và `12px` ở mobile để dữ liệu lớn, rõ và sát mép hơn.
- `Ad accounts` là route setup riêng `/ad-accounts`; `Công việc quảng cáo` là route monitoring `/campaigns`. Cả hai dùng cùng app shell, KPI strip, section/table anatomy và visual tokens canonical.
- Filter đầu trang nằm trong content gutter chuẩn và có khoảng cách đáy riêng trước KPI/panel; không dùng margin ngang hoặc margin-top lặp lại làm lệch nhịp topbar.
- Main shell giữ `height: 100vh` với topbar cố định và `.content-pane` cuộn độc lập; nhờ vậy scrollbar không làm co sidebar/topbar và gutter/panel width giữ đúng prototype. Account table dùng layout cố định theo tỷ lệ canonical `19% / 25.3% / 8.45% / 17.41% / 17.12% / 12.72%` để empty state không làm trôi cột.
- `Meta Light Focus` tách vai trò màu để tăng scanability: logo/ad-account dùng Meta blue `#0866FF`; primary CTA và selected navigation dùng indigo đậm `#4F46E5` với hover `#4338CA`; campaign draft dùng indigo; pending dùng amber; approved/resource dùng green. Inactive sidebar text dùng slate `#344054`; brand/footer trung tính để selected row là điểm neo duy nhất trong sidebar.
- Canvas giữ base neutral gần trắng; một ellipse glow warm-peach rất nhạt có chung tâm tại góc viewport trên trái, nối liên tục qua sidebar và topbar rồi tan trước vùng content/KPI. Glow không nằm sau table/card. Panel dùng border và shadow nông; header bỏ accent line. Section helper copy trong header được ẩn ở density desktop canonical để title và action giữ một hàng gọn; icon Lucide `17px` đứng độc lập, không dùng tile nền. Table/KPI tăng cỡ chữ metadata, row height và spacing thay vì thêm panel trang trí.
- KPI dùng value và vạch đáy cùng semantic accent. Mỗi panel chỉ giữ một section icon màu ở header: Ad accounts xanh, Campaign drafts indigo, Meta resources green; table header và border có contrast cao hơn nhưng shadow vẫn shallow.
- KPI của `Meta Light Focus` dùng một strip liền có vertical divider; icon Lucide `14px` nằm bên phải label trong cùng grid row, không có tile nền. Value là focal point ở hàng riêng và vạch semantic accent được căn giữa đáy từng ô; mobile chuyển thành lưới `2×2` trong cùng một surface.
- Fidelity giữa prototype và app chính phải bao gồm cả SVG path và component anatomy, không dùng icon tự vẽ gần giống. Sidebar dùng đúng `users-round`, `credit-card`, `layout-dashboard`, `chart-no-axes-combined`, `server-cog`, `bot`, `messages-square`; custom loop mark dùng `viewBox="0 0 42 28"`, path và stroke `2.8` giống canonical prototype.
- Topbar production phải bám đúng anatomy prototype: breadcrumb + page title ở trái, search trong trang, notification bell có popover và primary CTA ở phải. Search lọc các table row hiện có, hỗ trợ phím `/` nhưng không hiện shortcut keycap; notification lấy số cảnh báo thật từ KPI/page state, không dùng dữ liệu minh họa giả.
- Breadcrumb dùng hai icon cùng box `13px` (bao gồm chevron `>`), khoảng cách `6px`; sidebar giữ icon Lucide `17px`, gap `11px`, nav row `42px` và padding ngang `12px` để vị trí icon không lệch giữa các route.
- Topbar action group dùng gap `18px`; search icon là `16px`, notification `17px`, action icon `15px`, tất cả stroke `2px`. Section header icon dùng box `18px`, stroke `2px`; active nav giữ `border-left: 1px` để content bắt đầu tại cùng x-position với prototype. Loop mark production dùng inline SVG với visual box `38×26px` ở brand và `28×19px` ở footer, không scale kín asset ngoài.
- Dialog dùng header phẳng với border phân tách mảnh, không có accent line hoặc icon tile. `/ad-accounts` giữ dialog setup resource; `/campaigns` chỉ có detail timeline của agent work. Single-select giữ mật độ gần native select: popover cách trigger `4px`, bo `10px`, option cao `31px` dạng hàng chữ không checkbox. Dialog body và menu dài vẫn dùng scrollbar mảnh bo tròn nằm gọn trong surface. Danger/destructive giữ `#B83A3A`.
- Jinja templates, shared CSS và interaction layer của app chính phải dùng bộ token, layout và component anatomy này. Prototype chỉ còn là reference snapshot; source production là `backend/app/templates/**` và `backend/app/static/**`.
- Prototype không gọi API, không dùng production data và không nhúng password mẫu; danger/destructive giữ `#B83A3A` ở cả ba hướng.
