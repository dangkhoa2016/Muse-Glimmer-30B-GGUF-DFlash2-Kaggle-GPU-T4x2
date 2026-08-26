# Pull Request
> 🌐 Language / Ngôn ngữ: [English](PULL_REQUEST_TEMPLATE.md) | **Tiếng Việt**

## Tóm tắt

Mô tả thay đổi và động cơ. Liên kết các issue liên quan (nếu có).

## Khai báo thay đổi hành vi

- [ ] Không thay đổi hành vi runtime.
- [ ] Thay đổi hành vi được khai báo rõ bên dưới.

> Nếu thay đổi generation defaults, thứ tự SSE, `[DONE]` / `finish_reason`,
> ngữ nghĩa busy/429, admission slots, model selection, GPU split, cờ CUDA,
> revision llama.cpp, quantization, hay hành vi prompt/template, hãy giải thích
> lý do và cách bạn xác minh.

## Checklist

- [ ] Tests chạy đạt cục bộ: `./demo-smoke.sh` và `python3 tests/test_public_contract.py`
- [ ] Phạm vi tập trung, dễ review
- [ ] Tài liệu EN/VI song song (cả `*.md` và `*.vi.md` đều cập nhật cùng giá trị)
- [ ] Không đưa secrets
- [ ] Không đưa model binaries (không GGUF/safetensors/weights)
- [ ] Tài liệu đã cập nhật (lệnh/port/giới hạn đồng bộ)
- [ ] Đã tái tạo `SOURCE_MANIFEST.sha256` nếu đổi tệp trong phạm vi (`python3 -B scripts/source_manifest.py write --root .`)