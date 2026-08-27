# Support
> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](SUPPORT.vi.md)

## What you can expect

This is a self-hosted reference implementation maintained on a best-effort
community basis. There is no hosted inference, no SLA, and no commercial
support contract.

## Where to get help

1. **Read the docs first**
   - [README.md](README.md) — architecture, quick start, configuration, API.
   - [SECURITY.md](SECURITY.md) — reporting vulnerabilities.
   - [CONTRIBUTING.md](CONTRIBUTING.md) — contributing guidelines.
2. **Run the deterministic checks** to confirm your environment baseline:
   ```bash
   ./readiness.sh
   ./demo-smoke.sh
   ```
3. **Open an issue** in this repository with:
   - your environment (Kaggle session type, GPU, Python version);
   - the exact command(s) run;
   - reproduction steps;
   - expected vs. actual behavior;
   - relevant logs (no credentials — see [SECURITY.md](SECURITY.md)).
4. **Do not** post bearer tokens, passwords, cookies, SSH keys, private URLs,
   or `.env` values.

## Unsupported scenarios

Because this project runs on user-owned Kaggle compute, we cannot provide
support for your Kaggle account status, quota, billing, or outage outside the
scope of this repository.

## Security issues

Use the private channel for vulnerabilities:

```text
i.am@dangkhoa.dev
```

Security reports are handled under our [Security Policy](SECURITY.md).