# Deployment Handoff — Verification Core Is Live

_Updated 2026-07-19 after PR #18, production migration/bootstrap, and the 8/8 verification smoke run._

## Current production

- URL: https://agent-sandbox-xvx2.onrender.com
- Render service: `srv-d7a57o15pdvs73c0g3cg`
- Live application commit: `e98559dc1b06c5e530df0057e815db15f9160ee8`
- Current deploy: `dep-d9eh1tj7uimc73fjmfdg`
- Health check: `/readyz`
- Instance: Render Free (cold starts after inactivity are expected)

The service is connected to `oldmanmike518-design/agent-sandbox` on `main`. PR #18's verification core is migrated, bootstrapped, and live.

Render Free cannot run shell commands or one-off jobs. The Docker start path therefore runs `alembic upgrade head`, then the idempotent conformance-agent bootstrap, then Uvicorn. A migration or stable-identity conflict fails the new deploy before it receives traffic.

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
- `GET /openapi.json` — `200`, 51 paths; root and `/v1` verification/report routes present.
- `GET /docs` — `200`.
- Invalid host — `403`.
- Security headers — CSP, frame denial, `nosniff`, Referrer-Policy, and Permissions-Policy present.
- `GET /agents?q=InteropConformanceAgent` — the house partner is present and visibly `system_operated=true`.
- Production smoke run `3a65d5dc-ad82-4dbb-8fa3-5643370a0cd6` — all eight checks passed through public endpoints.
- Report `https://agent-sandbox-xvx2.onrender.com/reports/eR1129MH5RLwvAdl` — complete 8/8, engine commit `e98559d`, no verifier fault, HTML/JSON/SVG available, unlisted by default.

The first live CORS check exposed a stale wildcard value. It was replaced with the exact production origin and the final Render configuration deploy completed successfully. Reconfirm the response header during the first outside-builder smoke test.

The PR #18 merge did not trigger a visible Render build even though Settings shows **Auto-Deploy: On Commit**. The current release was started with **Manual Deploy → Deploy latest commit**. Verify the dashboard after future merges until automatic deployment is observed independently.

## Remaining deployment operations

These are the only deployment-side follow-ups:

1. Schedule `PYTHONPATH=. python scripts/purge_old_events.py` daily with `ENV=production`, the production database URL, and `EVENT_LOG_RETENTION_DAYS=90`.
2. Replace `<CONTACT_EMAIL>` in `PRIVACY.md` and `ACCEPTABLE_USE.md` with a dedicated public data-controller address.
3. Capacity envelope: **completed** and recorded in `docs/LOAD_TESTING.md`.
4. Record the database backup/restore owner and the uptime/error/dependency-alert owner.
5. Keep `SECURITY_HSTS_SECONDS=0` while using the shared `*.onrender.com` domain.
6. Leave `TRUSTED_PROXY_CIDRS` empty unless the exact immediate Render proxy CIDR is confirmed from authoritative provider information.

## Launch status

- **Controlled seed:** open now for 3–5 real framework builders.
- **Broad launch:** wait until retention, contact, capacity, operational ownership, and three real outside integrations are recorded.
- **Promotion execution:** use `PROMOTION-COMMAND-CENTER.md`.
- **Never:** create fake agents or fabricated traffic to inflate public stats.
