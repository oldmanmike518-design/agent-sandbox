# Agent Sandbox — Session Handoff

> Canonical current-state document. Update this file at the end of every work session. Append durable history to `agent-sandbox-log.md`.

**Last updated:** 2026-07-16
**Canonical workspace:** `/Users/michaellanger/Projects/agent-sandbox`
**GitHub:** https://github.com/oldmanmike518-design/agent-sandbox
**Current branch:** `main` (local hardening commits are intentionally ahead of `origin/main`; run `git log -1` for the current commit)
**Recorded deployment:** https://agent-sandbox-xvx2.onrender.com
**Deployment status:** **Live and independently verified on 2026-07-16.** It cold-started (initial `503` with `Retry-After: 5`) and then became healthy. `/stats` still showed zero agents, messages, and transactions. `/docs`, `/openapi.json`, and `/metrics` were all publicly reachable without authentication.

---

## Current State

Agent Sandbox is a compact FastAPI service where autonomous agents can register, authenticate, send direct or broadcast messages, transfer internal credits, and generate an auditable event trail.

The code is suitable for local experiments and friendly private testing. It is **not yet approved for promoted public traffic**. Two independent reviews (Codex, 2026-07-16; Claude, 2026-07-16) agree on the launch blockers: unlimited identity creation, production-secret validation, dependency-failure handling, concurrency, health/readiness, tests, moderation, privacy, and operational readiness. Both audits are recorded in `agent-sandbox-log.md`; this handoff is the authoritative execution order.

Historical deployment configuration (treat as historical until each item is re-verified without copying credentials into the repo): Render free-tier Docker service, Neon PostgreSQL in Frankfurt, no Redis (database rate-limit fallback), wallet tip endpoint configured.

### Review reconciliation notes (2026-07-16 Claude review)

- **Transfers are protected from double-spending.** The sender row is `SELECT … FOR UPDATE`-locked before the balance check and decrement inside one transaction, so concurrent same-sender debits serialize and re-read a fresh balance. No double-spend, no negative balance. The residual risk is that **opposing A→B and B→A transfers can deadlock and return HTTP 500** (no deadlock retry). This is a reliability defect, not a money-loss bug.
- **New — Compose ships the forgeable JWT secret.** `docker-compose.yml` sets no `JWT_SECRET`, so the README's headline `docker compose up` runs on the public default `change-me`; with HS256 anyone can forge a token for any agent. The live Render host is likely protected via `render.yaml` `generateValue: true` (not verified by forging). High severity for the shipped code / Compose path.
- **New — naive UTC datetime.** Model timestamp defaults use naive `datetime.utcnow` written into `timestamptz` columns while the app compares against aware `datetime.now(timezone.utc)`; latent offset in time-window comparisons. Low severity.
- **Lower-severity framing (kept):** CORS `*` is Low (the wildcard branch sets `allow_credentials=False` and auth is a header Bearer token, not a cookie). Integer overflow is Low (PostgreSQL raises, does not silently wrap). PyJWT 2.10.1 is Low (the known issuer-bypass CVE is already fixed; verification pins HS256 and required claims).

## Canonical Workspace Rules

1. Work only from `/Users/michaellanger/Projects/agent-sandbox`.
2. Treat other copies as stale reference copies; do not edit them.
3. Read this handoff and `agent-sandbox-log.md` before making changes.
4. Append completed work and important decisions to the running log.
5. Update this handoff at session end with exact current state and next actions.
6. Never commit `.env`, database URLs, JWT secrets, API tokens, private keys, seed phrases, or provider credentials.
7. Public cryptocurrency **receiving addresses and required destination memos are intentional and are NOT secrets** — they exist so people and agents can send tips. Do not flag them as leaked. Only private keys, seed phrases, exchange/API credentials, JWT secrets, and database credentials are sensitive.
8. Do not push, deploy, or modify external services without explicit user authorization.

## Immediate Objective

Ship the Phase 0.5 immediate safety fixes, then build a testable baseline (Phase 1), before any behavior-changing hardening. Do not promote until the launch gate passes.

## Ordered Work Plan

### Phase 0 — Consolidation and safety record

- [x] Recover the historical brief, handoff, running log, and marketing plan.
- [x] Select `~/Projects/agent-sandbox` as the canonical workspace.
- [x] Fast-forward the canonical checkout to current GitHub `main` (`0b58810`).
- [x] Scan filenames, working files, and history for common secret patterns (clean).
- [x] Record the Codex audit and the independent Claude review in `agent-sandbox-log.md`.
- [x] **Wallet-address policy resolved:** public receiving addresses and memos stay visible in `.env.example` and API responses because tips are intentional; they are not secrets.
- [ ] Run a dedicated history-aware secret scanner once one is installed (`gitleaks` or equivalent).

### Phase 0.5 — Immediate safety fixes (do now, before the test harness)

Small, high-leverage changes that close the worst exposure without altering core behavior.

- [x] **JWT fail-closed guardrail (completed 2026-07-16).** Non-development startup rejects empty, known-placeholder, or shorter-than-32-byte `JWT_SECRET` values. Compose supplies an explicit development-only secret and `.env.example` clearly requires replacement.
- [x] **Redis failure handling (completed 2026-07-16).** Redis uses short connect/read timeouts; connection/command failures discard the cached client and deliberately use the database fallback instead of returning 500. Focused regression coverage is included.

### Phase 1 — Establish a testable baseline

- [ ] Expand pytest unit and integration coverage for registration, JWT authentication, messaging, pagination, transfers, rate limiting, health/readiness, and validation failures. **Partial:** seven focused tests now cover production JWT-secret rejection/acceptance and Redis-down database fallback.
- [ ] Add concurrency tests: duplicate registration race (must return 409, not 500); concurrent same-sender debits must not oversend (double-spend regression guard); opposing transfers must not 500 after the deadlock-retry fix.
- [ ] Add GitHub Actions for tests, linting, dependency audit, and secret scanning.
- [ ] Add reproducible local test instructions that do not require production credentials.

Reason for doing this first: hardening changes need regression protection before behavior is altered.

### Phase 2 — Close public-launch security blockers

- [ ] Registration throttling at both edge and application levels.
- [ ] Global/IP limits so unlimited new identities cannot bypass per-agent limits.
- [ ] Anti-Sybil policy for starting credits (invite, proof-of-work, delayed credits, verified builders, or explicitly non-economic test credits) plus a non-economic-credit disclaimer.
- [ ] Shorten JWT lifetime and add a credential-version claim so tokens can be revoked without deleting the agent.
- [ ] Request-body and header-size limits at the deployment edge (and consider an app-layer cap).
- [ ] Define safe CORS origins and add trusted-host / security-header configuration.
- [ ] Gate `/metrics` (auth token or private network / IP allowlist); decide consciously whether `/docs` stays public.

### Phase 3 — Reliability and data-integrity hardening

- [ ] Lock transfer participants in deterministic UUID order and retry deadlocks safely; map failure to a stable API response (not 500).
- [ ] Catch case-insensitive duplicate-registration races and return `409`.
- [ ] Make database-fallback rate limiting concurrency-safe (atomic counter).
- [ ] Migrate balances/amounts to `BIGINT` and bound transaction amounts (low priority — PostgreSQL raises on overflow, no silent corruption).
- [ ] Fix naive `datetime.utcnow` defaults (use aware UTC or DB `now()`).
- [ ] Add database-backed readiness checks separate from process liveness; verify migration revision during readiness/deploy.
- [ ] Correct the autonomous-agent inbox cursor so messages are not reprocessed.

### Phase 4 — Operations, abuse response, and privacy

- [ ] Admin controls to deactivate agents, revoke credentials, block abuse, and remove malicious content.
- [ ] Publish acceptable-use, privacy, retention, and internal-credit disclaimers; document IP/user-agent logging and define retention/deletion (Frankfurt DB → GDPR in scope).
- [ ] Configure database backups and perform a restore drill.
- [ ] Add uptime, error-rate, latency, database-capacity, and dependency alerts.
- [ ] Make migrations safe for multi-replica deployment (release step, not per-startup).
- [ ] Define log redaction rules; confirm authorization headers/tokens are never logged.

### Phase 5 — Dependency and capacity verification

- [ ] Upgrade the dependency set (including PyJWT, as hygiene) and run a resolved-tree vulnerability scan.
- [ ] Digest-pin or verify container supply-chain inputs and add automated image scanning.
- [ ] Run end-to-end tests against disposable PostgreSQL and Redis.
- [ ] Load-test registration, messaging, inbox pagination, stats, and transfers; establish a conservative public-alpha traffic envelope from measured results.
- [ ] Verify Render/Neon service limits, cold starts, connection pooling, TLS, and current pricing/tier behavior.

### Phase 6 — Deployment verification

- [x] Confirm the recorded Render deployment exists and is reachable (done 2026-07-16: live, cold-starts, healthy after retries, zero usage, docs/openapi/metrics public).
- [ ] Verify Render environment-variable names without recording values.
- [ ] Verify `PUBLIC_BASE_URL`, database TLS, JWT secret strength, CORS, and wallet configuration.
- [ ] Confirm production schema revision and backup state.
- [ ] Run the complete smoke/integration suite against a staging deployment.
- [ ] Release as a clearly labeled public experimental alpha only after Phases 0.5–5 pass.

### Phase 7 — Product loop (post-hardening, before promotion)

Build a reason to return before driving traffic. Positioning: **a public interoperability and integration-test sandbox where builders test agents against agents they did not build.**

- [ ] **Weekly quest** paid in internal (non-monetary) credits with a public result — highest-value addition.
- [ ] **Moderated live activity/broadcast feed** so the sandbox is never an empty room.
- [ ] **Agent profiles and a browsable directory** (build on `GET /agents`).
- [ ] **Copy-paste Python and Node quickstarts** (register in under 60 seconds).
- [ ] **`llms.txt`, an agent manifest, and a checked-in OpenAPI schema** for machine discovery.
- [ ] **A small Python SDK** (`pip install`) to remove most integration friction.
- [ ] Update `site/config.js` only after the production URL is re-verified; add a cold-start/status note to developer docs.

### Phase 8 — Promotion (only after the launch gate passes)

- [ ] Privately seed 5–10 framework builders; do not launch with an empty feed.
- [ ] Soft-launch in agent-framework communities (AutoGen, CrewAI, LangGraph, AgentOps) and r/LocalLLaMA.
- [ ] Show HN backed by a live, non-empty feed and a dataset story; add GitHub Topics and a Hugging Face dataset card.
- [ ] First revenue experiment: **sponsored quests** (see monetization stance below).

## Launch Gate

Public promotion is blocked until all of the following are true:

- App fails to start in non-dev with a missing/default/weak `JWT_SECRET`, and Compose no longer runs on `change-me`.
- Registration and global abuse controls are active; an anti-Sybil credit policy is live (or credits are declared explicitly non-economic).
- Redis/database failure behavior is defined and tested.
- Transfer deadlock retry and duplicate-registration `409` are shipped; the double-spend regression test is green.
- Readiness reflects real dependency/migration state.
- `/metrics` is gated; a privacy/retention notice and deletion path exist.
- Automated tests and CI pass; dependency and secret scans pass.
- Moderation, privacy, backups, and alerts each have a named owner.
- A measured load test establishes a safe initial traffic envelope.

## Positioning and Monetization Stance

- **Positioning:** a free, public interoperability and integration-test sandbox ("test your agent against strangers' agents before you trust it in production"), with a secondary hook as an open, observable dataset of agent-to-agent interaction.
- **Strongest initial monetization candidate:** **sponsored quests** (a framework/tool funds a branded challenge with a prize pool).
- **Internal credits remain explicitly non-monetary and non-convertible** — a game/rate-limit token, never sold or redeemed.
- **Cryptocurrency tips are voluntary support for the maintainer, not the primary business model**; keep them low-key and never injected into agent responses.
- **The interaction dataset can become valuable only after privacy, consent, and retention are addressed.**

## Next Session — Start Here

Continue Phase 1: expand the focused test baseline into endpoint, authentication, integration, and concurrency coverage; then add GitHub Actions. Do not begin promotion work.

## Known Historical Notes

- Render free tier introduces ~30-second cold starts after inactivity (re-observed 2026-07-16).
- ReDoc previously rendered a white screen while Swagger worked.
- The historical handoff said `PUBLIC_BASE_URL` still needed correction.
- A May 2 marketing note listed deployment as unconfirmed; the April 7 live status was revalidated on 2026-07-16.
