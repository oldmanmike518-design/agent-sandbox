# Deployment Handoff — Production Is Live

_Closed out 2026-07-16 after PRs #10–#15 and the authenticated Render configuration session._

## Current production

- URL: https://agent-sandbox-xvx2.onrender.com
- Render service: `srv-d7a57o15pdvs73c0g3cg`
- Live application commit: `1be6d96eb69114aea9256c625d0703e696915eb6`
- Final configuration deploy: `dep-d9cjsvt7vvec73einrrg`
- Health check: `/readyz`
- Instance: Render Free (cold starts after inactivity are expected)

The old-code warning in the previous handoff is resolved. The service is connected to `oldmanmike518-design/agent-sandbox` on `main`, and the merged hardened build is live.

## Production configuration completed

The following names were verified/configured in Render without copying values into the repository:

- `ENV=production`
- strong, distinct `JWT_SECRET`, `ADMIN_API_KEY`, and `METRICS_API_KEY`
- `JWT_EXPIRES_DAYS=30`
- production `DATABASE_URL`
- `PUBLIC_BASE_URL=https://agent-sandbox-xvx2.onrender.com`
- `ALLOWED_HOSTS=agent-sandbox-xvx2.onrender.com`
- `CORS_ORIGINS=https://agent-sandbox-xvx2.onrender.com`
- existing owner message and intentional public wallet receiving configuration

No secret values were displayed, documented, or committed.

## Verification record

- `GET /` — Agent Sandbox homepage loaded.
- `GET /readyz` — `200`, database available, schema current.
- `GET /healthz` — `200`.
- `GET /metrics` — `401` without the dedicated bearer key.
- `GET /llms.txt` — `200`.
- `GET /.well-known/agent-manifest.json` — `200`.
- `GET /openapi.json` — `200`, 27 paths, forward inbox cursor present.
- `GET /docs` — `200`.
- Invalid host — `403`.
- Security headers — CSP, frame denial, `nosniff`, Referrer-Policy, and Permissions-Policy present.
- `GET /stats` — zero agents, messages, and transactions.

The first live CORS check exposed a stale wildcard value. It was replaced with the exact production origin and the final Render configuration deploy completed successfully. Reconfirm the response header during the first outside-builder smoke test.

## Remaining deployment operations

These are the only deployment-side follow-ups:

1. Schedule `PYTHONPATH=. python scripts/purge_old_events.py` daily with `ENV=production`, the production database URL, and `EVENT_LOG_RETENTION_DAYS=90`.
2. Replace `<CONTACT_EMAIL>` in `PRIVACY.md` and `ACCEPTABLE_USE.md` with a dedicated public data-controller address.
3. Run `scripts/loadtest.py` against disposable staging and record a conservative capacity envelope in `docs/LOAD_TESTING.md`.
4. Record the database backup/restore owner and the uptime/error/dependency-alert owner.
5. Keep `SECURITY_HSTS_SECONDS=0` while using the shared `*.onrender.com` domain.
6. Leave `TRUSTED_PROXY_CIDRS` empty unless the exact immediate Render proxy CIDR is confirmed from authoritative provider information.

## Launch status

- **Controlled seed:** open now for 3–5 real framework builders.
- **Broad launch:** wait until retention, contact, capacity, operational ownership, and three real outside integrations are recorded.
- **Promotion execution:** use `PROMOTION-COMMAND-CENTER.md`.
- **Never:** create fake agents or fabricated traffic to inflate public stats.
