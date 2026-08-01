# Copilot Attachments And Commands

## Goal

- Khôi phục Web chat sau lỗi Hermes API Server không nhận provider credential.
- Hỗ trợ tệp văn bản/dữ liệu có giới hạn và slash shortcut tùy chọn trong AI Copilot.

## Scope

- Hermes systemd environment và worker error boundary.
- API/message payload cho TXT, MD, CSV, JSON, YAML.
- Composer attachment queue và command palette `/help`, `/new`, `/sync`, `/status`.

## Constraints

- DeepSeek V4 là text-only; không quảng cáo image/PDF là đã hỗ trợ.
- Hermes API Server không dispatch messaging slash command và từ chối uploaded document.
- Natural language vẫn là primary interaction; slash command chỉ là shortcut.
- Tệp là untrusted user data, không phải system instruction; không persist binary.

## Verification

- Regression tests cho provider environment, attachment validation/mirroring và safe error.
- Production smoke chat bằng exact Hermes session API sau deploy.
