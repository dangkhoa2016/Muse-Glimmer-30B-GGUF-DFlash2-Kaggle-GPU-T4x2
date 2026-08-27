# Chính sách bảo mật
> 🌐 Language / Ngôn ngữ: [English](SECURITY.md) | **Tiếng Việt**

## Version được hỗ trợ

Public version được hỗ trợ:

| Version | Được hỗ trợ |
| --- | --- |
| v1.0.0 | Có |

Chỉ public release duy nhất `v1.0.0` được hỗ trợ. Bất cứ thứ gì không được
gắn tag `v1.0.0` trong repository này đều không phải release được hỗ trợ.

## Mô hình trách nhiệm

- Repository này là **reference implementation tự-host**. Người duy trì
  **không** vận hành hosted inference, và không có SLA.
- Là operator, bạn chịu trách nhiệm về tài khoản Kaggle của mình, GPU quota,
  credentials và mọi kênh public bạn tạo ra.
- Người duy trì không yêu cầu credentials của bạn. Một tunnel cloudflare
  quick/named đưa gateway lên Internet; hãy dùng `MUSE_API_TOKEN` mạnh (≥ 32
  ký tự in được) và xoay vòng khi cần.

## Báo cáo lỗ hổng

Hãy báo các vấn đề bảo mật riêng tư cho người duy trì:

```text
i.am@dangkhoa.dev
```

Kèm theo, khi có và liên quan:

- môi trường bạn đã chạy (loại phiên Kaggle, GPU, version Python);
- (các) lệnh chính xác gây ra vấn đề;
- các bước tái hiện;
- hành vi mong đợi so với thực tế;
- log liên quan và, nếu nghi runtime, commit runtime đã giải quyết và giá trị
  SHA-256 của mô hình.

**Không** đưa bearer tokens, mật khẩu, cookies, SSH keys, URL riêng tư, hay
credentials khác vào báo cáo, log, hoặc bài đăng issue.

## Điều bạn có thể mong đợi

- Xác nhận nhận được báo cáo.
- Quyết định phân loại và, với lỗi được chấp nhận, bản sửa trong release được
  hỗ trợ kèm ghi chú changelog tương ứng.
- Ràng buộc toàn vẹn nguồn (`SOURCE_MANIFEST.sha256`) được thực thi ở chế độ
  strict khi start; thay đổi runtime bất thường nên được coi là đáng ngờ và
  được báo lên.

## Xử lý secrets trong repository này

- Gateway không bao giờ ghi log hay lưu bearer tokens, prompts, completions,
  reasoning, hay raw request bodies; telemetry chỉ chứa counter.
- Không commit các tệp `.env`, tokens, hay bất kỳ state nào sinh ra từ
  `artifacts/` (tất cả bị `.gitignore` bỏ qua).