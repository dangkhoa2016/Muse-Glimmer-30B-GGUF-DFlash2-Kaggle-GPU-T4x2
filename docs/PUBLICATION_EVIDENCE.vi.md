# Bằng chứng Publication
> 🌐 Language / Ngôn ngữ: [English](PUBLICATION_EVIDENCE.md) | **Tiếng Việt**

Public release `v1.0.0` tách rõ **bằng chứng build/export release** khỏi
**bằng chứng publication run thực thi trên Kaggle**.

Portable release evidence hiện có chứng minh quy trình đóng gói source/export
xác định. Publication evidence dưới đây chứng minh một lần chạy notebook thực
trên Kaggle NVIDIA T4 x2 thành công với runtime source `v1.0.0` đã khóa.

## Publication run canonical

| Mục | Giá trị |
| --- | --- |
| Run ID | `20260906T115701Z` |
| Runtime source tag | `v1.0.0` |
| Runtime source HEAD đã resolve | `9e4588c49144c00f38ae0799da16bfbf19dd495d` |
| Phần cứng | Kaggle NVIDIA T4 x2 |
| Delta model residency GPU0 | `8825 MiB` |
| Delta model residency GPU1 | `9325 MiB` |
| SHA-256 target GGUF | `0d3fc85f61d10fdc84072f0bba6005d61c1ac5605a2627b0fd5ea4ff8194c384` |
| SHA-256 DFlash2 GGUF | `93dbfb6f88e4645dec1347cf93f9d6fc80b90d413038722385b2a8e53565c949` |
| Non-stream generation | PASS |
| SSE generation / terminal `[DONE]` | PASS |
| Semantic sanity | PASS (`104`) |
| DFlash2 activity | PASS (`1395` drafted / `455` accepted, `32.62%`) |
| Gateway xác thực Bearer | PASS |
| Quick Tunnel transport | PASS |
| Secret scan / cleanup | PASS |
| Overall production demo | PASS |

Tổng DFlash2 là tổng của cả ba inference request thực:

- non-stream: `705 / 186` drafted / accepted;
- SSE: `480 / 170`;
- semantic sanity: `210 / 99`;
- tổng: `1395 / 455`.

Đây là measurement quan sát được trong một run. Chúng chứng minh speculative
drafting thực sự hoạt động; chúng **không** phải benchmark speedup
DFlash2-vs-baseline.

## Release assets

- [`muse-glimmer-30b-v1.0.0-publication-evidence.zip`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-publication-evidence.zip)
- [`muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256)
- [`muse-glimmer-30b-v1.0.0-review-summary.txt`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-review-summary.txt)

SHA-256 của publication evidence ZIP:

```text
131d1bfcd4365e5c03c07feec3b969e558bbd2f846b65a416454e80a81cf2ca6
```

ZIP chứa:

```text
muse-glimmer-30b-v1.0.0-demo-evidence.json
muse-glimmer-30b-v1.0.0-interaction-evidence.json
muse-glimmer-30b-v1.0.0-review-summary.txt
muse-glimmer-30b-v1.0.0-SHA256SUMS
```

Hai JSON evidence được giữ nguyên byte-for-byte từ successful run. Reviewer
summary chỉ được hiệu chỉnh ở tầng trình bày để hiển thị counter DFlash2 của
semantic sanity và mô tả rõ credential tự sinh là file runtime tạm thời.

## Xác minh

Tải ZIP và sidecar rồi xác minh artifact bên ngoài:

```bash
sha256sum -c muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256
```

Xác minh từng file bên trong:

```bash
rm -rf muse-publication-evidence
mkdir muse-publication-evidence
unzip -q muse-glimmer-30b-v1.0.0-publication-evidence.zip -d muse-publication-evidence
(
  cd muse-publication-evidence
  sha256sum -c muse-glimmer-30b-v1.0.0-SHA256SUMS
)
```

SHA-256 bên ngoài dự kiến:

```text
131d1bfcd4365e5c03c07feec3b969e558bbd2f846b65a416454e80a81cf2ca6
```

## Notebook source và executed evidence

[`notebooks/kaggle-production.ipynb`](../notebooks/kaggle-production.ipynb)
là publication source sạch, tái sử dụng được. Notebook tracked không chứa
execution output hay credential value.

Publication evidence ZIP là review artifact riêng của successful executed run.
Notebook sạch có các control Stop / Reset / Re-run:

- `muse_stop()` dừng tunnel, proxy và backend thuộc ownership của notebook;
- `muse_reset(preserve_evidence=True)` reset runtime state nhưng giữ evidence;
- `muse_reset(preserve_evidence=False)` xóa cả publication evidence;
- lần **Run All** tiếp theo có thể dùng lại chính notebook Kaggle đó mà không
  cần tạo notebook mới.

Evidence bundle ghi lại một qualification run thành công. Nó không claim rằng
một full Run All lần hai đã được qualification riêng.

## Biên credential

Khi Kaggle Secret chưa được cấu hình, notebook có thể tạo token tạm thời an
toàn bằng cơ chế mật mã dưới `/kaggle/working/.muse-secrets/`.

Trong publication run đã ghi nhận:

- file token tạm dùng mode `0600`;
- raw token không được publish trong evidence bundle;
- interaction evidence lưu `Authorization: Bearer <REDACTED>`;
- publication secret scan PASS;
- token runtime tự sinh được xóa khi cleanup.

## Biên claim

Evidence này chứng minh deployment/runtime/API behavior đã kiểm thử,
dual-GPU model residency, non-stream/SSE generation thực, deterministic
semantic sanity task, DFlash2 speculative activity, authenticated gateway,
Quick Tunnel tùy chọn, integrity checks và cleanup.

Evidence **không** claim SLA, high availability, multi-tenancy, mTLS,
service mesh hay DFlash2 speedup so với matched baseline.
