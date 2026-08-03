# Thiết kế tone Meta Balanced

## Mục tiêu

- Chuyển visual tone của `Ads Meta Master` từ cam/vàng sang blue–indigo–green theo cảm hứng Meta Ads.
- Giữ nguyên màu sidebar hiện tại vì dark navy/slate có thể không hợp với bố cục đang dùng.
- Giữ màu đỏ cho error, blocker và destructive action thật sự.
- Đây là thay đổi tone tạm thời; không redesign layout, component structure, nội dung hoặc interaction flow.

## Palette canonical

| Vai trò | Màu chính | Màu nền nhẹ | Mục đích |
|---|---|---|---|
| Primary blue | `#1877F2` | `#EFF6FF` | primary button, link/action emphasis, focus |
| Primary hover | `#166FE5` | — | hover/pressed của primary action |
| Indigo | `#4F46E5` | `#EEF2FF` | safety boundary, approval, waiting/attention không nguy hiểm |
| Green | `#16865F` | `#ECFDF5` | success, ready, online, completed |
| Danger red | `#B83A3A` | `#FFF3F3` | error, blocker, delete, revoke và destructive action |
| Page background | `#F3F6FB` | — | canvas nội dung chính |
| Subtle surface | `#F7F9FC` | — | table header, selected/secondary surface |
| Border | `#D8E0EB` | — | border thông thường |
| Strong border | `#B8C4D4` | — | input và control border |
| Text | `#172033` | — | nội dung chính |
| Muted text | `#667085` | — | helper text và metadata |

## Mapping component

- `.button-primary`, composer send button và các primary CTA dùng primary blue; hover dùng primary hover.
- Focus border/ring của input, select, textarea và keyboard focus dùng primary blue với ring alpha nhẹ.
- Default `.notice` là informational blue, không còn cam.
- `.notice-success` và positive status dùng green.
- `.safety-banner`, `.session-help`, `.approval-warning` và `.execution-warnings` dùng indigo vì đây là thông tin cần chú ý nhưng không phải lỗi.
- `.execution-blockers`, password error và `.button-danger` tiếp tục dùng danger red.
- `.status.warning` chuyển từ amber sang indigo; `.status.success` dùng green; `.status.danger` giữ red.
- Selected/highlight surface dùng blue-gray hoặc blue tint nhẹ, không dùng gradient hoặc glow.
- Auth page canvas và light product surfaces chuyển sang blue-gray nhẹ; typography, radius và spacing giữ nguyên.

## Phần giữ nguyên

- Sidebar giữ nguyên `#242321`, active navigation `#3A3733`, border và text hiện tại.
- Login brand panel và dark command/terminal panel tiếp tục dùng dark neutral hiện tại.
- Custom brand SVG và favicon giữ nguyên.
- Không thay font, sidebar width, component radius, shadows, spacing, layout hoặc responsive behavior.
- Không thay HTML copy, JavaScript behavior, API, database, route, worker contract hoặc deployment config.

## Loại bỏ màu cũ

Không còn dùng các màu cam/vàng sau trong stylesheet product UI:

- `#D85C36`
- `#BD4827`
- `rgba(216,92,54,.12)`
- `#A76513`
- `#FFF1DC`
- `#EDCF9F`
- `#FFF8ED`
- `#FFF6E9`
- `#714813`

Màu đỏ hiện có không thuộc danh sách loại bỏ.

## Khả năng truy cập và semantic safety

- Không dùng green cho error hoặc destructive action.
- Không dùng red cho informational notice hoặc normal approval flow.
- Button và text quan trọng phải giữ contrast đọc được trên light surface.
- Focus state phải rõ hơn hover state và không dựa chỉ vào thay đổi độ sáng nhỏ.
- Không thay tiếng Việt, encoding UTF-8 hoặc font rendering.

## Kiểm thử và nghiệm thu

- Static CSS response chứa palette canonical mới và không còn các literal cam/vàng bị loại bỏ.
- Auth/workspace integration test vẫn pass; không thay runtime identifier.
- Full `pytest` và Python compile pass.
- Browser smoke local trên ít nhất Workspace, Campaigns và Hermes Agents xác nhận:
  - primary CTA màu blue;
  - safety/approval/warning không còn vàng;
  - success/online dùng green;
  - destructive/error vẫn red;
  - sidebar giữ nguyên màu hiện tại;
  - không có layout hoặc UTF-8 regression.

## Tiêu chí hoàn thành

- UI không còn cảm giác cam/vàng ở action và feedback thông thường.
- Blue là màu tương tác chính, indigo là attention/safety, green là success và red chỉ dành cho danger.
- Sidebar giữ nguyên như yêu cầu.
- Thay đổi chỉ nằm ở theme tone, sẵn sàng để redesign sâu hơn theo mẫu người dùng cung cấp sau này.
