# Publication Evidence
> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](PUBLICATION_EVIDENCE.vi.md)

The public `v1.0.0` release separates **release-build/export evidence** from
**executed Kaggle publication-run evidence**.

The existing portable release evidence proves deterministic source/export
packaging. The publication evidence below proves a successful real Kaggle
NVIDIA T4 x2 notebook run against the frozen `v1.0.0` runtime source.

## Canonical publication run

| Item | Value |
| --- | --- |
| Run ID | `20260906T115701Z` |
| Runtime source tag | `v1.0.0` |
| Resolved runtime source HEAD | `9e4588c49144c00f38ae0799da16bfbf19dd495d` |
| Hardware | Kaggle NVIDIA T4 x2 |
| GPU0 model-residency delta | `8825 MiB` |
| GPU1 model-residency delta | `9325 MiB` |
| Target GGUF SHA-256 | `0d3fc85f61d10fdc84072f0bba6005d61c1ac5605a2627b0fd5ea4ff8194c384` |
| DFlash2 GGUF SHA-256 | `93dbfb6f88e4645dec1347cf93f9d6fc80b90d413038722385b2a8e53565c949` |
| Non-stream generation | PASS |
| SSE generation / terminal `[DONE]` | PASS |
| Semantic sanity | PASS (`104`) |
| DFlash2 activity | PASS (`1395` drafted / `455` accepted, `32.62%`) |
| Bearer-authenticated gateway | PASS |
| Quick Tunnel transport | PASS |
| Secret scan / cleanup | PASS |
| Overall production demo | PASS |

The DFlash2 total is the sum of all three real inference requests:

- non-stream: `705 / 186` drafted / accepted;
- SSE: `480 / 170`;
- semantic sanity: `210 / 99`;
- total: `1395 / 455`.

These are observed single-run measurements. They demonstrate that speculative
drafting was active; they are **not** a DFlash2-vs-baseline speedup benchmark.

## Release assets

- [`muse-glimmer-30b-v1.0.0-publication-evidence.zip`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-publication-evidence.zip)
- [`muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256)
- [`muse-glimmer-30b-v1.0.0-review-summary.txt`](https://github.com/dangkhoa2016/Muse-Glimmer-30B-GGUF-DFlash2-Kaggle-GPU-T4x2/releases/download/v1.0.0/muse-glimmer-30b-v1.0.0-review-summary.txt)

Publication evidence ZIP SHA-256:

```text
131d1bfcd4365e5c03c07feec3b969e558bbd2f846b65a416454e80a81cf2ca6
```

The ZIP contains:

```text
muse-glimmer-30b-v1.0.0-demo-evidence.json
muse-glimmer-30b-v1.0.0-interaction-evidence.json
muse-glimmer-30b-v1.0.0-review-summary.txt
muse-glimmer-30b-v1.0.0-SHA256SUMS
```

The JSON evidence files are byte-for-byte preserved from the successful run.
The reviewer summary is a presentation-only correction that surfaces the
semantic-sanity DFlash2 counters and explicitly describes the auto-generated
credential as an ephemeral runtime file.

## Verification

Download the ZIP and its sidecar, then verify the outer artifact:

```bash
sha256sum -c muse-glimmer-30b-v1.0.0-publication-evidence.zip.sha256
```

Verify the files inside the bundle:

```bash
rm -rf muse-publication-evidence
mkdir muse-publication-evidence
unzip -q muse-glimmer-30b-v1.0.0-publication-evidence.zip -d muse-publication-evidence
(
  cd muse-publication-evidence
  sha256sum -c muse-glimmer-30b-v1.0.0-SHA256SUMS
)
```

The expected outer SHA-256 is:

```text
131d1bfcd4365e5c03c07feec3b969e558bbd2f846b65a416454e80a81cf2ca6
```

## Notebook source versus executed evidence

[`notebooks/kaggle-production.ipynb`](../notebooks/kaggle-production.ipynb)
is the clean, reusable publication source. It has no committed execution
outputs or embedded credential values.

The publication evidence ZIP is a separate review artifact from the successful
executed run. The clean notebook includes Stop / Reset / Re-run controls:

- `muse_stop()` stops the owned tunnel, proxy, and backend;
- `muse_reset(preserve_evidence=True)` clears runtime state while preserving
  evidence;
- `muse_reset(preserve_evidence=False)` also removes publication evidence;
- a later **Run All** can reuse the same Kaggle notebook instead of creating a
  new notebook.

The evidence bundle captures one successful qualification run. It does not
claim that a complete second Run All was separately qualified.

## Credential boundary

When a Kaggle Secret is not configured, the notebook may create a
cryptographically secure temporary token under `/kaggle/working/.muse-secrets/`.

For the recorded publication run:

- the temporary token file used mode `0600`;
- the raw token was never published in the evidence bundle;
- interaction evidence stores `Authorization: Bearer <REDACTED>`;
- publication secret scans passed;
- the generated runtime token was deleted during cleanup.

## Claim boundary

This evidence demonstrates the tested deployment/runtime/API behavior,
dual-GPU model residency, real non-stream/SSE generation, a deterministic
semantic sanity task, DFlash2 speculative activity, authenticated gateway
behavior, optional Quick Tunnel transport, integrity checks, and cleanup.

It does **not** claim SLA, high availability, multi-tenancy, mTLS, service
mesh, or DFlash2 speedup versus a matched baseline.
