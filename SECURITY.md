# Security policy

## Supported versions

Security fixes are expected to target the latest released version.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose private archive content, bypass authentication, escape the configured media directory, or leak credentials.

Report the issue privately to the repository maintainer using GitHub's private vulnerability reporting feature when enabled.

Include:

- affected version
- reproduction steps
- expected behavior
- actual behavior
- impact

Do not attach real Telegram exports or private messages.

## Deployment guidance

Telegram archives are sensitive data. For internet-facing deployments:

- use HTTPS
- use a strong archive password
- use a long random `SESSION_SECRET`
- set `COOKIE_HTTPS_ONLY=true`
- do not expose `telegram_export/` directly through the reverse proxy
- mount the Telegram export read-only
- keep `.env`, `data/`, and `telegram_export/` out of Git
- keep the host and Docker engine updated

The application login is intentionally simple and is not a replacement for enterprise SSO, MFA, VPN access controls, or a zero-trust gateway when those are appropriate.
