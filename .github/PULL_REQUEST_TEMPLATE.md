# Pull Request
> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](PULL_REQUEST_TEMPLATE.vi.md)

## Summary

Describe the change and its motivation. Link any related issues.

## Behavior change declaration

- [ ] No runtime behavior change.
- [ ] Behavior change explicitly declared below.

> If this changes generation defaults, SSE order, `[DONE]` / `finish_reason`,
> busy/429 semantics, admission slots, model selection, GPU split, CUDA flags,
> the llama.cpp revision, quantization, or prompt/template behavior, explain
> why and how you verified it.

## Checklist

- [ ] Tests pass locally: `./demo-smoke.sh` and `python3 tests/test_public_contract.py`
- [ ] Scope is focused and reviewable
- [ ] EN/VI documentation parity is maintained (both `*.md` and `*.vi.md` updated with the same values)
- [ ] No secrets introduced
- [ ] No model binaries introduced (no GGUF/safetensors/weights)
- [ ] Documentation updated (commands/ports/limits are in sync)
- [ ] `SOURCE_MANIFEST.sha256` regenerated if scoped files changed (`python3 -B scripts/source_manifest.py write --root .`)