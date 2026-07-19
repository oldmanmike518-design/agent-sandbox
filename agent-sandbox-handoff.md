# Agent Sandbox — Session Handoff

> Authoritative current state and execution order. Read this first. Historical detail is append-only in `agent-sandbox-log.md`.

- **Last updated:** 2026-07-19 — Session 17 closeout (production smoke pass, capacity envelope, workspace consolidation, and PR #17)
- **Canonical workspace:** `/Users/michaellanger/Projects/agent-sandbox`
- **GitHub:** https://github.com/oldmanmike518-design/agent-sandbox
- **Production:** https://agent-sandbox-xvx2.onrender.com
- **Production code:** `main` baseline `1be6d96` (PRs #10–#15 merged)
- **Repository state:** `main` is at Session 16 commit `78e1a3d`; Session 17 documentation is committed as `8dbec31` on `agent/session-17-capacity-handoff` in draft PR #17
- **GitHub metadata:** interoperability description, production homepage, and discovery topics are live
- **Public usage:** two clearly-labeled project-operated smoke agents and one broadcast (2026-07-19 end-to-end check); no outside builders yet

## Executive State

The engineering and production-deployment sprint is complete. Claude merged operational readiness, web hardening, agent-discovery assets, privacy/retention, and load-test tooling in PRs #10–#14. PR #15 reconciled the sprint documentation. Codex then configured the manually created Render service from the user's authenticated personal browser and deployed current `main`.

The service is now a live, clearly experimental public alpha with:

- production fail-closed secret validation and three distinct production authentication secrets;
- a 30-day JWT lifetime, revocable credential versions, and separate admin/metrics credentials;
- PostgreSQL-backed registration and global write-abuse controls;
- dependency- and migration-aware `/readyz`;
- authenticated `/metrics`;
- trusted-host enforcement, security headers, request-size limits, and restricted production CORS;
- public `/llms.txt`, agent manifest, OpenAPI, Python/Node quickstarts, and a small Python SDK;
- privacy, acceptable-use, non-monetary-credit, and 90-day event-retention policy;
- unit, integration, concurrency, dependency-audit, lint, and full-history secret-scan CI;
- a repeatable staging load-test harness.

**Launch posture:** the controlled seed launch is open now. Invite 3–5 real framework builders and connect genuine agents. Do not manufacture fake traffic. The one-time broad Show HN/Reddit launch remains gated on real seed activity and the short operational checklist below.

## Workspace and Tool Handoff

This repository is tool-neutral: Codex, Claude, Gemini, or another coding agent may continue the work, but every tool must use only:

`/Users/michaellanger/Projects/agent-sandbox`

Start by checking out current `main`, pulling from `origin`, reading this file, and reading only the latest entry in `agent-sandbox-log.md`. Follow `AGENTS.md`. Do not copy work between checkouts.

Two redundant checkouts were verified as non-canonical, contained no work that needed combining, and were manually moved to Trash by the maintainer on 2026-07-19:

- `/Users/michaellanger/Documents/Codex/2026-07-16/oldmanmike518-design-agent-sandbox-https-github` — clean Session 16 duplicate.
- `/Users/michaellanger/Documents/bug-bounties/agent-sandbox` — obsolete May checkout.

Their removal was verified after the manual cleanup. The GitHub repository and the canonical `Projects` checkout are now the only sources of truth.

## Production Deployment Record

- Render service ID: `srv-d7a57o15pdvs73c0g3cg`
- Final configuration deploy: `dep-d9cjsvt7vvec73einrrg`
- Deployed commit: `1be6d96eb69114aea9256c625d0703e696915eb6`
- Render status at closeout: **Live** (48.9-second final configuration deploy)

Configured in Render without recording secret values:

- `ENV=production`
- distinct strong `JWT_SECRET`, `ADMIN_API_KEY`, and `METRICS_API_KEY`
- `JWT_EXPIRES_DAYS=30`
- `PUBLIC_BASE_URL=https://agent-sandbox-xvx2.onrender.com`
- `ALLOWED_HOSTS=agent-sandbox-xvx2.onrender.com`
- `CORS_ORIGINS=https://agent-sandbox-xvx2.onrender.com`
- health-check path `/readyz`
- existing database, owner-message, and intentional public wallet configuration preserved

Defaults remain active for event retention (90 days), HSTS (off on the Render subdomain), trusted-proxy CIDRs (empty until an exact provider CIDR is confirmed), and Redis (database-authoritative fallback when no Redis URL is configured).

### Live verification completed

- On 2026-07-19 after the Session 17 documentation push, an independent check returned `/readyz` `200` with database available and schema current and `/healthz` `200`; the warm readiness response completed in about 0.29 seconds.
- `/` opened as the Agent Sandbox homepage.
- `/readyz` returned `200` with the database available and schema current.
- `/healthz` returned `200`.
- `/metrics` returned `401` without its bearer key.
- `/llms.txt`, `/.well-known/agent-manifest.json`, and `/openapi.json` returned `200`.
- `/docs` returned `200`.
- An invalid `Host` header returned `403`.
- CSP, Permissions-Policy, Referrer-Policy, `nosniff`, and frame-denial headers were present.
- The manifest advertises the production base URL and the checked-in OpenAPI has 27 paths including forward inbox polling.
- `/stats` showed zero usage.

The first CORS probe exposed a stale wildcard Render value. Codex corrected the environment row to the single production origin and Render completed the final configuration deploy successfully. A new independent header probe from outside the managed browser sandbox is a useful smoke check during the first seed integration, but no further configuration change is expected.

## Completed Work

### Recovery and review

- [x] Recovered the canonical project, brief, handoff, running log, and marketing plan.
- [x] Preserved the independent Codex and Claude audits.
- [x] Scanned the working tree and full history; no private keys, provider credentials, database URLs, or production secrets were committed.
- [x] Recorded that public cryptocurrency receiving addresses and required destination memos are intentionally public.

### Engineering and security

- [x] JWT fail-closed production guardrail and safe development-only Compose secret.
- [x] Redis failure timeouts/reset/fallback.
- [x] Atomic registration and global authenticated-write budgets.
- [x] Duplicate-registration `409`, deterministic transfer locking, and double-spend regression coverage.
- [x] JWT rotation, revocation, deactivation, and disposable-alpha identity policy.
- [x] Database/migration readiness and gated metrics.
- [x] Security headers, trusted hosts, body-size cap, and configurable CORS/HSTS/proxy handling.
- [x] Aware UTC model timestamps and forward inbox polling.
- [x] Privacy/acceptable-use/retention notices and purge implementation.
- [x] CI with Ruff, pytest, PostgreSQL 16, Redis 7, Alembic, pip-audit, and Gitleaks.

### Discovery and distribution

- [x] Public quickstarts, SDK, `llms.txt`, agent manifest, and checked-in OpenAPI.
- [x] Load-test driver and capacity methodology.
- [x] GitHub description, homepage, and discovery topics.
- [x] Ready-to-paste seed and launch copy in `PROMOTION-COMMAND-CENTER.md`.
- [x] Current hardened `main` deployed to Render.

## Remaining Operational Checklist

These are real follow-ups, not reasons to restart the engineering audit:

1. **Schedule retention enforcement.** Run `PYTHONPATH=. python scripts/purge_old_events.py` daily with production database access.
2. **Publish a data-controller contact.** Replace `<CONTACT_EMAIL>` in `PRIVACY.md` and `ACCEPTABLE_USE.md` with a dedicated public address.
3. **Measure a staging capacity envelope.** **Done 2026-07-19** — measured against disposable local Docker staging and recorded in `docs/LOAD_TESTING.md` (read 538 req/s, write 269 req/s, mixed 384 req/s at concurrency 50; saturation knee between 50 and 100; zero errors at every level; current production rate limits remain the binding constraint by two orders of magnitude).
4. **Assign operational owners.** Record who owns database backups/restore drills and uptime/error/dependency alerts.
5. **Verify with real seed traffic.** Have at least three outside builders complete registration and one cross-agent interaction; capture framework, latency, failures, and return behavior.

Optional, separately reviewed engineering work:

- bounded database retry for rare transfer serialization/deadlock failures;
- edge-level request/header throttling;
- image/base-digest supply-chain pinning;
- richer moderation/content-removal tooling before any unauthenticated public activity feed;
- a weekly quest, directory, and moderated feed.

## Launch Gates

### Controlled seed launch — OPEN

- [x] Current hardened code is live.
- [x] Strong distinct production credentials are configured.
- [x] Readiness and schema state are healthy.
- [x] Metrics are private.
- [x] Application abuse controls and non-economic credit policy are active.
- [x] Tests, concurrency checks, dependency audit, and secret scan are green on merged PRs.
- [x] Machine discovery, quickstarts, privacy, and acceptable-use documents are public.

### Broad public launch — HOLD until all are checked

- [ ] Retention purge is scheduled.
- [ ] Public data-controller contact is set.
- [x] Conservative staging load envelope is recorded (2026-07-19, `docs/LOAD_TESTING.md`).
- [ ] Backup/restore and alert ownership are recorded.
- [ ] At least three real outside builders have produced non-house activity.

## Next Session — Start Here

1. Work only in `/Users/michaellanger/Projects/agent-sandbox`; pull current `main`, then read this handoff and the latest log entry.
2. Review and merge draft PR #17 (documentation only; CI test, integration, and secret-scan jobs passed on 2026-07-19).
3. Open `PROMOTION-COMMAND-CENTER.md`.
4. Recruit 3–5 AutoGen, CrewAI, or LangGraph builders for the controlled seed; use transparent project-operated agents only for support/status, never fake users.
5. Have outside builders repeat the proven register → discover → message → forward-poll inbox → stats flow and capture framework, setup friction, latency, failures, cross-agent interaction, and return behavior.
6. In parallel, schedule retention, publish the dedicated contact, and record backup/alert ownership (the staging load test is done).
7. Once all five broad-launch boxes are checked, execute the channel order in the command center: AutoGen → CrewAI → LangGraph → Reddit → Show HN.
8. Measure real integrations, repeat use, cross-agent messages, server errors, and genuine voluntary tips—not vanity page views.

## Durable Decisions

- Positioning: **a public interoperability and integration-test sandbox where builders test agents against agents they did not build.**
- Internal credits are non-monetary, non-convertible, non-purchasable, and non-redeemable.
- Public wallet receiving addresses and required memos stay visible by design; private keys, seed phrases, credentials, and production secrets never enter the repository.
- Sponsored quests are the strongest first monetization experiment after real usage exists.
- Voluntary crypto tips support the maintainer but are not the core business model.
- Do not astroturf, fabricate agent activity, ask for coordinated engagement, or weaken abuse controls to inflate statistics.
- The Render free instance can cold-start after inactivity; mention that honestly during alpha.
