#!/usr/bin/env python3
"""HTTP load test for Agent Sandbox.

Run this against a DISPOSABLE staging instance (never production, never to
generate fake public activity). It measures latency percentiles, throughput,
and the status/rate-limit breakdown for a mixed read/write workload.

Registration is rate-limited per IP (REGISTRATION_IP_LIMIT_PER_HOUR), so the
driver pre-registers a small pool of agents and reuses their tokens for the
load phase. To exercise higher agent counts, raise the REGISTRATION_* limits on
the staging instance for the duration of the test, or run from multiple hosts.

Usage:
    python scripts/loadtest.py --base-url https://staging.example \
        --agents 10 --concurrency 20 --requests 2000 --scenario mixed
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx


async def _register_pool(base_url: str, count: int) -> list[dict]:
    """Best-effort registration of a token pool. Tolerates 429 throttling."""
    pool: list[dict] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        for i in range(count):
            name = f"LoadAgent_{int(time.time())}_{i}"
            try:
                resp = await client.post(
                    "/register",
                    json={"name": name, "description": "load-test agent"},
                )
            except httpx.HTTPError as exc:  # network error
                print(f"  register error: {exc}")
                continue
            if resp.status_code == 200:
                data = resp.json()
                pool.append({"token": data["token"], "id": data["agent"]["id"]})
            elif resp.status_code == 429:
                print(f"  registration throttled at agent {i} (429) — using {len(pool)} tokens")
                break
            else:
                print(f"  register status {resp.status_code}: {resp.text[:120]}")
    return pool


async def _worker(
    client: httpx.AsyncClient,
    pool: list[dict],
    scenario: str,
    remaining: list[int],
    latencies: list[float],
    statuses: Counter,
    lock: asyncio.Lock,
) -> None:
    idx = 0
    while True:
        async with lock:
            if remaining[0] <= 0:
                return
            remaining[0] -= 1
        agent = pool[idx % len(pool)]
        idx += 1
        headers = {"Authorization": f"Bearer {agent['token']}"}

        if scenario == "read":
            method, path, kwargs = "GET", "/stats", {}
        elif scenario == "write":
            method, path, kwargs = (
                "POST",
                "/message/send",
                {"json": {"content": "load", "subject": "l"}, "headers": headers},
            )
        else:  # mixed: rotate read/write/inbox
            pick = idx % 3
            if pick == 0:
                method, path, kwargs = "GET", "/stats", {}
            elif pick == 1:
                method, path, kwargs = "GET", "/message/inbox", {"headers": headers}
            else:
                method, path, kwargs = (
                    "POST",
                    "/message/send",
                    {"json": {"content": "load", "subject": "l"}, "headers": headers},
                )

        start = time.perf_counter()
        try:
            resp = await client.request(method, path, **kwargs)
            statuses[resp.status_code] += 1
        except httpx.HTTPError:
            statuses["error"] += 1
        latencies.append((time.perf_counter() - start) * 1000.0)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[rank]


async def _run(args: argparse.Namespace) -> None:
    print(f"Registering up to {args.agents} agents at {args.base_url} ...")
    pool = await _register_pool(args.base_url, args.agents)
    if not pool:
        raise SystemExit("No agents registered; cannot run load test.")
    print(f"Registered {len(pool)} agents. Running {args.requests} requests "
          f"at concurrency {args.concurrency} (scenario={args.scenario}) ...")

    latencies: list[float] = []
    statuses: Counter = Counter()
    remaining = [args.requests]
    lock = asyncio.Lock()

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0, limits=limits) as client:
        await asyncio.gather(
            *(
                _worker(client, pool, args.scenario, remaining, latencies, statuses, lock)
                for _ in range(args.concurrency)
            )
        )
    elapsed = time.perf_counter() - started

    total = len(latencies)
    print("\n=== Results ===")
    print(f"requests:     {total}")
    print(f"duration:     {elapsed:.2f}s")
    print(f"throughput:   {total / elapsed:.1f} req/s")
    print(f"latency ms:   p50={_percentile(latencies, 50):.1f} "
          f"p90={_percentile(latencies, 90):.1f} "
          f"p95={_percentile(latencies, 95):.1f} "
          f"p99={_percentile(latencies, 99):.1f} "
          f"max={max(latencies):.1f}")
    print(f"mean ms:      {statistics.fmean(latencies):.1f}")
    print(f"status:       {dict(statuses)}")
    ratelimited = statuses.get(429, 0)
    if ratelimited:
        print(f"rate-limited: {ratelimited} ({100 * ratelimited / total:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Sandbox HTTP load test")
    parser.add_argument("--base-url", required=True, help="Disposable staging base URL")
    parser.add_argument("--agents", type=int, default=10, help="Token pool size to register")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument(
        "--scenario", choices=("read", "write", "mixed"), default="mixed"
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
