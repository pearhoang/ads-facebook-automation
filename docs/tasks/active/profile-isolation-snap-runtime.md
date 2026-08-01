# profile-isolation-snap-runtime Cô lập Chrome profile trên Snap Chromium

## Goal
- Mỗi Facebook account dùng cookie/user data riêng theo `profile_key` trong noVNC và execution runtime.

## Scope
- `workers/agent/browser_runtime.py`, worker env, regression tests và migration production cho trạng thái cookie lịch sử.

## Constraints
- Không xóa kho cookie dùng chung hoặc profile cũ.
- Không ghi cookie account test vào profile account mới.
- Chỉ restart worker sau khi phiên lỗi đã đóng và không có execution job.

## Current State
- Root cause: `/snap/bin/chromium` làm child process dùng `/root/snap/chromium/common/chromium` dù main process nhận profile UUID.
- Worker đã chuyển sang direct binary, thêm launch guard và deploy production.
- Kho dùng chung đã backup rồi copy nguyên trạng vào đúng profile account test; SHA-256 cookie trùng trước/sau.
- Profile mới launch thành công, process/cookie path tách biệt và CDP trả Meta Business login page.

## Next Steps
- User đăng nhập account mới trong phiên noVNC đang mở và xác nhận session.
- Khi cần, mở lại profile account test để smoke cookie preservation; không cần làm trước khi user hoàn tất login mới.

## Risks
- Snap revision thay đổi đường dẫn vật lý; symlink `/snap/chromium/current` và launch guard là boundary chống regression.
