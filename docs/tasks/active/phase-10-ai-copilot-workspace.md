# Phase 10 — AI Copilot workspace

## Mục tiêu

- Biến `/ai-copilot` thành workspace hội thoại dùng session/API thật của Hermes.
- Cho phép tiếp tục session Telegram trên web mà không tạo một ngữ cảnh AI riêng.
- Chuyển provider/model settings sang khu vực `Hermes Agents` theo từng worker.
- Giữ ngôn ngữ tự nhiên là luồng chính; shortcut chỉ xuất hiện khi có action/resource cụ thể.

## Phạm vi

- Control-plane: conversation mirror, message mirror, agent job queue và tenant authorization.
- Worker: outbound bridge tới Hermes API Server chạy local, đồng bộ session/message và thực thi chat turn.
- UI: danh sách hội thoại, chat thread, composer, chọn worker/profile, đồng bộ Telegram.
- Settings: trang Hermes Agents riêng; bỏ provider settings trùng lặp khỏi popup sửa worker.

## Guardrails

- `agent/` chỉ gọi typed tools; không truy cập database trực tiếp.
- Action có thể tiêu tiền vẫn tạo draft hoặc yêu cầu approval rõ ràng.
- Hermes API Server chỉ bind localhost; API key không đi tới browser/control-plane.
- Shortcut tối đa hai mục và không vô hiệu hóa ô nhập ngôn ngữ tự nhiên.

## Kế hoạch

- [x] Thêm schema/migration/API cho conversation, message và agent job.
- [x] Thêm worker bridge tới Hermes API Server và session sync.
- [x] Tách trang Hermes Agents khỏi AI Copilot/Bot VPS.
- [x] Xây AI Copilot UI natural-first và resume Telegram session.
- [x] Biến Add Bot thành one-shot bootstrap gồm Hermes provider, Telegram token và allowlist mà không persist token tại control-plane.
- [x] Kiểm thử contract, tenant boundary, UI/API và worker bridge.
- [ ] Deploy, migrate và smoke test production.

## Tiêu chí hoàn thành

- Web nhìn thấy và mở được session Telegram đã có.
- Gửi tin nhắn web vào đúng Hermes session và nhận phản hồi trở lại.
- Tạo được chat web mới cho Ads Copilot.
- Provider settings chỉ còn một canonical UI tại Hermes Agents.
- Không có generic action buttons dưới mọi câu trả lời.
