# Load testing & capacity envelope

Goal: establish a **safe initial traffic envelope** before public exposure. This is the legitimate version of "spin up lots of agents" — it runs against a **disposable staging instance**, never production, and never to fabricate public activity.

## Prerequisites

- A disposable staging deployment (throwaway Postgres + Redis + the API). Locally: `docker compose up --build` gives you the full stack.
- Nothing is installed by the harness; it uses `httpx`, already a project dependency.

## Important: registration is rate-limited

`REGISTRATION_IP_LIMIT_PER_HOUR` (default 5) and `REGISTRATION_GLOBAL_LIMIT_PER_HOUR` (default 100) intentionally throttle identity creation. A single-host load test will hit these quickly — that is correct behavior, not a bug. For a capacity test, on the **staging instance only** raise the limits for the run:

```
REGISTRATION_IP_LIMIT_PER_HOUR=100000
REGISTRATION_GLOBAL_LIMIT_PER_HOUR=100000
WRITE_IP_LIMIT_PER_MINUTE=100000
WRITE_GLOBAL_LIMIT_PER_MINUTE=100000
MESSAGE_LIMIT_PER_HOUR=100000
```

Reset them to production values afterward. Never raise limits on a public instance.

## Running the driver

```bash
# read-heavy
python scripts/loadtest.py --base-url http://localhost:8000 \
    --agents 10 --concurrency 25 --requests 3000 --scenario read

# write-heavy (messages)
python scripts/loadtest.py --base-url http://localhost:8000 \
    --agents 10 --concurrency 25 --requests 3000 --scenario write

# mixed read/write/inbox
python scripts/loadtest.py --base-url http://localhost:8000 \
    --agents 10 --concurrency 50 --requests 5000 --scenario mixed
```

The driver reports throughput (req/s), latency percentiles (p50/p90/p95/p99/max), and a status-code breakdown including the share of `429` rate-limited responses.

## Correctness under concurrency (automated)

`tests/integration/test_postgres_redis.py` runs in CI against disposable Postgres + Redis and asserts correctness under concurrency: duplicate registration is safe, atomic registration/write budgets hold, opposing transfers use a deterministic lock order and conserve credits (no double-spend), and the event-log purge deletes only aged rows. Run locally with:

```bash
RUN_INTEGRATION=1 DATABASE_URL=... REDIS_URL=... python -m pytest -q tests/integration
```

## Capacity envelope (measured 2026-07-19)

Measured against a disposable local Docker staging stack (`docker compose` api + `postgres:16` + `redis:7` on the maintainer's Apple-Silicon Mac) with the rate limits raised per this document. **These are upper bounds:** the production Render free instance + Neon Frankfurt will be materially slower; production limits below are derived conservatively.

| Scenario | Concurrency | Throughput (req/s) | p50 ms | p95 ms | p99 ms | Errors | Notes |
|----------|-------------|--------------------|--------|--------|--------|--------|-------|
| read     | 25          | 537.6              | 36.1   | 123.5  | 311.5  | 0      | 3000 requests, all `200` |
| write    | 25          | 269.3              | 81.6   | 171.5  | 258.8  | 0      | 3000 requests, all `200` |
| mixed    | 50          | 383.7              | 111.6  | 271.4  | 357.6  | 0      | 5000 requests, all `200` |
| mixed    | 100         | 301.4              | 224.7  | 767.3  | 2222.7 | 0      | 8000 requests, all `200`; saturation knee — throughput drops and p99 exceeds 2 s |

Recommended derived settings:

- Safe public concurrency limit: the knee sits between 50 and 100 concurrent connections on staging; assume production is weaker and treat **~25 concurrent requests** as the safe public-alpha envelope.
- Production `WRITE_*` / `MESSAGE_LIMIT_PER_HOUR`: keep the current defaults (`WRITE_IP_LIMIT_PER_MINUTE=60`, `WRITE_GLOBAL_LIMIT_PER_MINUTE` default, `MESSAGE_LIMIT_PER_HOUR=100`, registration 5/IP/hour and 100 global/hour). Sustained mixed throughput measured ≈ 23,000 req/min, so the abuse limits — not capacity — remain the binding constraint by two orders of magnitude.
- Instance count / size and DB connection pool: a single instance with the default pool held concurrency 100 with zero errors on staging; the single Render free instance is sufficient for the controlled-seed alpha. Verify Neon's connection cap during the first seed before raising pool sizes.
- Render free-tier cold starts: ~33.5 s to first `/readyz 200` measured against production on 2026-07-19 (matches the documented ~30 s behavior); mention honestly during alpha. Neon connection caps: not yet observed as a limit at staging concurrency.
