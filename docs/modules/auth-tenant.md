# Authentication And Tenant

## Responsibility

- Quản lý application user, password hash, tenant membership và phiên đăng nhập web.
- Cấp `tenant_id` canonical cho user API và browser proxy.
- Không quản lý Facebook credential, OTP hoặc recovery code.

## Entry Points

- `backend/app/api/auth.py`: login, current user, đổi mật khẩu và logout.
- `backend/app/services/auth.py`: Argon2 verification, opaque session, CSRF và provisioning.
- `backend/app/dependencies.py`: principal, tenant và CSRF dependencies.
- `python -m backend.app.cli provision-admin`: tạo/cập nhật owner ngoài public web.

## Invariants

- Password chỉ lưu dưới dạng Argon2 hash.
- Session token và CSRF token chỉ lưu SHA-256 digest trong database.
- Session cookie là `Secure`, `HttpOnly`, `SameSite=Lax`; CSRF cookie là `Secure`, `SameSite=Strict`.
- Mọi user mutation API phải có authenticated session và matching `X-CSRF-Token`.
- Browser WebSocket phải đúng session tenant và `Origin` canonical ở production.
- Không dùng `X-Dev-Tenant-ID` trong production và không có public signup.
- Đổi mật khẩu phải xác minh mật khẩu hiện tại, giữ phiên đang thao tác và revoke mọi phiên khác của cùng user.

## Current Limits

- Đã có self-service đổi mật khẩu; chưa có recovery/reset khi quên mật khẩu, invite flow hoặc UI quản trị user.
- Chưa có login rate limiting phân tán; cần bổ sung trước khi mở rộng user/public traffic.
- Một user có nhiều membership phải truyền workspace khi login; UI workspace switcher chưa có.
- Production auth state hiện nằm trong PostgreSQL và schema được quản lý bằng Alembic.

## Related Decisions

- `DEC-009`
