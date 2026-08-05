# Account Session

## Responsibility

- Quản lý Facebook account record, persistent Chrome profile và phiên noVNC dùng để login/checkpoint/2FA.
- Không quản lý campaign automation hoặc KPI reporting.
- UI setup canonical là `/`, gộp Facebook profile, ad account và Meta resource theo đúng thứ tự định tuyến; `/ad-accounts` chỉ redirect tương thích.

## Planned Flow

1. User tạo Facebook account/profile record.
2. Backend gán profile cho một worker online.
3. User yêu cầu mở session.
4. Worker poll và khởi động Xvfb/Openbox/Chromium/x11vnc/websockify.
5. Backend trả temporary noVNC access URL.
6. User tự đăng nhập hoặc xác minh.
7. Worker phát hiện session ổn định; user/backend confirm.
8. Session đóng nhưng persistent Chrome profile được giữ lại.

## Planned States

- `requested`
- `starting`
- `awaiting_user`
- `ready`
- `closing`
- `closed`
- `failed`
- `expired`

## Invariants

- Một profile chỉ có một active session.
- Automation lock và human-control lock loại trừ lẫn nhau.
- Không lưu password, OTP hoặc recovery code.
- URL noVNC có TTL và bị thu hồi khi session đóng.
- Production TTL hiện là `120` phút để đủ thời gian login/2FA và khảo sát UI; user/backend vẫn có thể đóng sớm và worker phải giải phóng profile lock.
- Worker/profile ownership được kiểm tra ở mọi poll/sync/action.
- Human handoff chỉ nhận `launch_url` HTTPS thuộc `*.facebook.com` với Ads Manager path; URL được truyền qua backend assignment tới browser runtime, không mở CDP/noVNC trực tiếp.
- Snap Chromium phải được unwrap sang direct binary; main/child process và cookie database phải nằm dưới exact `<profile_root>/<profile_key>`.

## Production Evidence

- Account test lịch sử dùng profile `2d67ab0a-ac12-45b0-b2b4-410c16b1202f`; account `stable difusion page` dùng profile riêng `d8824f1a-994c-425a-b49e-91a85a21a553`.
- Sau fix, tất cả Chromium process của phiên mới dùng `d8824f1a-...`, không còn process dùng `/root/snap/chromium/common/chromium`.
- CDP của profile mới trả Meta Business/Ads Manager đúng account; các phiên khảo sát E2E đã đóng sạch trước khi worker chạy draft builder.

## Reuse Candidates

- `workers/agent/browser_runtime.py`
- `workers/agent/browser_sessions.py`
- Browser session worker API và UI state patterns từ `Youtube_Upload_Lush`.

## Related Decisions

- `DEC-001`
- `DEC-004`
- `DEC-006`
- `DEC-017`
