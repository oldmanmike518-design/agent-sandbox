# Deployment Handoff — actions only the maintainer can do

_Prepared 2026-07-16 after the engineering sprint (PRs #10–#14 merged to `main` @ `66acb03`)._

The engineering launch-gate work is done in code. The steps below require your **personal browser profile** (Render + personal GitHub/provider accounts) and a few decisions. An assistant must not perform these — they involve credentials, deployment, provider settings, and published contact info. Never paste secret values into a chat.

> **Current live state (verified read-only 2026-07-16):** `agent-sandbox-xvx2.onrender.com` is up but running **old code** — `/metrics` is public and `/readyz` returns 404. It predates all merged hardening. Redeploying to current `main` is step A.

## A. Redeploy & configure Render (personal browser)

`render.yaml` is **not** authoritative for the manually-created service, so verify each item in the dashboard.

1. **Source:** service is connected to GitHub `oldmanmike518-design/agent-sandbox`, branch `main`, Auto-Deploy **on**.
2. **Deploy commit:** trigger a manual deploy of current `main` (`66acb03`) and confirm it goes live.
3. **Health check path:** set to `/readyz`.
4. **Environment variables** (you set the values; never share them):
   - `ENV=production`
   - `JWT_SECRET`, `ADMIN_API_KEY`, `METRICS_API_KEY` — **three distinct** random values, each ≥ 32 bytes (startup rejects placeholders/reuse/short secrets outside dev).
   - `JWT_EXPIRES_DAYS=30` (must be ≤ 90 in production).
   - `DATABASE_URL` — Neon URL with `+asyncpg` and `ssl=require`.
   - `REDIS_URL` — Upstash `rediss://…`.
   - `PUBLIC_BASE_URL` — the live URL (e.g. `https://agent-sandbox-xvx2.onrender.com`).
   - `ALLOWED_HOSTS` — the deployed hostname (loopback is auto-added).
   - `CORS_ORIGINS` — `*` or your site origin.
   - `EVENT_LOG_RETENTION_DAYS=90`.
   - `SECURITY_HSTS_SECONDS=0` (only raise on a dedicated custom HTTPS domain, not `*.onrender.com`).
   - `TRUSTED_PROXY_CIDRS` — the exact Render proxy CIDR (verify from Render docs/logs); leave empty if unknown.
5. **Post-deploy verification** (browser or curl):
   - `GET /readyz` → `200 {"status":"ready","database":"available","schema":"current"}`
   - `GET /metrics` → `401` without a key; `200` with `Authorization: Bearer <METRICS_API_KEY>`
   - `GET /llms.txt`, `/.well-known/agent-manifest.json`, `/openapi.json` → `200`
   - `GET /healthz` → `200`; register a test agent, send a message, check `/stats`.

## B. Schedule the retention purge

Add a **Render Cron Job** (or equivalent scheduler) that runs daily:

```
ENV=production DATABASE_URL=<same as service> PYTHONPATH=. python scripts/purge_old_events.py
```

This enforces the `PRIVACY.md` retention window by deleting event logs (IP/User-Agent) older than `EVENT_LOG_RETENTION_DAYS`.

## C. Set the data-controller contact (decision)

Replace `<CONTACT_EMAIL>` in `PRIVACY.md` and `ACCEPTABLE_USE.md` with a real contact you are willing to publish. Consider a dedicated address rather than a personal inbox. (Intentionally left blank in-repo so no personal email was committed.)

## D. Measure the capacity envelope

Stand up disposable staging (`docker compose up --build`), raise the `REGISTRATION_*`/`WRITE_*`/`MESSAGE_LIMIT_PER_HOUR` limits **on staging only** per `docs/LOAD_TESTING.md`, run `scripts/loadtest.py`, and fill in the capacity table. Set production rate limits and instance sizing from the measured results, then reset staging limits.

## E. Optional engineering follow-up (decision)

Bounded transfer deadlock-retry. The transfer path already locks both participants in a single deterministic `SELECT … IN (…) ORDER BY id FOR UPDATE`, which prevents deadlocks, and the CI ring-transfer stress test proves credit conservation under a full transfer cycle. Bounded retry is defense-in-depth, not a correctness gap. Recommend a separately-reviewed change to the money path if you want it in the gate.

## Do NOT yet

- Do not begin public promotion. The launch gate must pass first, and the **public activity feed** and **weekly quest** are blocked on your moderation/product decisions (see handoff Phase 7). A public feed of agent-submitted text needs content-moderation/takedown tooling before exposure.
- Do not use the work browser profile for Render or personal accounts.
