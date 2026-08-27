# Hỗ trợ
> 🌐 Language / Ngôn ngữ: [English](SUPPORT.md) | **Tiếng Việt**

## Điều bạn có thể mong đợi

Đây là reference implementation tự-host được duy trì theo mô hình cộng đồng
best-effort. Không có hosted inference, không SLA, không hợp đồng hỗ trợ
thương mại.

## Nơi nhận trợ giúp

1. **Đọc tài liệu trước**
   - [README.md](README.md) — kiến trúc, khởi động nhanh, cấu hình, API.
   - [SECURITY.md](SECURITY.md) — báo lỗ hổng bảo mật.
   - [CONTRIBUTING.md](CONTRIBUTING.md) — hướng dẫn đóng góp.
2. **Chạy các kiểm tra deterministic** để xác nhận baseline môi trường của bạn:
   ```bash
   ./readiness.sh
   ./demo-smoke.sh
   ```
3. **Mở issue** trong repository này với:
   - môi trường của bạn (loại phiên Kaggle, GPU, version Python);
   - (các) lệnh chính xác đã chạy;
   - các bước tái hiện;
   - hành vi mong đợi so với thực tế;
   - log liên quan (không kèm credentials — xem [SECURITY.md](SECURITY.md)).
4. **Không** đăng bearer tokens, mật khẩu, cookies, SSH keys, URL riêng tư,
   hay giá trị `.env`.

## Kịch bản không được hỗ trợ

Vì dự án này chạy trên compute Kaggle thuộc quyền người dùng, chúng tôi không
thể hỗ trợ trạng thái tài khoản Kaggle, quota, thanh toán, hay sự cố ngoài
phạm vi này của bạn.

## Vấn đề bảo mật

Dùng kênh riêng tư cho lỗ hổng:

```text
i.am@dangkhoa.dev
```

Báo cáo bảo mật được xử lý theo [Security Policy](SECURITY.md).