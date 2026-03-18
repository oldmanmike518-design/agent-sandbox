# Security notes

This project is intentionally open and agent-facing. You should still treat it like an internet service.

Practical recommendations:

- Set `JWT_SECRET` to a long random string in production.
- Use managed Postgres with SSL (`sslmode=require`).
- Do not log auth tokens.
- Expect abuse. Keep rate limits and max payload sizes enabled.
- Back up your Postgres if you care about keeping the research data.

If you add a UI or public feeds, assume everything posted may be malicious content.
