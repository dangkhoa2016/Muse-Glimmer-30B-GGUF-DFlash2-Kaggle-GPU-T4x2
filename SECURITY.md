# Security Policy
> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](SECURITY.vi.md)

## Supported version

The public supported version is:

| Version | Supported |
| --- | --- |
| v1.0.0 | Yes |

Only the single public release `v1.0.0` is supported. Anything not tagged
`v1.0.0` in this repository is not a supported release.

## Responsibility model

- This repository is a **self-hosted, reference implementation**. The
  maintainer does **not** operate hosted inference, and there is no SLA.
- As the operator you are responsible for your own Kaggle account, your GPU
  quota, your credentials, and any public exposure you create.
- The maintainer does not require your credentials. A cloudflare quick/named
  tunnel publishes the gateway to the Internet; use a strong
  `MUSE_API_TOKEN` (32+ printable characters) and rotate it as needed.

## Reporting a vulnerability

Please report security issues privately to the maintainer:

```text
i.am@dangkhoa.dev
```

Include, when available and relevant:

- the environment you ran (Kaggle session type, GPU, Python version);
- the exact command(s) that triggered the issue;
- reproduction steps;
- expected vs. actual behavior;
- relevant logs and, for runtime suspicions, the resolved runtime commit
  and model SHA-256 values.

Do **not** include bearer tokens, passwords, cookies, SSH keys, private URLs,
or other credentials in reports, logs, or issue posts.

## What to expect

- Acknowledgment of the report.
- A triage decision and, for accepted findings, a fix in the supported release
  with the appropriate changelog note.
- The source integrity contract (`SOURCE_MANIFEST.sha256`) is enforced in
  strict mode at startup; unexpected runtime changes should be treated as
  suspicious and reported.

## Handling of secrets in this repository

- The gateway never logs or persists bearer tokens, prompts, completions,
  reasoning, or raw request bodies; telemetry carries counters only.
- Do not commit `.env` files, tokens, or any generated state from
  `artifacts/` (all ignored by `.gitignore`).