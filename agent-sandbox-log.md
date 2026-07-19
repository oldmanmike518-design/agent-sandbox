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

---

## 2026-07-16 — Session 11: Registration Abuse Controls

### Application controls added

- Added a PostgreSQL rate-limit bucket model and additive Alembic migration.
- Registration now consumes an atomic HMAC-client-fingerprint budget followed by a global budget before any agent lookup, insert, or starting-credit mint.
- The hierarchy stops immediately when the client budget is denied, so abusive retries cannot drain shared global capacity.
- PostgreSQL is the sole authoritative registration store. Redis availability cannot grant a second quota or reset already-consumed capacity.
- Rejections return `429`, `Retry-After`, limit, remaining, reset, and scope headers; allowed responses report the most restrictive active budget.
- Uvicorn automatic proxy-header rewriting is disabled. The app ignores forwarded client chains unless the immediate peer matches an explicitly configured trusted-proxy CIDR.
- Client bucket keys contain a truncated HMAC fingerprint rather than a raw address; expired buckets are deleted after a configurable retention grace period.

### Anti-Sybil baseline and documentation

- Default alpha budgets are five registrations per client and one hundred globally per hour, configurable by environment.
- README and deployment configuration now state that internal credits are sandbox-only, non-monetary, non-convertible, non-purchasable, and non-redeemable.
- Deployment documentation warns that the exact immediate-proxy CIDR must be verified before public traffic; leaving it blank can group clients behind the same peer proxy.

### Adversarial review corrections

- The first implementation incremented both client and global counters together and used independent Redis/database stores. The auth reviewer correctly rejected it because one IP could exhaust the global budget and a Redis outage could grant a fresh database quota.
- The implementation was replaced with hierarchical PostgreSQL-only consumption, Uvicorn proxy rewriting was disabled, retention cleanup was added, and allowed headers now select the tighter budget.
- The independent re-review found all branch-level P0/P1 issues closed and returned a merge ship verdict, while explicitly withholding public-deployment approval until the production proxy CIDR and broader privacy gate are complete.

### Verification

- Local: Ruff, compileall, Git whitespace checks, `39 passed`, `7 skipped` service-dependent scenarios.
- GitHub: unit/lint/dependency audit passed; full-history secret scan passed; disposable PostgreSQL/Redis integration job passed.
- Twenty concurrent database limiter calls from one client allow exactly five, consume exactly five global units, deny fifteen, and leave a second client able to consume remaining global capacity.
- Integration coverage also verifies most-restrictive allowed headers and deletion of expired fingerprint buckets.

### Next action

Merge PR #7. Then add cross-agent/global write caps and the JWT credential lifecycle, followed by metrics gating and database/migration readiness. Keep the live deployment blocked until Render source/auto-deploy/proxy settings are verified through the signed-in dashboard.

---

## 2026-07-16 — Session 12: Revocable Credential Lifecycle

### Secure defaults and token lifecycle

- Changed the default environment to fail-closed production. Local Compose and tests now opt into explicit development/test mode.
- Production startup rejects JWT lifetimes above 90 days and requires a separate non-placeholder admin key of at least 32 bytes.
- Render Blueprint configuration explicitly sets production mode, a 30-day JWT lifetime, generated JWT/admin secrets, and the existing hardening settings; the manually created live service still requires dashboard verification.
- Added `credential_version` to agents through an additive migration and to required JWT claims.
- Existing tokens become invalid immediately when the database credential version changes.

### Rotation and admin controls

- Added authenticated `POST /agents/me/rotate-token`; it atomically advances the credential version and returns one replacement token.
- Rotation uses compare-and-swap on the exact credential version that authenticated the request. Two simultaneous uses of one token produce exactly one replacement; an in-flight stale request cannot undo a completed admin revoke.
- Added separate-admin-key endpoints to revoke credentials or deactivate an agent. Both atomically increment credential version, emit an audit event, and commit before returning.
- Wrong/missing admin keys return a generic authentication failure; an unconfigured admin API is unavailable; key comparison uses a constant-time primitive.

### Adversarial correction and cutover decision

- The first rotation update filtered only by agent ID and active state. The auth reviewer correctly proved that concurrent rotations could both succeed and a stale rotation could mint a valid token after admin revocation.
- Added the credential-version CAS predicate plus two forced PostgreSQL race tests: synchronized same-token rotations and admin-revoke-before-stale-update. The independent re-review returned a merge ship verdict.
- Re-probed live `/stats` immediately before merge preparation: HTTP 200 with `agents_total=0`. Requiring the new `cv` claim therefore intentionally invalidates only legacy-format zero-user credentials; this is recorded as a one-time clean cutover.

### Verification

- Local: Ruff, compileall, shell syntax, Compose parsing, Git whitespace checks, `48 passed`, `10 skipped` service-dependent tests.
- GitHub: unit/lint/dependency audit, full-history secret scan, and disposable PostgreSQL/Redis integration jobs all passed.
- Integration coverage proves rotation, old-token rejection, new-token acceptance, admin revoke, deactivation, exactly-one concurrent replacement, and no stale post-revoke credential minting.

### Remaining recovery decision

- Rotation is intentionally destructive at commit. If the replacement response is lost, the agent is stranded; admin revoke/deactivate currently has no recovery/reissue/reactivation path.
- This does not weaken revocation and did not block merge, but public readiness requires either an explicit disposable-identity policy or a carefully audited secure recovery mechanism.

### Next action

Merge PR #8. Then implement cross-agent/global write caps and resolve the identity-recovery policy before metrics gating and dependency/migration readiness.

---

## 2026-07-16 — Session 13: Global Authenticated-Write Controls

### Cross-agent abuse budget

- Generalized the PostgreSQL-authoritative hierarchical limiter used by registration.
- Added one shared per-client/global budget across authenticated message, transfer, and ping writes. Creating more agent identities no longer creates more aggregate write capacity from the same client, and the global ceiling limits aggregate traffic across clients.
- Client-denied attempts stop before the global counter, preserving shared capacity during a single-client flood.
- Limiter counters commit before endpoint mutations and remain consumed if a later recipient, balance, or per-agent validation rejects the request. This deliberately budgets attempts, not only successful writes; those later errors carry the consumed budget's headers.
- PostgreSQL remains fail-closed and authoritative; there is no Redis/database split-brain quota.
- Write-path cleanup removes expired HMAC client buckets beyond the configured retention grace period on the next controlled request, so abandoned identifiers do not depend on future registrations for cleanup.

### Client contract and deployment configuration

- Successful and rejected writes expose scoped `X-RateLimit-*` headers; rejected writes include `Retry-After`.
- Message sends retain their tighter per-agent hourly limiter and report the more restrictive active scope.
- Added configurable per-client, global, and window values to settings, `.env.example`, the Render Blueprint, README, and deployment instructions.
- Default public-alpha values are 60 writes per client per minute and 600 writes globally per minute. Deployment-edge throttling is still required before public promotion.

### Verification

- Local: Ruff, compileall, shell syntax, Compose parsing, Git whitespace checks, `54 passed`, `11 skipped` disposable-service tests.
- GitHub PR #9: unit/lint/dependency audit, full-history secret scan, and PostgreSQL/Redis integration jobs passed.
- Twenty concurrent attempts from one client allow exactly five under a test limit, consume exactly five global units, and deny fifteen without draining global capacity. A second client can consume the final global unit through a different write endpoint, proving the bucket is cross-client and cross-endpoint.
- Direct ping tests prove allowed activity is committed with rate headers and denied activity writes nothing.
- Adversarial review found that the limiter's independent commit could leave the authenticated sender cached in SQLAlchemy's identity map. A later `FOR UPDATE` lock could therefore serialize correctly but still read the pre-lock balance. Locked participant queries now force `populate_existing`, and the PostgreSQL race test authenticates and binds both senders before their limiter commits; exactly one debit still succeeds and total credits remain conserved.

### Next action

Merge PR #9. Explicitly adopt the disposable-identity public-alpha policy, then gate metrics and implement database/migration readiness plus authenticated HTTP integration coverage. Continue hardening without promoting or deploying until the Render dashboard configuration is verified.

---

## 2026-07-16 — Session 14: Paused Operational-Readiness Checkpoint

### Merged baseline

- PR #9 merged to GitHub `main` as `8ee5d06` after all GitHub gates passed and the adversarial re-review returned a ship verdict.
- The merged slice adds PostgreSQL-authoritative cross-agent write budgets, refreshes locked transfer participants after the limiter's independent commit, bounds expired write-bucket retention, and preserves rate headers on post-limit failures.
- The live Render service was **not** deployed or modified and may still be on stale code.

### Local work in progress — checkpointed locally, not published

- Created local branch `agent/operational-readiness` from `8ee5d06`.
- Added a proposed dedicated `METRICS_API_KEY` bearer gate for `/metrics`, with production validation requiring JWT, admin, and metrics secrets to be strong and distinct.
- Added a proposed `/readyz` check that verifies PostgreSQL connectivity and exact agreement between `alembic_version` and the code's single migration head; `/healthz` remains dependency-free liveness.
- Pointed the proposed Render and container health checks at `/readyz`.
- Drafted the public-alpha disposable-identity policy: the returned token is the only credential; no replacement credential is issued without a pre-enrolled recovery factor; lost registration or rotation responses require a new identity.
- Extended local tests for metrics authentication, production key validation, readiness success, schema mismatch, database failure, and the live migrated PostgreSQL readiness function.

### Local verification at pause

- Ruff passed.
- `59 passed`, `11 skipped` disposable-service tests under deprecations-as-errors.
- Python compilation, shell syntax, Compose parsing, and Git whitespace checks passed.
- One local checkpoint commit preserves this WIP slice. No push, pull request, merge, deployment, browser action, or provider-setting change was made.

### Why work paused

- The browser open for Render verification was the user's work-profile browser, while Render/GitHub/provider access was created with the user's personal accounts and personal browser profile.
- Per the user's instruction, dashboard and deployment work is pinned. Do not use or alter the work-profile browser. Resume provider verification only after the user identifies or opens the personal browser/profile.

### Exact resume point

1. Open `/Users/michaellanger/Projects/agent-sandbox` and confirm branch `agent/operational-readiness`; use `git log -1` and `git status` to identify the exact local checkpoint.
2. Re-read the checkpoint diff against `main` and rerun Ruff, pytest, compileall, shell, Compose, and whitespace checks.
3. Send the metrics/readiness/auth boundary for read-only adversarial review.
4. If clean, commit locally, push, open the next PR, and require unit/audit, Gitleaks, and PostgreSQL/Redis integration gates before merge.
5. Keep deployment and Render settings untouched until the user provides the personal browser/profile.

---

## 2026-07-16 — Session 15: Autonomous Launch-Readiness Sprint (Claude)

Autonomous engineering sprint under a "keep moving until launch-ready" mandate, in the documented order: web-exposure hardening → product-loop assets → privacy notice → load test. Push/PR/merge on green CI + adversarial self-review; no deploy, no public posting, no browser/account changes. Started from `main` @ `8ee5d06`; ended at `main` @ `66acb03`.

### Merged this session

- **PR #10** — operational readiness (from the previously-paused checkpoint): `/metrics` gated behind `METRICS_API_KEY`, new `/readyz` (DB + Alembic-head check), Render health check → `/readyz`.
- **PR #11** — web-exposure hardening: security headers on every response (nosniff, `X-Frame-Options: DENY`, Referrer-Policy, framing CSP, Permissions-Policy), `TrustedHostMiddleware` host allowlist (`ALLOWED_HOSTS`, loopback auto-added), request-body cap (`MAX_REQUEST_BYTES`), optional HSTS (`SECURITY_HSTS_SECONDS`). New `app/core/middleware.py` + 6 tests.
- **PR #12** — product-loop discovery: served `/llms.txt` and `/.well-known/agent-manifest.json`, checked-in `openapi.json`/`llms.txt`/manifest snapshots + `scripts/dump_discovery.py`, a minimal Python SDK (`sdk/python`, `agent-sandbox-client`), and Python/Node quickstarts (`examples/`). Manifest advertises credits as non-monetary.
- **PR #13** — privacy/retention: `PRIVACY.md` + `ACCEPTABLE_USE.md`, `EVENT_LOG_RETENTION_DAYS` (default 90) with `purge_expired_events()` + `scripts/purge_old_events.py`, policies linked from README/llms.txt/manifest. Unit + purge integration tests.
- **PR #14** — load test: `scripts/loadtest.py` (throughput, latency percentiles, status/429 breakdown), `docs/LOAD_TESTING.md` (methodology + capacity-envelope template), and a ring-of-concurrent-transfers CI stress test proving credit conservation under contention.

All five passed remote CI (test + Postgres/Redis integration + Gitleaks) before merge. Test suite grew 59 → 71 local tests (+ integration).

### Deliberate scope calls (did NOT do, on purpose)

- **No fake-agent "pumping."** Fabricated registrations would astroturf public stats, trip the merged anti-Sybil/registration controls, and poison trust. The legitimate substitute is the load-test harness against disposable staging.
- **No public unauthenticated activity/broadcast feed.** It would expose arbitrary agent-submitted text with no moderation/takedown tooling (stored-content abuse risk). Parked in Phase 7 pending a moderation decision.
- **No personal email committed.** Data-controller contact left as `<CONTACT_EMAIL>` placeholder for the maintainer to set.
- **No rushed money-path retry.** Transfers already lock both participants in a single deterministic `SELECT … IN (…) ORDER BY id FOR UPDATE`, which prevents deadlocks; the CI ring stress test proves conservation. Bounded retry is optional defense-in-depth, recommended as a separately-reviewed follow-up rather than a tail-of-sprint change to the most safety-critical code.

### Could not do here (no Docker daemon, no local Postgres/Redis, no load tools)

- Measured load/capacity numbers — delivered the harness + methodology + a CI correctness-under-load test instead; the envelope must be measured against staging.
- Any deployment or dashboard verification — requires the maintainer's personal browser profile.

### Remaining before launch (human + decisions, not code)

Captured in `DEPLOYMENT_HANDOFF.md`: redeploy Render to current `main` and set env/secrets/health-check (the live service still runs old code — public `/metrics`, no `/readyz`); schedule the retention purge; set the data-controller contact; run the load test and record the envelope. Promotion stays blocked; the feed/quest need product + moderation decisions.

### Next action

Maintainer works `DEPLOYMENT_HANDOFF.md` on the personal browser. Do not begin promotion.

---

## 2026-07-16 — Session 16: Production Deployment, Distribution Setup, and Closeout (Codex)

The user reopened the personal Chrome profile, explicitly authorized Codex to take over the Render configuration/deployment work, and asked for a complete documented handoff ready for the next session.

### GitHub distribution work

- Updated the public repository description to lead with agent interoperability and testing against agents the builder did not create.
- Set the repository homepage to the production Render URL.
- Added discovery topics: `agent-interoperability`, `agent-testing`, `ai-agents`, `autonomous-agents`, `fastapi`, `llm`, `multi-agent-systems`, `openapi`, and `python`.
- Prepared `PROMOTION-COMMAND-CENTER.md` with exact channel order, ready-to-paste AutoGen/CrewAI/LangGraph seed copy, later Reddit/Show HN copy, software-agent discovery/adapters, legitimate project-operated agent rules, success metrics, and monetization sequence.

### Render account and service recovery

- Confirmed the user has a Render account and located the manually created `agent-sandbox` Web Service.
- Confirmed the service source is `oldmanmike518-design/agent-sandbox`, branch `main`.
- Confirmed the production URL is https://agent-sandbox-xvx2.onrender.com and service ID is `srv-d7a57o15pdvs73c0g3cg`.
- Identified that an old April commit was still deployed and that the previous health-path update had queued a stale build.
- Canceled the stale old-code deployment so current `main` could proceed.

### Production configuration

Configured Render without displaying, logging, or committing secret values:

- production environment mode;
- strong, distinct JWT, admin, and metrics secrets;
- 30-day JWT lifetime;
- production base URL;
- exact allowed host;
- exact production CORS origin;
- `/readyz` health-check path;
- preserved database, owner message, and intentional public wallet receive configuration.

The first live CORS check revealed the service was still returning wildcard access because the wrong masked environment row had retained `*`. Codex reopened the alphabetically ordered environment editor, replaced the exact `CORS_ORIGINS` row with the production origin, saved it, and allowed Render to rebuild current `main`.

### Deployment result

- PR #15 had merged the sprint documentation, making `1be6d96eb69114aea9256c625d0703e696915eb6` the current `main`.
- Render deployed that commit successfully.
- Final configuration deployment: `dep-d9cjsvt7vvec73einrrg`.
- Final Render state: **Live**, 48.9-second deploy.
- The service homepage opened successfully from the signed-in browser.

### Live verification

The following checks passed on the hardened build:

- `/readyz` returned `200` with database available and schema current.
- `/healthz` returned `200`.
- unauthenticated `/metrics` returned `401`.
- `/llms.txt`, `/.well-known/agent-manifest.json`, and `/openapi.json` returned `200`.
- `/docs` returned `200`.
- an invalid Host header returned `403`.
- CSP, Permissions-Policy, Referrer-Policy, `X-Content-Type-Options: nosniff`, and `X-Frame-Options: DENY` were present.
- the manifest used the production base URL and the OpenAPI snapshot contained 27 paths including forward inbox polling.
- `/stats` remained at zero agents, messages, and transactions.

After the corrected CORS value triggered the final deploy, Render showed the same current commit Live and the public homepage reopened. The managed shell/browser environment could not perform a second arbitrary-origin response-header probe, so the first real outside-builder integration should record that smoke check.

### Launch decision

- The engineering and deployment gate is complete.
- The **controlled seed launch is open** for 3–5 genuine outside framework builders.
- Fake registrations, fabricated agent traffic, and engagement manipulation remain prohibited.
- Broad Reddit/Show HN promotion waits for five concrete items: scheduled retention, public contact, measured staging capacity, backup/alert ownership, and at least three real outside integrations.
- The next session starts with seed recruitment and real interactions, not another general audit.

### Documentation reconciliation

- Replaced the stale “live old code / redeploy required” handoff with the exact current production state.
- Converted `DEPLOYMENT_HANDOFF.md` from a to-do sheet into a completed deployment record plus remaining operations.
- Updated `AGENTS.md`, the project brief, and the marketing plan so controlled seed outreach is open while broad promotion remains measured and gated.
- Added the promotion command center to the repository.
- Preserved Sessions 1–15 unchanged.

### Publication record

- Documentation closeout commit `dcb9986` was pushed on `agent/session-16-launch-handoff`.
- Opened GitHub PR #16, `docs: close out deployment and open controlled seed`, targeting `main`.

### Remaining operational work

1. Schedule the daily event-retention purge.
2. Publish a dedicated data-controller contact.
3. Measure and record a staging capacity envelope.
4. Assign database backup/restore and alert owners.
5. Complete real integrations with at least three outside framework builders.

## 2026-07-19 — Session 17: Production Smoke Pass and Measured Capacity Envelope (Claude)

Local session on the maintainer's machine. Fast-forwarded the canonical checkout to `origin/main` (`78e1a3d`, Session 16 closeout), then executed the two "Next Session" items that were possible without the personal browser or a maintainer decision: the production end-to-end smoke interaction and the staging capacity measurement. No pushes, no deploys, no provider changes; documentation edits are local and uncommitted pending maintainer review.

### Production end-to-end smoke interaction (handoff step 4)

Ran register → discover → broadcast → forward-poll inbox → stats against `https://agent-sandbox-xvx2.onrender.com` using a clearly-labeled project-operated agent (`SandboxSmokeCheck_*`, description states it is a maintainer smoke test, not a real user). All steps passed:

- Cold start: first `/readyz` took ~33.5 s then returned `200 {"status":"ready","database":"available","schema":"current"}` — matches the documented Render free-tier behavior.
- `/register` → `200` with token and agent id; `/agents` → `200`.
- Broadcast `/message/send` → `200`; `/message/inbox?after_id=0` returned the message with `next_after_id=1`; polling again from the cursor returned zero items (no reprocessing — the forward-polling contract holds in production).
- `/stats` → `200`: 2 agents, 1 message, 0 transactions.

Two labeled smoke agents now exist in production (a first script attempt registered before a client-side script bug aborted it; the bug was in the throwaway test script, not the API). No bearer tokens or secrets were recorded.

### Observations (no launch blockers)

1. **`agents_active_24h` counts only `/ping` heartbeats.** `last_seen_at` is updated exclusively in the ping endpoint, so an agent that registers and messages but never pings shows as inactive and the stat reads 0 even during real use. Semantics, not a defect — but consider bumping `last_seen_at` on authenticated writes, or documenting that the stat means "agents heartbeating via /ping."
2. **Compose startup race.** On a cold `docker compose up --build`, the API container can start before PostgreSQL finishes initializing, crash on connection-refused, and stay exited (`depends_on` has no health condition and no restart policy). A manual container restart fixes it. Optional small fix: add a `pg_isready` healthcheck to `db` and `condition: service_healthy` to the api's `depends_on`.

### Staging capacity envelope (handoff checklist item 3)

Stood up the disposable staging stack locally (Docker compose api + postgres:16 + redis:7) with the rate limits raised per `docs/LOAD_TESTING.md` via a compose override kept outside the repo, ran `scripts/loadtest.py`, then destroyed the stack and its volumes. Measured (all responses `200`, zero errors at every level):

| Scenario | Concurrency | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|
| read | 25 | 537.6 req/s | 36.1 ms | 123.5 ms | 311.5 ms |
| write | 25 | 269.3 req/s | 81.6 ms | 171.5 ms | 258.8 ms |
| mixed | 50 | 383.7 req/s | 111.6 ms | 271.4 ms | 357.6 ms |
| mixed | 100 | 301.4 req/s | 224.7 ms | 767.3 ms | 2222.7 ms |

The saturation knee is between concurrency 50 and 100 (throughput regresses and p99 exceeds 2 s at 100). Full numbers and conservatively derived production settings are recorded in `docs/LOAD_TESTING.md`: treat ~25 concurrent requests as the safe public-alpha envelope, keep current production rate limits (they bind two orders of magnitude below measured capacity), single instance is sufficient for the controlled seed. Local Apple-Silicon staging is an upper bound on the weaker production tier.

### Remaining operational work

1. Schedule the daily event-retention purge (personal browser, Render cron).
2. Publish a dedicated data-controller contact in `PRIVACY.md`/`ACCEPTABLE_USE.md` (maintainer decision).
3. Assign database backup/restore and alert owners.
4. Recruit 3–5 real outside framework builders for the controlled seed (maintainer accounts; seed copy is ready in `PROMOTION-COMMAND-CENTER.md`).

Broad-launch gate status after this session: staging envelope ✅; retention scheduling, public contact, backup/alert ownership, and three real outside integrations remain.

### Session 17 publication and workspace closeout (Codex)

- Reviewed the three-file Session 17 documentation diff and confirmed it contained only the smoke-test, load-test, and handoff updates.
- Committed the work as `8dbec31` on `agent/session-17-capacity-handoff`, pushed the branch, and opened draft PR #17. GitHub CI completed successfully for test, integration, and secret-scan jobs.
- Rechecked production: `/readyz` returned `200` with database available and schema current, and `/healthz` returned `200`; the warm readiness request completed in about 0.29 seconds.
- Confirmed `/Users/michaellanger/Projects/agent-sandbox` as the sole canonical workspace for Codex, Claude, Gemini, and other tools.
- Verified the Codex Session 16 checkout under `Documents/Codex` was a clean duplicate and the `Documents/bug-bounties/agent-sandbox` checkout was obsolete. Automated removal was blocked by macOS permissions; the maintainer then moved both to Trash manually, and Codex verified both paths were absent. No changes needed combining.
- Updated the tool handoff so the next session begins with PR #17 review/merge, controlled-seed recruitment, and the remaining operational gates—not another engineering audit.

## 2026-07-19 — Session 18: PR #17 Merge and Adopted Distribution Strategy (Claude)

### PR #17 merged

With explicit maintainer authorization, PR #17 was marked ready and merged as `8faf95c`. The local canonical checkout is back on `main`, fast-forwarded, clean.

### Strategy decision (Codex proposed, Claude refined, Codex concurred, maintainer adopted)

The maintainer asked both tools how independently operating agents would ever find and use Agent Sandbox. The converged answer, now recorded as durable decisions in the handoff:

- **Vision:** Agent Sandbox is the place builders send their agents to prove interoperability against systems they did not build — while remaining directly usable by the agents themselves. The first audience is builders bringing agents; "agents independently encountering the sandbox" is the eventual flywheel, not the entry strategy.
- **The platform was the destination; distribution is the missing roads.** Roads, in leverage order: seed builders → always-on conformance partner → remote MCP server + official MCP Registry → five-minute framework recipes → searchable content and real integration reports → honest A2A implementation when warranted (never a renamed manifest).
- **New product commitment:** a transparent `InteropConformanceAgent` (added to the command center's legitimate house agents) that gives every arriving agent a deterministic interop exchange and a machine-readable pass/fail report. It converts arrival into first-session value and produces publishable evidence without fabricating activity.
- **MCP is sequenced before A2A** because its deployed client base is far larger today.
- **Corpus qualification:** count on search indexing and links immediately; treat model-training inclusion as an uncontrollable long-term bonus.
- **Seed-operations caution:** shared cloud egress IPs will trip the 5/IP/hour registration limit; watch for it during seeding before diagnosing churn.

Handoff "Next Session" was rewritten to the adopted sequence; the command center's follow-ons were reordered to match. No code changes this session. Conformance-agent and MCP-adapter builds are ready to start on maintainer go; deploying any house agent requires maintainer authorization.
