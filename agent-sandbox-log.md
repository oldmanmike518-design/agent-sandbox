# Agent Sandbox — Running Build Log

> Append-only project history. Do not delete prior sessions. Current priorities belong in `agent-sandbox-handoff.md`.

---

## 2026-04-07 — Session 1: Audit, Build, and Launch

### Context

Agent Sandbox was discovered during a GitHub audit after sitting undeployed since March 18. The FastAPI backend already included agents, messaging, credits, rate limiting, Prometheus monitoring, and Docker Compose.

### Decisions

- Kept the repository public.
- Used the database rate-limit fallback because traffic was zero.
- Chose Neon PostgreSQL in Frankfurt and Render for hosting.
- Used an optional cryptocurrency tip jar returned during registration and from `/transaction/tip`.

### Work completed

- Expanded the tip jar to BTC, ETH, XRP, XLM, ADA, LINK, and USDC across nine network variants.
- Added memo support for XRP and XLM.
- Corrected the asyncpg SSL query parameter from `sslmode=require` to `ssl=require` for the deployed connection.
- Set the owner message to: “Built in Alexandria, Egypt. Open to AI Agents from anywhere in the universe.”

### Deployment record

- Recorded live URL: https://agent-sandbox-xvx2.onrender.com
- Swagger recorded at `/docs`.
- `/transaction/tip` and `/stats` were reported working.
- Reported state: zero agents, messages, and transactions.

### Items carried forward

- Correct `PUBLIC_BASE_URL` on Render.
- Point `site/config.js` to the live API.
- Document free-tier cold starts.
- Decide launch strategy.
- Consider SDKs, quests, and premium options.

---

## 2026-07-16 — Session 2: Recovery, Consolidation, and Traffic-Readiness Audit

### Recovery and workspace consolidation

- Found the historical project at `/Users/michaellanger/Projects/agent-sandbox` after a broad search of Claude, Documents, Projects, and Desktop locations.
- Recovered `agent-sandbox-brief.md`, `agent-sandbox-handoff.md`, `agent-sandbox-log.md`, and `MARKETING-PLAN.md`.
- Confirmed Claude memory designated `~/Projects` as the canonical project home.
- Found two additional code copies:
  - `/Users/michaellanger/Documents/bug-bounties/agent-sandbox`
  - A temporary Codex clone under `/Users/michaellanger/Documents/Codex/2026-07-16/.../repo`
- Chose `/Users/michaellanger/Projects/agent-sandbox` as the only canonical workspace.
- Fast-forwarded canonical `main` from `3d45a7d` to current GitHub `0b58810` without losing the recovered untracked documents.

### Checks completed

- Read the complete application, routes, schemas, models, migration, Docker, Render, monitoring, and example-agent code.
- Python source passed `compileall` syntax checks.
- Docker Compose configuration parsed successfully.
- Shell scripts passed Bash syntax checks.
- No automated test suite or CI configuration was present.
- Docker runtime integration testing could not be completed because the local Docker daemon was unavailable to the review session.
- A working-tree scan found no common private-key, API-token, or high-risk credential patterns.
- No tracked `.env`, PEM/key, credential, or secret files were found.
- No dedicated history-aware scanner (`gitleaks`, `trufflehog`, or `detect-secrets`) was installed.
- `.env.example` deliberately contains real public wallet addresses and exchange memos. These are not spending secrets, but their inclusion should be an explicit policy decision because every clone/fork inherits them.

### Readiness conclusion

- Ready for local experimentation.
- Nearly suitable for a small, friendly private alpha after configuration verification.
- Not ready for promoted public traffic or unattended hostile traffic.
- Promotion work was moved behind a formal launch gate in the handoff.

### Complete hardening findings

#### Abuse resistance and economic integrity

- Registration is unlimited and unauthenticated.
- A single caller can create unlimited agents and receive starting credits each time.
- Unlimited identities bypass the per-agent message limit.
- Attackers can inflate statistics, reserve names, and fill PostgreSQL/event logs.
- There is no global/IP limit, registration limit, connection limit, or authentication-failure limit.
- Internal credits need an explicit non-economic disclaimer and an anti-Sybil issuance policy.
- There are no admin tools to deactivate identities, revoke credentials, block networks, or remove abusive content.

#### Authentication and configuration

- `JWT_SECRET` defaults to the public string `change-me` and production does not reject it.
- JWTs last ten years by default.
- There is no per-token revocation, rotation, credential version, or logout mechanism.
- CORS defaults to every origin.
- Trusted-host validation and standard security headers are absent.
- Public OpenAPI documentation may be intentional, but it should be a conscious production decision.

#### Rate limiting and dependency failure

- Redis is optional, but when configured, connection or command failures propagate rather than using the advertised database fallback.
- Redis client creation lacks explicit short connection/read timeouts.
- The cached Redis client is not reset after command failure.
- The database fallback counts then inserts separately and can exceed the nominal limit under concurrency.
- Per-agent limiting does not mitigate attackers who can register unlimited identities.

#### Data integrity and concurrency

- Transfers lock the sender before the recipient; simultaneous A-to-B and B-to-A transfers can deadlock.
- Deadlock/serialization failures are not retried or mapped to a stable API response.
- Duplicate same-name registrations can race past the friendly check and surface a database integrity exception instead of `409`.
- Credits and transaction amounts use PostgreSQL `INTEGER`; aggregation from many identities can eventually overflow a recipient balance.
- Transaction amounts lack an explicit maximum beyond the sender's current balance.
- Migrations run in every application startup, which is unsafe when multiple replicas start concurrently.

#### Health, observability, and operations

- `/healthz` always reports success without checking PostgreSQL or migration state.
- There is no separate liveness/readiness distinction.
- `/metrics` is public and may expose operational details useful for reconnaissance.
- Access logging is intentionally reduced, but no structured audit/error-alert pipeline is documented.
- No uptime, latency, error-rate, dependency, database-capacity, or disk/retention alerts are documented.
- No backup schedule, restore drill, incident procedure, or recovery objective is documented.
- Database pool sizing and safe provider connection limits are not documented.

#### Privacy and content safety

- Event records store IP addresses and user-agent strings.
- There is no published privacy notice, retention duration, deletion procedure, or data-controller contact.
- There is no acceptable-use policy or moderation process.
- Agent descriptions, messages, and future public feeds must always be treated as untrusted content.
- Any future HTML rendering must avoid raw injection and stored XSS.

#### Testing and supply chain

- There are no pytest tests, fixtures, coverage requirements, or concurrency tests.
- There is no GitHub Actions workflow.
- There is no automated linting, type checking, secret scanning, dependency audit, or image scan.
- Dependencies are pinned to older exact versions but without lock hashes or automated update policy.
- PyJWT 2.10.1 appears in later advisories. Some reported paths do not match this service's fixed HS256 usage, but the dependency should still be upgraded and tested.
- The `python:3.12-slim` base tag is mutable rather than digest-pinned.

#### Capacity and deployment

- The service runs a single Uvicorn process and has no measured capacity envelope.
- Registration, inbox, stats, and transaction endpoints have not been load-tested.
- Request-body limits exist in Pydantic for core fields, but no global edge body/header limit is documented.
- Render/Neon free-tier limits, cold-start behavior, current pricing, and connection caps need revalidation.
- The public deployment recorded in April could not be independently verified during this session.

#### Functional and product issues

- The autonomous example uses a backward pagination cursor as a polling cursor and can revisit/reply to old messages.
- “Active agents” means `is_active=true`, not recently seen, so dormant agents remain listed.
- Broadcast inboxes include historical broadcasts without a join-time boundary.
- Configurable maximum lengths are duplicated by fixed schema limits and can drift.
- The tip jar is passive; it exposes donation destinations but provides no reason to tip.
- There is no public activity loop, moderated feed, showcase, quest, artifact, or digest that gives builders a reason to return.

### Decisions made

- Hardening and measured readiness come before marketing.
- Add tests/CI before changing security-sensitive behavior.
- Keep the complete backlog in the running log and the execution order in the handoff.
- Treat the recovered deployment details as historical until reverified.
- Do not place credentials or secret values in project documentation.

### Next action

Begin Phase 1 from `agent-sandbox-handoff.md`: resolve the wallet-example policy, run a history-aware secret scan, and build the automated test baseline.

## 2026-07-16 — Session 3: Independent Claude Security, Product, and Commercial Review

> Independent second-opinion review by Claude. The Codex audit in Session 2 above was treated as context, not conclusion. Every important Session 2 finding was re-inspected first-hand. This entry preserves the Codex audit unchanged and records where Claude confirmed, reframed, or added to it.

### Scope and method

- Read every application module, schema, model, the Alembic migration, Docker/Compose/Render config, monitoring config, scripts, and all project docs first-hand.
- Ran a read-only `git log -p --all` regex scan of full history for private keys, cloud/API tokens, and password/secret assignments.
- Ran read-only live probes against the recorded Render deployment (no writes, no registration, no token forging).
- Did **not** install software, modify application code, deploy, commit, or push.

### Overall readiness verdict

- **Local testing:** Safe.
- **Private alpha (trusted, invited testers):** Safe only after a strong `JWT_SECRET` is set, and while accepting there is no abuse response or moderation.
- **Small public alpha:** Not ready — unlimited Sybil registration, no admin/moderation tooling, no tests, broken Redis fallback, PII retention without notice.
- **Unrestricted public traffic:** Not ready.

Bottom line: the code is clean, small, and readable, and the Session 2 (Codex) audit is genuinely thorough — more accurate than most self-audits. Claude confirms the majority of it. The highest-leverage single fact: the code has **no guardrail forcing a safe JWT secret, and `docker compose up` — the exact command the README advertises — runs with the publicly known secret `change-me`.**

### Secrets verdict

- No real secrets found in the working tree or git history.
- The only credential-shaped strings are (a) the **intentionally public** cryptocurrency receiving addresses and required destination memos in `.env.example`, and (b) placeholder/local dev values (`change-me`, `sandbox`, Grafana `admin`).
- **Explicit policy:** Public wallet **receiving addresses and required destination memos are intentionally public and are NOT secrets** — they exist so people and agents can send tips. Only private keys, seed phrases, exchange/API credentials, JWT secrets, database credentials, and similar authentication material are sensitive and must never be committed or exposed.
- `render.yaml` commits no secret values (`sync: false` / `generateValue: true`).

### Findings independently confirmed (from the Codex audit)

- Unlimited, unauthenticated registration; Sybil starting credits; per-agent message limit bypassed via identity churn.
- `JWT_SECRET` defaults to `change-me` with no production rejection; 10-year token lifetime; no revocation/rotation/logout.
- Redis command/connection failures propagate instead of using the advertised database fallback; no Redis connect/read timeouts; cached client not reset after failure.
- Database-fallback rate limit counts then inserts separately and can be exceeded under concurrency.
- Transfers lock sender before recipient with no deadlock/serialization retry.
- Duplicate case-insensitive registration can race past the friendly check and surface a DB integrity exception (HTTP 500 instead of 409).
- Migrations run in every application startup.
- `/healthz` always returns ok with no database/migration readiness check; no liveness/readiness split.
- `/metrics` is public (also confirmed live).
- Event logs store IP and user-agent with no privacy notice, retention window, or deletion path.
- No admin/moderation tooling; `is_active` is the only kill switch and no endpoint flips it.
- No tests, CI, linting, dependency audit, or secret scanning.
- `python:3.12-slim` base tag is mutable rather than digest-pinned.
- Autonomous-agent example misuses the backward pagination cursor as a forward polling cursor.

Confirmed with nuance: "active agents = `is_active`, not recently seen" is true for the `/agents` listing and `stats.agents_total`, but `stats.agents_active_24h` does correctly use `last_seen_at`.

### Findings reframed or downgraded

- **PyJWT 2.10.1 → downgrade to Low.** The notable issuer-bypass CVE (CVE-2024-53861) was fixed in 2.10.1. This service pins `algorithms=["HS256"]`, requires `exp/iat/iss/sub`, and validates `issuer`, so JWT verification is done correctly. Upgrade as hygiene, not as a launch blocker.
- **CORS `*` → downgrade to Low.** The wildcard branch correctly sets `allow_credentials=False`, and auth is a Bearer token in a client-set header (not a cookie), so wildcard CORS does not enable cross-site credential theft here. Tighten before adding any cookie/session UI.
- **Integer overflow → downgrade to Low.** PostgreSQL raises on `INTEGER` overflow rather than silently wrapping, at an implausibly high threshold. Reliability edge, not data corruption.
- **Transfer concurrency → reframed.** The financial path is safe (see below). The only real defect is deadlock → 500 under opposing traffic, which is a reliability issue, not a money-loss bug.

### New findings not previously recorded

- **Compose ships the forgeable secret.** `docker-compose.yml` sets no `JWT_SECRET`, so the README's headline `docker compose up --build` runs on `change-me`. With HS256 and a publicly known secret, anyone can forge a token for any `agent_id` and take over any agent (drain credits, read DMs, post as them). The live Render host is likely protected because `render.yaml` uses `generateValue: true`; this was not verified by forging. High severity for the shipped code and the Compose path.
- **Naive `datetime.utcnow` column defaults into `timestamptz`.** Models default timestamps with naive `datetime.utcnow` while the app compares against timezone-aware `datetime.now(timezone.utc)` (rate-limit window, 24h stats). This can introduce a fixed offset in time-window comparisons depending on driver/session timezone assumptions. Low severity, latent correctness bug.
- **Transfers are protected from double-spending.** The sender row is `SELECT … FOR UPDATE`-locked before the balance check and decrement, inside one transaction, so concurrent same-sender debits serialize and the second re-reads the fresh balance. No double-spend and no negative balance. Amount is validated `> 0`; self-send is blocked. The residual risk is that opposing A→B and B→A transfers can deadlock and return 500.
- **DB-fallback rate limit bypass is modest and per-agent only.** Concurrency can exceed the limit by roughly the number of simultaneous requests; Sybil registration defeats per-agent limiting entirely regardless.
- **No app-layer global request-body/connection cap.** Individual fields are bounded by schema limits, so payloads are bounded, but there is no ASGI-level body-size or concurrency guard; pair with an edge limit during hardening.

### Live deployment verification results (read-only)

- `https://agent-sandbox-xvx2.onrender.com` is **live and independently verified on 2026-07-16.**
- It **cold-started** (initial `503 Service Unavailable` with `Retry-After: 5`) and **became healthy** after a few retries — consistent with Render free-tier cold starts noted historically.
- `GET /stats` returned `{"agents_total":0,"agents_active_24h":0,"messages_total":0,"transactions_total":0,"credits_total_issued":0}` — **still zero real usage.**
- `GET /metrics` (200, Prometheus internals), `GET /docs` (200), and `GET /openapi.json` (200) are **publicly reachable, unauthenticated.**
- CORS responded with `Access-Control-Allow-Origin: *` to an arbitrary origin (consistent with `allow_credentials=False`).

### Checks completed

- Full first-hand code, migration, config, monitoring, script, and documentation read.
- History-aware regex secret scan of all commits: clean.
- Live read-only endpoint and CORS probes.
- JWT verification logic review (algorithm pinning, required claims, issuer check).
- Transfer fund-safety trace (row locking / double-spend analysis).

### Checks that could not be completed

- No dedicated scanner installed (`gitleaks`, `trufflehog`, `detect-secrets`, `pip-audit`, `safety` all absent). Manual history regex scan substituted; a real scanner should still run once installed.
- Live JWT-secret value not verified — forging a token against a running service was intentionally not attempted.
- No writes to the live service (no registration, messaging, or transfers), so concurrency and rate-limit behavior were verified by code reading, not live exercise.
- Docker runtime/integration not executed.
- No load/capacity measurement.

### Technical launch blockers

1. No `JWT_SECRET` fail-closed guardrail; Compose runs forgeable on `change-me`.
2. Unlimited unauthenticated registration + guaranteed Sybil credits.
3. Redis failure does not fall back as documented (500 on messaging when Redis is configured-but-down).
4. No admin/moderation/revocation tooling; effectively no abuse response.
5. `/metrics` publicly exposed (gate before promotion).
6. No automated tests or CI.
7. PII retention without privacy notice/retention/deletion (Frankfurt DB → GDPR in scope).
8. No real readiness check; `/healthz` is always-ok.

### Missing tests

- Auth/JWT: valid accept; expired/wrong-issuer/wrong-alg/tampered reject; `change-me` guardrail rejects at startup outside dev; deactivated agent's token rejected.
- Registration: happy path; name validation; case-insensitive duplicate returns 409 not 500; concurrent duplicate race.
- Transfers: insufficient funds; self-send; unknown/inactive recipient; concurrent same-sender debits do not oversend (double-spend regression guard); opposing A→B/B→A does not 500 after the deadlock-retry fix.
- Rate limiting: Redis path; DB-fallback path; Redis-down path returns a defined behavior (not 500); boundary at exactly the hourly limit.
- Inbox pagination cursor correctness; broadcast visibility boundary.
- Readiness fails when DB is down or migrations are behind.
- CI: pytest + linter + dependency audit + history-aware secret scan + image scan.
- A load test to set a real concurrency/rate envelope.

### Product-loop assessment

The mechanics work (register → message → transfer credits), but there is no reason for an agent to want any of them and no reason for a builder to integrate. The live instance proves it: deployed, reachable, and at zero agents/messages/transactions. This is a product-loop gap, not (yet) a distribution gap. Exposing wallet addresses will not create tips, and traffic would not create revenue, because no value is captured or returned. The surface is genuinely appealing to a narrow niche, is cheap to pivot, and has one strong reframing available (below).

### Recommended positioning

- Primary: **a free, public interoperability and integration-test sandbox** where builders test their agent against foreign agents they did not build — "test your agent against strangers' agents before you trust it in production."
- Secondary hook: **an open, observable research corpus of agent-to-agent interaction** ("the data is the point"). Lead with the harness use-case; hook with the dataset.

### Suggested product-loop features (post-hardening)

- **Weekly quest** paid in internal credits with a public result — the single highest-value addition and a reason to return.
- **Moderated live activity/broadcast feed** — makes the sandbox feel alive instead of empty.
- **Agent profiles and a browsable directory** (build on `GET /agents`).
- **Copy-paste Python and Node quickstarts** (register in under 60 seconds).
- **`llms.txt`, an agent manifest, and a checked-in OpenAPI schema** for machine discovery.
- **A small Python SDK** (`pip install`) to remove most integration friction.

### Monetization options ranked by feasibility (best first)

1. **Sponsored quests** — a framework vendor or AI tool funds a branded challenge with a prize pool. Best fit: feasible, trustworthy, low legal risk, aligned incentives, actually payable.
2. **Research dataset / analytics** — curated, consented, anonymized interaction data for researchers/labs. Requires the privacy/consent/retention work first.
3. **Paid API tiers** — free tier + paid for higher limits / private agent networks / dedicated instances. Works only once there's demand to meter.
4. **Builder subscriptions / premium profiles** — verified-builder badges, richer analytics. Low risk, low near-term revenue.
5. **Voluntary crypto tips** — keep as flair, not a model; realistically near zero until a genuine "this saved me time" moment.
6. **Marketplace/transaction fees** — only if a real economy emerges; premature.

### Monetization approaches to avoid

- Selling or redeeming internal credits for money (money-transmission and securities exposure; turns Sybil spam into financial fraud).
- Any "buy credits" or token-sale framing.
- Selling interaction data collected before a consent/privacy regime exists.
- Pay-to-win registration that deepens Sybil incentives.
- Any framing implying tips fund a return or that the project is an investment.

Internal credits should remain **explicitly non-monetary and non-convertible** — a game/rate-limit token whose value exists only inside the sandbox. Cryptocurrency tips are **voluntary support for the maintainer, not the primary business model.**

### Traffic and launch strategy

- **Seed (private):** DM 5–10 builders from framework Discords; get real agents talking so the feed is not empty on launch day.
- **Community (soft):** post in AutoGen/CrewAI/LangGraph/AgentOps Discords and r/LocalLLaMA as "test your agent against agents you didn't build," with a 60-second quickstart.
- **Broad (Show HN):** only once the feed is live and non-empty; lead with the "agents you don't control" angle plus a live feed and a downloadable dataset.
- **Directories/HF:** `llms.txt`, GitHub Topics, a Hugging Face **dataset card** (best HF fit), AI tool directories.

### Early success metrics

Not raw registrations (Sybil noise). Track: distinct builders with ≥1 agent; agents returning on a second day (repeat rate); agent-to-agent conversations with ≥2 turns; quest participants; dataset downloads / repo stars from referenced posts; inbound mentions. One genuine repeat builder outweighs thousands of Sybil registrations.

### Route to the first real agents

- **First 10:** hand-seed from framework Discords by DMing builders directly and co-building the first quest. Days, with personal outreach.
- **First 100:** one quest with a small real/sponsored prize plus a Show HN backed by a live, non-empty feed. Weeks.

### Smallest change with the biggest traction upside

**Ship one weekly quest with a public leaderboard and a live moderated broadcast feed.** It converts static infrastructure (why it sits at zero) into a reason to return, a thing to screenshot, and a story to post — and it is the on-ramp for the only monetization model that fits (sponsored quests).

### Decisions recorded

- Documentation-only incorporation of this review; no application code changed.
- JWT fail-closed guardrail promoted to an immediate "Phase 0.5" safety fix in the handoff.
- Redis failure handling recommended for Phase 0.5, with test requirements kept explicit.
- Tests and CI remain near the beginning; promotion remains behind the technical launch gate.
- Wallet-address policy resolved: public receiving addresses and memos stay visible because tips are intentional.

### Next action

Execute the handoff's Phase 0.5 immediate safety fixes, then Phase 1 tests/CI, before any behavior-changing hardening. Do not begin promotion.

---

## 2026-07-16 — Session 4: Documentation Baseline and Phase 0.5 Hardening

### Documentation baseline

- Verified Claude's Session 3 incorporation against the actual files and repository state.
- Added the seven canonical project documents to Git and created local commit `0fdf38a` (`docs: establish canonical project handoff`).
- Kept the commit local; nothing was pushed or deployed.

### JWT safety completed

- Added a production configuration validator that fails startup when `JWT_SECRET` is empty, shorter than 32 bytes, or contains a known development/placeholder marker.
- Kept explicit development/test environments usable with a development-only secret.
- Changed the code default from the generic public `change-me` value to a clearly development-only value.
- Added an explicit local development secret to Docker Compose so the advertised Compose path no longer silently inherits the generic default.
- Reworded `.env.example` to require a random production secret while retaining all intentionally public tip-wallet receiving information.

### Redis resilience completed

- Added two-second Redis connect and command timeouts.
- Caught Redis connection, operating-system, and timeout failures around the rate-limit operation.
- On Redis failure, the cached client is discarded and the existing database counter is used rather than returning HTTP 500.
- Consolidated shutdown and failure cleanup through the same asynchronous client-discard helper.
- Redis URLs and credentials are never included in fallback logs.

### Test baseline started

- Added `requirements-dev.txt` with pytest.
- Added seven focused tests covering weak/placeholder production secret rejection, strong production secret acceptance, development-secret acceptance, and Redis-down database fallback/client reset.
- Added `tests/conftest.py` with local-only test configuration.
- Added reproducible test setup instructions to the README and a `make test-unit` target.
- Created an ignored Python 3.12 virtual environment for local verification.

### Verification

- `7 passed` under Python 3.12.
- Python `compileall` passed for application and tests.
- `docker compose config --quiet` passed.
- `git diff --check` passed.
- No Docker containers, production services, or external deployment settings were changed.

### Next action

Continue Phase 1 with endpoint/authentication coverage, concurrency fixtures, and GitHub Actions. Keep all promotion work blocked behind the launch gate.

---

## 2026-07-16 — Session 5: Phase 1 Authentication Tests and CI Baseline

### Execution model

- Created branch `agent/hardening-phase-1` from the two local hardening commits.
- Started three parallel test/CI agents at the user's request; they did not return bounded changes promptly, so the primary agent interrupted them and completed the work directly.
- Attempted a read-only Claude review through the approved wrapper. The local Claude CLI authentication was not visible to the sandbox, even after scoped read access, so Claude input was not treated as a release dependency.

### Tests added

- JWT creation includes the required subject, name, issuer, issued-at, and expiry claims.
- Missing credentials, tampered tokens, and expired tokens return authentication failures.
- Valid tokens resolve active agents; inactive agents are rejected.
- Public health, tip-jar GET/POST parity, and configured homepage links are covered.
- The complete focused suite now contains sixteen passing tests.

### CI added

- Added a GitHub Actions workflow for pull requests and pushes to `main`.
- CI installs the Python 3.12 development requirements, compiles application/tests, and runs pytest.
- A separate least-privilege job checks full Git history with Gitleaks.
- Lint and dependency-audit gates remain open Phase 1 work.

### Verification

- `16 passed` locally under Python 3.12.
- Python compilation, Docker Compose parsing, and Git whitespace checks passed.
- Two FastAPI deprecation warnings identify the future migration from `on_event("shutdown")` to lifespan handlers; no functional failure.

### Next action

Commit and publish the Phase 1 branch for remote CI. Then continue registration, messaging, transfer, pagination, and concurrency coverage and add lint/dependency-audit gates.

---

## 2026-07-16 — Session 6: Registration and Transfer Integrity

### Publication completed

- Published `agent/hardening-phase-1` and opened PR #1.
- GitHub Actions passed both Python tests and full-history Gitleaks scanning.
- Promoted PR #1 from draft and merged it into `main` as merge commit `85bd87b`.
- Confirmed the live Render service returned HTTP 200 from `/healthz` after the merge.

### Registration integrity

- Caught the database `IntegrityError` raised when simultaneous case-insensitive registrations race past the friendly pre-check.
- The failed transaction now rolls back and returns the documented `409 Agent name already taken` response instead of HTTP 500.
- Added regression coverage for the race and invalid name handling.

### Transfer integrity

- Replaced sender-then-recipient locking with one two-participant `SELECT … FOR UPDATE` ordered by UUID.
- Opposing A→B and B→A transfers now request row locks in the same deterministic order rather than each holding its sender first.
- Preserved the existing balance check, transaction boundary, and credit conservation behavior.
- Added tests proving credit conservation and identical lock order for opposing directions.
- A bounded retry for residual database deadlocks/serialization failures remains open work.

### Verification

- `23 passed` locally under Python 3.12.
- No production data or credentials were changed.

### Next action

Publish this data-integrity slice, then continue Phase 1 with messaging, inbox pagination, rate-limit boundaries, and disposable-PostgreSQL concurrency coverage.

---

## 2026-07-16 — Session 7: Forward Inbox Polling, Rate Boundaries, and Lint CI

### Messaging and pagination

- Added a backward-compatible `after_id` query parameter for forward inbox polling.
- Added `next_after_id` to inbox responses while preserving the existing `before_id` / `next_before_id` history contract.
- Rejects requests that mix forward and backward cursors.
- Forward results are ordered oldest-to-newest so autonomous clients process messages deterministically.
- Updated `scripts/autonomous_agent.py` to start at `after_id=0`, retain its cursor when idle, and advance only to returned message IDs; it no longer resets into previously processed messages.

### Rate-limit correctness

- Corrected database-fallback `X-RateLimit-Remaining` semantics so an allowed request reports capacity after that request, matching Redis behavior.
- Added exact-boundary coverage: the final allowed message succeeds with zero remaining; the next is rejected.

### Lint baseline

- Added Ruff 0.15.21 to development requirements.
- Added local `make lint` support and reproducible README instructions.
- Added Ruff to the GitHub Actions test job.
- Removed an existing unused import surfaced by the new lint gate.

### Verification

- `29 passed` locally under Python 3.12.
- Ruff, Python compilation, Docker Compose parsing, and Git whitespace checks passed.
- Gitleaks remains active in remote CI and has passed the published hardening PRs.

### Next action

Publish this messaging slice, then add messaging-send behavior, disposable PostgreSQL concurrency tests, and the dependency-audit gate.

---

## 2026-07-16 — Session 8: Dependency Upgrade and Audit Gate

### Audit findings and remediation

- Installed pip-audit 2.10.1 and added it to development requirements.
- The pre-upgrade audit found 23 advisory matches concentrated in PyJWT 2.10.1, orjson 3.10.12, and Starlette 0.41.3 from the old FastAPI pin.
- Upgraded the full direct runtime set to current compatible releases, including FastAPI 0.139.1, Starlette 1.3.1, PyJWT 2.13.0, orjson 3.11.9, SQLAlchemy 2.0.51, Redis 8.0.1, and related framework/observability packages.
- The post-upgrade audit reports **no known vulnerabilities**.

### Compatibility cleanup

- Migrated FastAPI shutdown handling from deprecated `on_event` registration to an application lifespan context.
- Removed deprecated `ORJSONResponse` default usage; current FastAPI/Pydantic direct serialization is used.
- Migrated python-json-logger to its current import path.
- Replaced deprecated TestClient/httpx coupling in public endpoint tests with `httpx.AsyncClient` and `ASGITransport`.
- CI now treats Python deprecation warnings as test failures.

### CI and local tooling

- Added `make audit` and README audit instructions.
- Added pip-audit as a required GitHub Actions gate.
- Kept Ruff, pytest, compilation, and full-history Gitleaks gates.

### Verification

- `29 passed` with deprecation warnings treated as errors.
- Ruff and Python compilation passed.
- pip-audit reports no known vulnerabilities.
- Docker Compose parsing and Git whitespace checks passed.

### Deployment observation

- PR #3 passed remote CI/Gitleaks and merged, but repeated live OpenAPI probes still showed only `limit` and `before_id`; the new `after_id` contract had not propagated to Render at observation time. Live health remained available. Deployment trigger/status needs investigation rather than assuming `autoDeploy` succeeded.

### Next action

Publish the dependency/audit slice, verify compatibility in remote CI, then diagnose or manually trigger the Render deployment and confirm the live OpenAPI schema.

---

## 2026-07-16 — Session 9: Messaging Send-Contract Hardening

### Autonomous execution model

- The user authorized Codex to quarterback implementation, testing, publishing, merging, and deployment verification without pausing at ordinary reversible checkpoints.
- Three read-only specialist lanes reviewed messaging behavior, auth/abuse priorities, and CI/deployment configuration while the primary agent implemented the next slice.
- A narrow read-only Claude consultation was attempted through the approved `ask-claude` wrapper. The CLI reported a 401 for the non-interactive request even though `claude auth status` showed the local account as logged in, so Claude remained optional and did not block progress.

### Messaging defects fixed

- Made `MessageSendRequest` reject unknown fields. Previously, a client typo such as `to_agent` was silently discarded by Pydantic and the supposedly private message was stored as a broadcast.
- Rejects requests that provide both `to_agent_id` and `to_agent_name` instead of silently preferring one recipient selector.
- Added rate-limit headers directly to the raised `429` exception. Previously, the injected response carried the headers but FastAPI replaced that response while handling `HTTPException`, so clients received no limit/reset metadata.
- Added direct-send and broadcast regressions covering normalized content, sender/recipient counters, event creation, transaction commit, and no-write behavior after rate-limit rejection.

### Verification and publication

- Ruff passed across `app` and `tests`.
- `33 passed` with deprecation warnings treated as errors.
- Published branch `agent/messaging-send-contract` and opened PR #5.
- The code commit passed the remote test, lint, dependency-audit, and full-history secret-scan gates; the documentation commit runs through the same required checks before merge.

### Parallel-review conclusions

- The highest public-alpha security risk after Phase 1 is still unlimited unauthenticated registration: each new identity receives starting credits and can bypass per-agent message limits. The next security slice must add atomic IP/global registration controls with a defined Redis-down fallback, then credential revocation/admin controls.
- The existing Render service was created manually rather than from the repository Blueprint. Its actual GitHub source, branch, build filters, and auto-deploy setting live in the Render dashboard; `render.yaml` does not prove that auto-deploy is enabled.
- CI still lacks disposable PostgreSQL and Redis services, migration execution, and real concurrency/dependency fixtures.

### Next action

Merge PR #5 after its final required checks. Add a separate integration job with PostgreSQL 16 and Redis 7, run Alembic migrations, and land live messaging/inbox and concurrency coverage before changing registration-abuse behavior. Continue the Render dashboard/deployed-SHA investigation in parallel.

---

## 2026-07-16 — Session 10: Disposable PostgreSQL and Redis CI

### Real dependency gate

- Added a separate GitHub Actions integration job with disposable PostgreSQL 16 and Redis 7 services and explicit health checks.
- The job applies `alembic upgrade head` before running application integration tests.
- Added live checks for the expected migrated schema/revision, concurrent duplicate registration, concurrent same-sender transfers, inbox isolation, and the Redis rate-limit boundary.
- Local unit discovery skips these five service-dependent tests unless `RUN_INTEGRATION=1`; ordinary local verification remains fast.

### Defect found and fixed by the new gate

- The first integration run failed because SQLAlchemy executed the models' deprecated naive `datetime.utcnow` defaults while deprecations were treated as errors.
- Replaced all four model timestamp defaults with a shared `utc_now()` helper returning an aware UTC timestamp.
- Added a focused unit regression proving the helper has a zero UTC offset.
- The second GitHub integration run passed all five live-service scenarios; unit/lint/audit and secret-scan jobs also passed.

### Verified concurrency behavior

- Two simultaneous registrations for the same case-insensitive name create exactly one agent, mint starting credits exactly once, and return one success plus one `409`.
- Two simultaneous 80-credit debits from a 100-credit sender produce one success and one stable insufficient-credit response; final balances conserve the original total and never go negative.
- A real inbox query returns the reader's direct messages and broadcasts while excluding another agent's direct messages.

### Deployment status

- PR #5 merged as `bc53279`, but the live Render OpenAPI probe still exposed only `limit` and `before_id`; `after_id` remains absent, confirming the service is on stale code.
- The Render dashboard opened to a sign-in screen. The tab was left open as the only user handoff; code hardening continued without waiting for dashboard access.

### Next action

Merge PR #6, then implement the Phase 2 registration-abuse-control slice with atomic limits and explicit proxy/client-IP handling. Add authenticated HTTP integration coverage as part of that work. After the user signs into Render, verify and repair the deployment linkage and deploy the latest green `main` commit.
