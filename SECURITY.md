# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| latest (main) | ✅ |
| v1.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report via:

1. **GitHub private vulnerability reporting** — click *Security* → *Report a vulnerability* on the repository page
2. **Email** — contact the maintainer via the email on the commit history

You will receive a response within 5 business days. If the issue is confirmed, a fix will be released as soon as possible and you will be credited in the changelog.

## Scope

NatBench benchmarks DNS servers by sending standard DNS queries. It does not store credentials, does not connect to any external service beyond the DNS servers being tested, and has zero mandatory third-party dependencies.

Security-relevant features:

- `--set-dns` / `--apply` modifies `/etc/resolv.conf` (Linux), `networksetup` (macOS), or the Windows registry — requires elevated privileges and prompts for confirmation
- The plugin system loads `.py` files from `~/.natbench/plugins/` — treat this directory with appropriate filesystem permissions
