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

## Capacity envelope (fill in from a staging run)

Record measured results here before public launch and set production rate limits and instance sizing accordingly.

| Scenario | Concurrency | Throughput (req/s) | p50 ms | p95 ms | p99 ms | Errors | Notes |
|----------|-------------|--------------------|--------|--------|--------|--------|-------|
| read     |             |                    |        |        |        |        |       |
| write    |             |                    |        |        |        |        |       |
| mixed    |             |                    |        |        |        |        |       |

Recommended derived settings:

- Safe public concurrency limit: _TBD_
- Production `WRITE_*` / `MESSAGE_LIMIT_PER_HOUR`: _TBD_
- Instance count / size and DB connection pool: _TBD_
- Notes on Render free-tier cold starts and Neon connection caps: _TBD_
