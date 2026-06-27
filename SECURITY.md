# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |

## Reporting a vulnerability

If you discover a security issue, please **do not** open a public GitHub issue.

Email the maintainer privately with:

- A description of the issue
- Steps to reproduce
- Impact assessment (if known)

We will acknowledge receipt and work on a fix as soon as possible.

## Secrets and sensitive data

This project must never commit:

- `.env` or API keys
- Real bank statements or user uploads (`media/`)
- Production database credentials

Use `.env.example` as a template for local development only.
