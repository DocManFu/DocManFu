# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in DocManFu, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

Email: **security@docmanfu.com**

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Acknowledgment** within 48 hours
- **Status update** within 7 days
- **Fix timeline** depends on severity — critical issues are prioritized

### Scope

This policy covers:

- The DocManFu application (backend API, frontend, worker)
- Docker configuration and deployment scripts
- Authentication and authorization logic
- File upload and storage handling

Out of scope:

- Third-party dependencies (report upstream)
- Issues in development/test environments that don't affect production
- Social engineering attacks

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Older releases | Best effort |

## Security Best Practices for Operators

- Always set strong values for `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`
- Use a reverse proxy (Caddy/nginx) with HTTPS in production
- Keep Docker images updated (`./prod rebuild`)
- Restrict network access to database and Redis ports
- Review `.env` files — never commit secrets to version control
- Use Ollama or self-hosted AI to keep document content private
