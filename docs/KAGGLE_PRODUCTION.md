# Kaggle Production Notebook
> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](KAGGLE_PRODUCTION.vi.md)

The canonical production notebook for the public `v1.0.0` release is:

`notebooks/kaggle-production.ipynb`

It is an operator-focused Kaggle NVIDIA T4 x2 notebook that uses the frozen public repository as the runtime source rather than reimplementing the serving stack.

## What the notebook validates

A complete run validates:

- exactly two NVIDIA T4 GPUs with the required visible VRAM;
- the exact target GGUF, DFlash2 draft GGUF, and prebuilt llama.cpp runtime inputs;
- the frozen `v1.0.0` Git source identity and `SOURCE_MANIFEST.sha256`;
- secure `MUSE_API_TOKEN` handling, including a temporary-file fallback when a Kaggle Secret is unavailable;
- the canonical local backend and Bearer-authenticated gateway;
- one real non-streaming generation with visible assistant content;
- one real SSE generation with visible streamed content, a terminal finish reason, and `[DONE]`;
- optional Cloudflare Quick Tunnel transport independently from local model/runtime health;
- deterministic evidence and cleanup, including deletion of any notebook-generated token.

## Runtime boundaries

The notebook is a production-style reference workflow, not a managed hosted service.

The local model/runtime qualification is authoritative for the serving core. Quick Tunnel is an optional transport layer and is evaluated separately so external DNS or tunnel instability does not erase a valid local inference result.

The notebook keeps the public request cap at `max_tokens=512`, uses the model-native request template setting `reasoning_strength=low`, and applies a notebook-owned auth-proxy backend response timeout of 120 seconds without changing the frozen repository source tree.

## Required Kaggle inputs

Attach:

- `bartowski-muse-glimmer-30b-gguf`
- `incoai-muse-glimmer-30b-dflash2-gguf`
- `muse-glimmer-30b-dflash2-llama-runtime`

The notebook discovers nested Kaggle model/dataset mounts recursively.

## Recommended secret

Create a Kaggle Secret:

`MUSE_API_TOKEN`

Use at least 32 printable characters.

If the secret is missing, the notebook creates a cryptographically secure temporary token under:

`/kaggle/working/.muse-secrets/MUSE_API_TOKEN`

The directory uses mode `0700`, the file uses mode `0600`, the token value is never printed, and normal cleanup deletes the generated file.

## Run procedure

1. Select **GPU T4 x2**.
2. Enable Internet for the repository clone and optional Quick Tunnel.
3. Attach the three required inputs.
4. Optionally configure `MUSE_API_TOKEN`.
5. Use **Restart Session → Run All**.
6. Review the final evidence and verdict lines before publishing notebook output.

A successful release qualification should include:

```text
KAGGLE_T4X2_GATE=PASS
ATTACHED_INPUT_GATE=PASS
FROZEN_SOURCE_IDENTITY=PASS
CANONICAL_ENVIRONMENT=PASS
LOCAL_AUTH_GATEWAY=PASS
LOCAL_NONSTREAM_DEMO=PASS
LOCAL_SSE_DEMO=PASS
VISIBLE_ANSWER_GATE=PASS
CORE_PRODUCTION_DEMO=PASS
PUBLIC_QUICK_TUNNEL=PASS
OVERALL_PRODUCTION_DEMO=PASS
AUTO_CLEANUP=PASS
GENERATED_TOKEN_CLEANUP=PASS
FORENSIC_CAPTURE_COUNT=0
FINAL_FORENSIC_ZIP=NOT_CREATED_THIS_RUN
FINAL_NOTEBOOK_RESULT=PASS
NOTEBOOK_EXECUTION_COMPLETED=PASS
```

## Publication rule

The repository notebook is published clean, with no cell outputs and no embedded credentials.

Executed qualification notebooks and operational evidence are review artifacts; they are not committed as the canonical source notebook.

Before repository publication, verify the tracked notebook SHA-256 against:

`notebooks/kaggle-production.ipynb.sha256`
