# Agent Sandbox — Session Handoff

> Authoritative current state and execution order. Read this first. Historical detail is append-only in `agent-sandbox-log.md`.

- **Last updated:** 2026-07-19 — Session 20 (verification core released and proven in production)
- **Canonical workspace:** `/Users/michaellanger/Projects/agent-sandbox`
- **GitHub:** https://github.com/oldmanmike518-design/agent-sandbox
- **Production:** https://agent-sandbox-xvx2.onrender.com
- **Production application code:** `e98559d` (PR #18 merged and live; later Session 20 closeout commits are documentation-only)
- **Repository state:** PR #18 is merged; PR #19 is the documentation-only Session 20 release closeout
- **GitHub metadata:** interoperability description, production homepage, and discovery topics are live
- **Public usage:** three clearly labeled project-operated smoke agents, the visibly labeled system conformance partner, and one complete 8/8 verification report; no outside builders yet

## Session 20 Verification-Core Release Handoff (READ FIRST)

Revision 4 of `docs/plans/2026-07-19-verification-core.md` is fully implemented, merged in PR #18, migrated, bootstrapped, deployed, and proven through the public production contracts. Production is no longer on the pre-verification build.

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

### Release verification completed

- Unit suite: **114 passed**.
- New verification integration module: **23 passed**.
- Complete integration directory: **37 passed** after the release-review regression test.
- Ruff: **all checks passed**.
- Alembic migration imports and upgrades successfully to `0004_verification_core`.
- Checked-in OpenAPI snapshot regenerated.
- GitHub PR #18 CI: test, integration, and full-history secret scan all passed.

Disposable local PostgreSQL and Redis were started only for integration tests. No production data or credentials were used.

### Deliberate deviations and corrections

1. Corrected the Task 2 migration so `verification_reports.slug` has one named unique index matching the ORM.
2. Added `SQLAlchemy[asyncio]` to requirements because the integration run proved the async engine’s required `greenlet` extra was undeclared.
3. The integration module uses one persistent event loop because the application’s pooled async engine cannot safely cross separate `asyncio.run()` loops.
4. Updated the pre-existing migration integration assertion from revision 0003 to 0004 and included all five verification tables.
5. The normative max-length fixture is defined algebraically in the spec instead of printing 1,984 repeated `x` characters.
6. The plan’s admin snippets repeated the router’s `/admin` prefix; implementation correctly declares routes relative to the existing prefixed router.
7. Release review moved conformance identity validation into the insert transaction, so a mixed-case reserved-name conflict rolls back without leaving a partial system row.
8. Render Free has no shell or one-off jobs, so `scripts/start.sh` now runs the idempotent bootstrap after Alembic and before Uvicorn. A migration or identity conflict fails the new deploy while the previous release remains live.

### Production proof

- PR #18 merged to `main` as `e98559dc1b06c5e530df0057e815db15f9160ee8`.
- Render deploy `dep-d9eh1tj7uimc73fjmfdg` completed successfully.
- Startup logs confirmed migration `0003_agent_credential_version → 0004_verification_core`, `Bootstrap ensured: InteropConformanceAgent`, application startup, and Render health acceptance.
- `/readyz` returns `200` with database available and schema current.
- Live OpenAPI now exposes 51 paths, including root and `/v1` aliases for `/verify` and `/reports`.
- Clearly labeled `CodexInteropSmoke_mrs3v0q2` completed the real register → verify → discover → direct-send → forward-poll → instructed-replay → fresh-nonce → finalize flow.
- Run `3a65d5dc-ad82-4dbb-8fa3-5643370a0cd6` passed all eight checks with no verifier fault.
- Public report: `https://agent-sandbox-xvx2.onrender.com/reports/eR1129MH5RLwvAdl` (complete 8/8, `0.1-draft`, unlisted by default).
- The report JSON records engine commit `e98559d`; HTML, JSON badge, and SVG badge all serve successfully.

Render did not start a build automatically after the merge even though the service setting reads **Auto-Deploy: On Commit**. Codex triggered the latest-commit deploy manually. Treat automatic deployment as unproven and verify the dashboard after future merges.

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
- Verification-core release deploy: `dep-d9eh1tj7uimc73fjmfdg`
- Application code commit: `e98559dc1b06c5e530df0057e815db15f9160ee8`
- Render status at closeout: **Live**

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
- The manifest advertises the production base URL and live OpenAPI now has 51 paths, including root and `/v1` verification/report routes.
- The system-operated conformance partner is visibly labeled in `/agents`.
- The Session 20 production verification run produced a complete 8/8 report and green badge while remaining absent from the public index by default.

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
- [x] Durable verification core, conformance partner, public reports, and badges deployed and proven 8/8 in production.

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

1. Recruit 3–5 AutoGen, CrewAI, LangGraph, OpenAI Agents SDK, generic-MCP, or plain-HTTP builders and have each produce a real verification report.
2. Capture framework, completion time, failed/not-observed checks, integration friction, and whether the builder publishes or returns to the report.
3. Fix only friction proven by outside clients; keep the specification at `0.1-draft` until those thresholds are validated.
4. In parallel, schedule daily retention, publish the dedicated contact, and record backup/alert ownership.
5. Then build the remote MCP interface and verified five-minute framework recipes using the production verification flow.
6. Verify the Render dashboard after every merge until automatic deployment is independently observed working.
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
