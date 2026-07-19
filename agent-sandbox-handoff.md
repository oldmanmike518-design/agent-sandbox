# Agent Sandbox — Session Handoff

> Authoritative current state and execution order. Read this first. Historical detail is append-only in `agent-sandbox-log.md`.

- **Last updated:** 2026-07-19 — Session 19 (verification core built and locally verified)
- **Canonical workspace:** `/Users/michaellanger/Projects/agent-sandbox`
- **GitHub:** https://github.com/oldmanmike518-design/agent-sandbox
- **Production:** https://agent-sandbox-xvx2.onrender.com
- **Production code:** `main` baseline `1be6d96` (PRs #10–#15 merged)
- **Repository state:** checkout is on local branch `agent/verification-core`; implementation through Task 12 is committed at `64eb48f`, with this Task 13 closeout commit at the branch tip. `main` remains at `8faf95c`.
- **GitHub metadata:** interoperability description, production homepage, and discovery topics are live
- **Public usage:** two clearly-labeled project-operated smoke agents and one broadcast (2026-07-19 end-to-end check); no outside builders yet

## Session 19 Verification-Core Handoff (READ FIRST)

Revision 4 of `docs/plans/2026-07-19-verification-core.md` is fully implemented locally. Claude completed Tasks 0–2 before its usage limit; Codex verified the inherited migration correction and completed Tasks 3–13. **Nothing was pushed, no PR was opened, no production bootstrap ran, and no deploy occurred. The Render production service remains on the pre-verification code.**

### Built and committed

- Reserved, visibly labeled `InteropConformanceAgent` identity and safe idempotent bootstrap.
- Durable verification runs, observations, transactional outbox, immutable reports, and separate mutable publication state.
- Authenticated `/verify` lifecycle; deterministic eight-check `rest-interop` evaluator; strict cursor-chain, overlap replay, edge recovery, duplicate suppression, cadence, and verifier-fault rules.
- Public HTML/JSON reports, JSON/SVG badges, opt-in report index, owner listing controls, and admin delist/disable/dead-letter endpoints.
- Revocation/deactivation aborts an open run transactionally; token rotation preserves it.
- Window-scoped, idempotent verifier-fault budget refunds using a dedicated limiter transaction.
- Draft normative specification at `docs/INTEROP_SPEC.md` (`0.1-draft`, never “certified”).
- Observation retention purge and privacy disclosure.
- Endpoint-driven PostgreSQL integration matrix covering the compliant flow, deficient clients, foreign traffic, lifecycle, concurrency, refunds, outbox recovery, takedown, sanitized output, statistics exclusion, bootstrap conflicts, and purge.

### Local verification completed

- Unit suite: **114 passed**.
- New verification integration module: **23 passed**.
- Complete integration directory: **36 passed**.
- Ruff: **all checks passed**.
- Alembic migration imports and upgrades successfully to `0004_verification_core`.
- Checked-in OpenAPI snapshot regenerated.

Disposable local PostgreSQL and Redis were started only for integration tests. No production data or credentials were used.

### Deliberate deviations and corrections

1. Corrected the Task 2 migration so `verification_reports.slug` has one named unique index matching the ORM.
2. Added `SQLAlchemy[asyncio]` to requirements because the integration run proved the async engine’s required `greenlet` extra was undeclared.
3. The integration module uses one persistent event loop because the application’s pooled async engine cannot safely cross separate `asyncio.run()` loops.
4. Updated the pre-existing migration integration assertion from revision 0003 to 0004 and included all five verification tables.
5. The normative max-length fixture is defined algebraically in the spec instead of printing 1,984 repeated `x` characters.
6. The plan’s admin snippets repeated the router’s `/admin` prefix; implementation correctly declares routes relative to the existing prefixed router.

### Still requires maintainer authorization

1. Review the local branch and commits.
2. Push `agent/verification-core` and open a PR.
3. Let GitHub CI run and review the PR.
4. Merge only after approval.
5. Run migration 0004 and `scripts/bootstrap_conformance_agent.py` in production.
6. Deploy and perform a production register → verify → report smoke test.

No step above has been performed yet.

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

1. Review the local `agent/verification-core` branch, its commit series, and the Session 19 log entry.
2. With maintainer approval, push the branch and open a PR; wait for and review all CI checks.
3. After separate merge/deploy authorization, migrate production, run the idempotent conformance-agent bootstrap, deploy, and execute the production verification smoke flow.
4. Then recruit 3–5 AutoGen, CrewAI, or LangGraph builders and collect real reports and integration friction.
5. In parallel, schedule retention, publish the dedicated contact, and record backup/alert ownership.
6. Build the remote MCP interface and framework recipes after the verification core is proven with outside clients.
7. Keep broad Reddit/Show HN promotion gated on the five checklist boxes above.

## Durable Decisions

- Positioning: **a public interoperability and integration-test sandbox where builders test agents against agents they did not build.**
- Vision (adopted 2026-07-19, Codex + Claude concurring): **Agent Sandbox is the place builders send their agents to prove interoperability against systems they did not build — while remaining directly usable by the agents themselves.** The first audience is builders bringing agents, not a swarm of roaming agents; "agents independently encountering the sandbox" is the eventual flywheel, not the entry strategy.
- Distribution roads, in leverage order: seed builders → always-on conformance partner → remote MCP server + official registry → framework recipes → searchable content/reports → honest A2A when warranted.
- Internal credits are non-monetary, non-convertible, non-purchasable, and non-redeemable.
- Public wallet receiving addresses and required memos stay visible by design; private keys, seed phrases, credentials, and production secrets never enter the repository.
- Sponsored quests are the strongest first monetization experiment after real usage exists.
- Voluntary crypto tips support the maintainer but are not the core business model.
- Do not astroturf, fabricate agent activity, ask for coordinated engagement, or weaken abuse controls to inflate statistics.
- The Render free instance can cold-start after inactivity; mention that honestly during alpha.
