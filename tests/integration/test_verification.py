from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1", reason="integration tests disabled"
)

_TEST_LOOP = asyncio.new_event_loop()


def _run(coroutine):
    return _TEST_LOOP.run_until_complete(coroutine)


@pytest.fixture(scope="module", autouse=True)
def _migrated_database():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env={**os.environ},
    )
    yield
    from app.db.session import engine

    _TEST_LOOP.run_until_complete(engine.dispose())
    _TEST_LOOP.close()


@pytest.fixture(autouse=True)
def _generous_limits(monkeypatch):
    from app.core.config import settings

    for name, value in {
        "REGISTRATION_IP_LIMIT_PER_HOUR": 100000,
        "REGISTRATION_GLOBAL_LIMIT_PER_HOUR": 100000,
        "WRITE_IP_LIMIT_PER_MINUTE": 100000,
        "WRITE_GLOBAL_LIMIT_PER_MINUTE": 100000,
        "MESSAGE_LIMIT_PER_HOUR": 100000,
        "VERIFY_RUNS_PER_AGENT_PER_DAY": 1000,
        "VERIFY_RUNS_PER_IP_PER_DAY": 100000,
        "VERIFY_RUNS_GLOBAL_PER_DAY": 100000,
        # Deterministic timing: with the floor at 0, the compliant driver
        # needs NO real sleeps. Tests that exercise the floor raise it
        # locally via monkeypatch instead of racing wall-clock time.
        "VERIFY_POLL_FLOOR_MS": 0,
    }.items():
        monkeypatch.setattr(settings, name, value)


def _client(raise_app_exceptions: bool = True) -> AsyncClient:
    from app.main import app

    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url="http://testserver",
    )


async def _register(client: AsyncClient, prefix: str):
    name = f"{prefix}_{uuid.uuid4().hex[:10]}"
    resp = await client.post(
        "/register", json={"name": name, "description": "integration test agent"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["agent"]["id"], {"Authorization": f"Bearer {data['token']}"}, name


async def _bootstrap_partner():
    from app.db.session import AsyncSessionLocal
    from app.services.system_agents import ensure_conformance_agent

    async with AsyncSessionLocal() as session:
        await ensure_conformance_agent(session)


def _extract_token(content: str) -> str | None:
    for word in content.replace("\n", " ").split(" "):
        if word.startswith("nonce:"):
            return word.strip(".,;")
    return None


async def _open_run(client: AsyncClient, auth: dict) -> dict:
    resp = await client.post("/verify", headers=auth, json={})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _drive_compliant(client: AsyncClient, auth: dict, opened: dict, *, sleep: float = 0.0) -> dict:
    """Executes the instructed flow exactly, via public endpoints only.
    Returns endpoint-derived state ({run_id, nonce, fresh_nonce, partner})
    so no test ever needs a direct database read for flow values. sleep
    defaults to 0 because the fixture sets the poll floor to 0."""
    run_id = opened["run_id"]
    partner = opened["instructions"]["partner"]
    assert (
        await client.get(
            "/agents",
            headers=auth,
            params={"q": partner["name"]},
        )
    ).status_code == 200

    resp = await client.post(
        "/message/send", headers=auth,
        json={"to_agent_name": partner["name"], "subject": "hello", "content": "hello partner"},
    )
    assert resp.status_code == 200, resp.text

    cursor, nonce, edge_seen = 0, None, 0
    for _ in range(60):
        await asyncio.sleep(sleep)
        resp = await client.get("/message/inbox", headers=auth, params={"after_id": cursor})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            if item["sender_id"] != partner["id"]:
                continue
            if item["content"].startswith("edge:"):
                edge_seen += 1
            token = _extract_token(item["content"])
            if token and nonce is None:
                nonce = token
        if data["next_after_id"] is not None:
            cursor = data["next_after_id"]
        if nonce and edge_seen >= 6:
            break
    assert nonce and edge_seen >= 6, f"nonce={nonce} edges={edge_seen}"

    await asyncio.sleep(sleep)
    resp = await client.post(
        "/message/send", headers=auth,
        json={"to_agent_name": partner["name"], "subject": "echo", "content": f"echo {nonce}"},
    )
    assert resp.status_code == 200

    status = (await client.get(f"/verify/{run_id}", headers=auth)).json()
    replay_after = status["instructions"]["state"]["replay_after_id"]
    await asyncio.sleep(sleep)
    resp = await client.get("/message/inbox", headers=auth, params={"after_id": replay_after})
    assert resp.status_code == 200  # duplicate re-served; deliberately NOT re-echoed

    fresh = None
    for _ in range(60):
        await asyncio.sleep(sleep)
        resp = await client.get("/message/inbox", headers=auth, params={"after_id": cursor})
        data = resp.json()
        for item in data["items"]:
            if item["sender_id"] != partner["id"]:
                continue
            token = _extract_token(item["content"])
            if token and token != nonce:
                fresh = token
        if data["next_after_id"] is not None:
            cursor = data["next_after_id"]
        if fresh:
            break
    assert fresh, "fresh nonce never arrived"

    await asyncio.sleep(sleep)
    resp = await client.post(
        "/message/send", headers=auth,
        json={"to_agent_name": partner["name"], "subject": "echo", "content": f"echo {fresh}"},
    )
    assert resp.status_code == 200
    return {"run_id": run_id, "nonce": nonce, "fresh_nonce": fresh, "partner": partner}


async def _finalize(client: AsyncClient, auth: dict, run_id: str) -> dict:
    resp = await client.post(f"/verify/{run_id}/finalize", headers=auth)
    assert resp.status_code == 200, resp.text
    return resp.json()
def test_compliant_client_scores_eight_of_eight_and_report_is_public():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, name = await _register(client, "Compliant")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            result = await _finalize(client, auth, run_id)
            slug = result["report_slug"]
            report_json = await _client_get_json(client, slug)
            assert result["complete"] is True, report_json["results"]
            assert result["passed"] == 8 and result["failed"] == 0, report_json["results"]
            assert (await client.get(f"/reports/{slug}.json")).status_code == 200
            page = await client.get(f"/reports/{slug}")
            assert page.status_code == 200 and name in page.text
            assert (await client.get(f"/reports/{slug}/badge.json")).json()["color"] == "brightgreen"
            assert (await client.get(f"/reports/{slug}/badge.svg")).headers["content-type"].startswith("image/svg")
    _run(_case())


def test_foreign_traffic_does_not_affect_results():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, noisy_auth, _ = await _register(client, "Noisy")
            _, auth, _ = await _register(client, "Target")
            opened = await _open_run(client, auth)

            async def _noise():
                for _ in range(8):
                    await client.post(
                        "/message/send", headers=noisy_auth,
                        json={"subject": "noise", "content": "broadcast noise"},
                    )
                    await asyncio.sleep(0.4)

            noise_task = asyncio.create_task(_noise())
            run_id = (await _drive_compliant(client, auth, opened))["run_id"]
            await noise_task
            result = await _finalize(client, auth, run_id)
            assert result["passed"] == 8, result
    _run(_case())


def test_double_echo_fails_duplicate_suppression():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "DoubleEcho")
            opened = await _open_run(client, auth)
            flow = await _drive_compliant(client, auth, opened)
            run_id = flow["run_id"]
            # Deficiency: echo the ORIGINAL nonce a second time before
            # finalizing. The nonce comes from the endpoint-driven flow —
            # never from a direct database read.
            await client.post(
                "/message/send", headers=auth,
                json={"to_agent_name": flow["partner"]["name"], "subject": "oops", "content": f"echo {flow['nonce']}"},
            )
            result = await _finalize(client, auth, run_id)
            slug = result["report_slug"]
            report = (await client.get(f"/reports/{slug}.json")).json()
            assert report["results"]["duplicate_delivery_suppression"]["state"] == "FAIL"
            assert report["results"]["nonce_round_trip"]["state"] == "PASS"
    _run(_case())


def test_unreturned_cursor_fails_forward_cursor():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "BadCursor")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            # Deficiency: poll with a cursor the server never returned.
            await client.get("/message/inbox", headers=auth, params={"after_id": 10**9})
            result = await _finalize(client, auth, run_id)
            report = (await _client_get_json(client, result["report_slug"]))
            assert report["results"]["forward_cursor_correctness"]["state"] == "FAIL"
    _run(_case())


async def _client_get_json(client: AsyncClient, slug: str) -> dict:
    resp = await client.get(f"/reports/{slug}.json")
    assert resp.status_code == 200
    return resp.json()


def test_hot_loop_fails_polling_discipline(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "HotLoop")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            # Deterministic without wall-clock racing: raise the floor so the
            # deliberately added rapid polls all violate it at evaluation
            # time. The spec fails only after more than three violations.
            from app.core.config import settings
            monkeypatch.setattr(settings, "VERIFY_POLL_FLOOR_MS", 10**7)
            for _ in range(5):
                response = await client.get(
                    "/message/inbox",
                    headers=auth,
                    params={"after_id": 0},
                )
                assert response.status_code == 200
            result = await _finalize(client, auth, run_id)
            report = await _client_get_json(client, result["report_slug"])
            assert report["results"]["polling_discipline"]["state"] == "FAIL"
    _run(_case())


def test_token_rotation_mid_run_continues_and_completes():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Rotator")
            opened = await _open_run(client, auth)
            # Locate the self-rotation endpoint from the live schema rather
            # than hardcoding a path this plan cannot know.
            paths = (await client.get("/openapi.json")).json()["paths"]
            rotate_path = next(p for p in paths if "rotate" in p)
            resp = await client.post(rotate_path, headers=auth)
            assert resp.status_code == 200, resp.text
            new_auth = {"Authorization": f"Bearer {resp.json()['token']}"}
            assert (await client.get(f"/verify/{opened['run_id']}", headers=auth)).status_code == 401
            run_id = (await _drive_compliant(client, new_auth, opened))["run_id"]
            result = await _finalize(client, new_auth, run_id)
            assert result["passed"] == 8
    _run(_case())


def test_admin_revocation_aborts_open_run():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            agent_id, auth, _ = await _register(client, "Revoked")
            opened = await _open_run(client, auth)
            from app.core.config import settings
            paths = (await client.get("/openapi.json")).json()["paths"]
            revoke_path = next(p for p in paths if "revoke" in p and "{" in p).replace("{agent_id}", agent_id)
            resp = await client.post(revoke_path, headers={"X-Admin-Key": settings.ADMIN_API_KEY})
            assert resp.status_code == 200, resp.text
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.verification import VerificationRun
            async with AsyncSessionLocal() as s:
                run = (await s.execute(select(VerificationRun).where(VerificationRun.id == uuid.UUID(opened["run_id"])))).scalar_one()
                assert run.status == "aborted"
                assert run.lifecycle_note == "credentials_revoked"
    _run(_case())


def test_5xx_incident_is_recorded_and_budget_refunded(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        async with _client(raise_app_exceptions=False) as client:
            _, auth, _ = await _register(client, "Incident")
            opened = await _open_run(client, auth)
            # Induce one 500 on the inbox path for this verifying agent.
            from app.api.v1.endpoints import messages as messages_module
            original = messages_module.record_observation
            calls = {"n": 0}
            async def _boom(*args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("induced observation failure")
                return await original(*args, **kwargs)
            monkeypatch.setattr(messages_module, "record_observation", _boom)
            resp = await client.get("/message/inbox", headers=auth, params={"after_id": 0})
            assert resp.status_code == 500
            monkeypatch.setattr(messages_module, "record_observation", original)

            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.rate_limit_bucket import RateLimitBucket
            from app.models.verification import VerificationRun
            async with AsyncSessionLocal() as s:
                run = (await s.execute(select(VerificationRun).where(VerificationRun.id == uuid.UUID(opened["run_id"])))).scalar_one()
                assert run.verifier_fault is True
                assert any(i["path"].endswith("/message/inbox") for i in run.verifier_incidents)
                keys = [w["key"] for w in run.run_metadata["budget_buckets"]]
                before = {
                    b.bucket_key: b.count
                    for b in (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key.in_(keys)))).scalars()
                }
            result = await _finalize(client, auth, opened["run_id"])
            assert result["verifier_fault"] is True
            async with AsyncSessionLocal() as s:
                after = {
                    b.bucket_key: b.count
                    for b in (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key.in_(keys)))).scalars()
                }
            assert all(after[k] == before[k] - 1 for k in before), (before, after)
    _run(_case())


def test_dead_lettered_nonce_is_verifier_fault_not_agent_fail(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        from app.core.config import settings
        from app.services.verification import driver as driver_module
        monkeypatch.setattr(settings, "VERIFY_OUTBOX_MAX_ATTEMPTS", 1)
        async def _always_fail(self, session, **kwargs):
            raise RuntimeError("induced partner failure")
        monkeypatch.setattr(driver_module.InProcessConformanceDriver, "send_partner_message", _always_fail)
        async with _client() as client:
            _, auth, _ = await _register(client, "DeadLetter")
            opened = await _open_run(client, auth)
            result = await _finalize(client, auth, opened["run_id"])
            assert result["verifier_fault"] is True and result["complete"] is False
            report = await _client_get_json(client, result["report_slug"])
            for check in ("inbox_consumption", "nonce_round_trip", "duplicate_delivery_suppression"):
                assert report["results"][check]["state"] == "NOT_OBSERVED"
                assert report["results"][check]["evidence"]["reason"] == "verifier_fault"
            assert report["failed"] == 0
    _run(_case())


def test_verifier_fault_refund_is_idempotent(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        from app.core.config import settings
        from app.services.verification import driver as driver_module
        monkeypatch.setattr(settings, "VERIFY_OUTBOX_MAX_ATTEMPTS", 1)
        async def _always_fail(self, session, **kwargs):
            raise RuntimeError("induced partner failure")
        monkeypatch.setattr(driver_module.InProcessConformanceDriver, "send_partner_message", _always_fail)
        async with _client() as client:
            _, auth, _ = await _register(client, "RefundOnce")
            opened = await _open_run(client, auth)
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.rate_limit_bucket import RateLimitBucket
            from app.models.verification import VerificationRun
            async with AsyncSessionLocal() as s:
                run = (await s.execute(select(VerificationRun).where(VerificationRun.id == uuid.UUID(opened["run_id"])))).scalar_one()
                keys = [w["key"] for w in run.run_metadata["budget_buckets"]]
                before = {
                    b.bucket_key: b.count
                    for b in (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key.in_(keys)))).scalars()
                }
            # Concurrent finalize, then a third sequential one: exactly ONE refund.
            r1, r2 = await asyncio.gather(
                client.post(f"/verify/{opened['run_id']}/finalize", headers=auth),
                client.post(f"/verify/{opened['run_id']}/finalize", headers=auth),
            )
            assert r1.status_code == 200 and r2.status_code == 200
            assert (await client.post(f"/verify/{opened['run_id']}/finalize", headers=auth)).status_code == 200
            async with AsyncSessionLocal() as s:
                after = {
                    b.bucket_key: b.count
                    for b in (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key.in_(keys)))).scalars()
                }
                run = (await s.execute(select(VerificationRun).where(VerificationRun.id == uuid.UUID(opened["run_id"])))).scalar_one()
                assert run.budget_refunded_at is not None
            assert all(after[k] == before[k] - 1 for k in before), (before, after)
    _run(_case())


def test_refund_never_touches_a_newer_bucket_window():
    async def _case():
        # Service-level check of the window guard (labeled: direct service
        # call — window rollover is not reachable as scored public behavior).
        from datetime import timedelta as _td
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.rate_limit_bucket import RateLimitBucket
        from app.services.abuse_control import refund_verification_limit
        from app.utils.time import utc_now
        bucket_key = f"verify:test:window-guard:{uuid.uuid4().hex}"
        async with AsyncSessionLocal() as s:
            bucket = RateLimitBucket(
                bucket_key=bucket_key, count=5,
                window_ends_at=utc_now() + _td(hours=1),
            )
            s.add(bucket)
            await s.commit()
            stale = (bucket.window_ends_at - _td(days=1)).isoformat()
            await refund_verification_limit(s, [{"key": bucket_key, "window_ends_at": stale}])
            await s.commit()
            row = (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key == bucket_key))).scalar_one()
            assert row.count == 5  # stale-window refund must not touch the newer window
            current = row.window_ends_at.isoformat()
            await refund_verification_limit(s, [{"key": bucket_key, "window_ends_at": current}])
            await s.commit()
            row = (await s.execute(select(RateLimitBucket).where(RateLimitBucket.bucket_key == bucket_key))).scalar_one()
            assert row.count == 4  # matching window is decremented
    _run(_case())


def test_losing_concurrent_open_is_not_charged():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "RaceOpen")
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import func, select
            from app.models.rate_limit_bucket import RateLimitBucket
            async with AsyncSessionLocal() as s:
                before = (
                    await s.execute(
                        select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                            RateLimitBucket.bucket_key.like("verify:%")
                        )
                    )
                ).scalar_one()
            r1, r2 = await asyncio.gather(
                client.post("/verify", headers=auth, json={}),
                client.post("/verify", headers=auth, json={}),
            )
            assert sorted([r1.status_code, r2.status_code]) == [201, 409]
            async with AsyncSessionLocal() as s:
                after = (
                    await s.execute(
                        select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                            RateLimitBucket.bucket_key.like("verify:%")
                        )
                    )
                ).scalar_one()
            # Exactly ONE open consumed budget (one IP + one global increment),
            # regardless of whether the loser hit the pre-check or the
            # unique-index race path.
            assert after == before + 2, (before, after)
    _run(_case())


def test_failure_after_budget_consumption_commits_nothing_and_compensates(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        from app.services.verification import runs as runs_module

        async def _boom(*args, **kwargs):
            raise RuntimeError("induced failure immediately after budget consumption")

        monkeypatch.setattr(runs_module, "enqueue", _boom)
        async with _client(raise_app_exceptions=False) as client:
            agent_id, auth, _ = await _register(client, "PostBudgetCrash")
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import func, select
            from app.models.rate_limit_bucket import RateLimitBucket
            from app.models.verification import VerificationRun
            async with AsyncSessionLocal() as s:
                before = (
                    await s.execute(
                        select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                            RateLimitBucket.bucket_key.like("verify:%")
                        )
                    )
                ).scalar_one()
            resp = await client.post("/verify", headers=auth, json={})
            assert resp.status_code == 500
            async with AsyncSessionLocal() as s:
                runs = (
                    await s.execute(
                        select(VerificationRun).where(VerificationRun.agent_id == uuid.UUID(agent_id))
                    )
                ).scalars().all()
                # The provisional run was never committed — and therefore no
                # FK'd outbox action referencing it can exist either.
                assert runs == []
                after = (
                    await s.execute(
                        select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                            RateLimitBucket.bucket_key.like("verify:%")
                        )
                    )
                ).scalar_one()
            # Best-effort compensation refunded the already-committed budgets.
            assert after == before, (before, after)
    _run(_case())


def test_denied_budget_retains_counter_but_never_a_run(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        from app.core.config import settings
        monkeypatch.setattr(settings, "VERIFY_RUNS_PER_IP_PER_DAY", 0)
        async with _client() as client:
            agent_id, auth, _ = await _register(client, "Denied")
            resp = await client.post("/verify", headers=auth, json={})
            assert resp.status_code == 429
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import func, select
            from app.models.rate_limit_bucket import RateLimitBucket
            from app.models.verification import VerificationRun
            async with AsyncSessionLocal() as s:
                runs = (
                    await s.execute(
                        select(VerificationRun).where(VerificationRun.agent_id == uuid.UUID(agent_id))
                    )
                ).scalars().all()
                assert runs == []  # never committed, never retained, never visible
                denied_ip = (
                    await s.execute(
                        select(func.coalesce(func.sum(RateLimitBucket.count), 0)).where(
                            RateLimitBucket.bucket_key.like("verify:ip:%")
                        )
                    )
                ).scalar_one()
                assert denied_ip >= 1  # the denied attempt persisted independently
    _run(_case())


def test_outbox_crash_after_claim_recovers_via_lease(monkeypatch):
    async def _case():
        await _bootstrap_partner()
        from app.services.verification import driver as driver_module
        original = driver_module.InProcessConformanceDriver.send_partner_message
        calls = {"n": 0}
        async def _fail_once(self, session, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("induced first-attempt failure")
            return await original(self, session, **kwargs)
        monkeypatch.setattr(driver_module.InProcessConformanceDriver, "send_partner_message", _fail_once)
        async with _client() as client:
            _, auth, _ = await _register(client, "Lease")
            opened = await _open_run(client, auth)
            # Infrastructure manipulation (labeled): simulate a crashed claimer
            # by expiring the retry delay and lease on the failed action.
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.verification import VerificationOutboxAction
            from app.utils.time import utc_now
            async with AsyncSessionLocal() as s:
                pending = (
                    await s.execute(
                        select(VerificationOutboxAction).where(
                            VerificationOutboxAction.run_id == uuid.UUID(opened["run_id"]),
                            VerificationOutboxAction.completed_at.is_(None),
                        )
                    )
                ).scalars().all()
                assert pending, "expected a failed pending action"
                for action in pending:
                    action.available_at = utc_now() - timedelta(seconds=1)
                    action.claim_expires_at = utc_now() - timedelta(seconds=1)
                await s.commit()
            # Any run touch drains and retries:
            assert (await client.get(f"/verify/{opened['run_id']}", headers=auth)).status_code == 200
            async with AsyncSessionLocal() as s:
                remaining = (
                    await s.execute(
                        select(VerificationOutboxAction).where(
                            VerificationOutboxAction.run_id == uuid.UUID(opened["run_id"]),
                            VerificationOutboxAction.completed_at.is_(None),
                            VerificationOutboxAction.dead_lettered.is_(False),
                        )
                    )
                ).scalars().all()
                assert len(remaining) < len(pending)
    _run(_case())


def test_concurrent_finalize_yields_one_report():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Concurrent")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            r1, r2 = await asyncio.gather(
                client.post(f"/verify/{run_id}/finalize", headers=auth),
                client.post(f"/verify/{run_id}/finalize", headers=auth),
            )
            assert r1.status_code == 200 and r2.status_code == 200
            assert r1.json()["report_slug"] == r2.json()["report_slug"]
    _run(_case())


def test_second_open_run_conflicts_and_reserved_name_rejected():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Conflict")
            await _open_run(client, auth)
            resp = await client.post("/verify", headers=auth, json={})
            assert resp.status_code == 409
            resp = await client.post(
                "/register", json={"name": "InteropConformanceAgent", "description": "impostor"}
            )
            assert resp.status_code == 409
    _run(_case())


def test_bootstrap_idempotent_and_fails_safely_on_conflict():
    async def _case():
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import func, select
        from app.models.agent import Agent
        from app.services.system_agents import (
            CONFORMANCE_AGENT_ID, CONFORMANCE_AGENT_NAME, ensure_conformance_agent,
        )
        await _bootstrap_partner()
        await _bootstrap_partner()  # idempotent
        async with AsyncSessionLocal() as s:
            count = (
                await s.execute(select(func.count(Agent.id)).where(Agent.name == CONFORMANCE_AGENT_NAME))
            ).scalar_one()
            assert count == 1
        # Infrastructure manipulation (labeled): plant a conflicting row.
        async with AsyncSessionLocal() as s:
            (await s.execute(select(Agent).where(Agent.id == CONFORMANCE_AGENT_ID))).scalar_one().name = "Renamed"
            await s.commit()
        with pytest.raises(RuntimeError):
            async with AsyncSessionLocal() as s:
                await ensure_conformance_agent(s)
        async with AsyncSessionLocal() as s:  # restore
            (await s.execute(select(Agent).where(Agent.id == CONFORMANCE_AGENT_ID))).scalar_one().name = CONFORMANCE_AGENT_NAME
            await s.commit()
    _run(_case())


def test_listing_lifecycle_admin_takedown_and_neutral_page():
    async def _case():
        await _bootstrap_partner()
        from app.core.config import settings
        async with _client() as client:
            _, auth, _ = await _register(client, "Listing")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            slug = (await _finalize(client, auth, run_id))["report_slug"]

            index = (await client.get("/reports")).json()
            assert slug not in [i["slug"] for i in index["items"]]  # unlisted by default
            assert (await client.put(f"/reports/{slug}/listing", headers=auth)).status_code == 200
            assert slug in [i["slug"] for i in (await client.get("/reports")).json()["items"]]
            assert (await client.delete(f"/reports/{slug}/listing", headers=auth)).status_code == 200
            assert slug not in [i["slug"] for i in (await client.get("/reports")).json()["items"]]

            # Foreign agent cannot manage another owner's listing.
            _, other_auth, _ = await _register(client, "NotOwner")
            assert (await client.put(f"/reports/{slug}/listing", headers=other_auth)).status_code == 404

            admin = {"X-Admin-Key": settings.ADMIN_API_KEY}
            assert (await client.post(f"/admin/reports/{slug}/disable", headers=admin)).status_code == 200
            page = await client.get(f"/reports/{slug}")
            assert page.status_code == 410 and "removed by the operator" in page.text
            assert (await client.get(f"/reports/{slug}.json")).status_code == 410
            assert (await client.get(f"/reports/{slug}/badge.json")).status_code == 410
    _run(_case())


def test_raw_evidence_never_appears_in_public_outputs():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Projection")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            slug = (await _finalize(client, auth, run_id))["report_slug"]
            body = (await client.get(f"/reports/{slug}.json")).text
            page = (await client.get(f"/reports/{slug}")).text
            for leaked in ("served_partner_ids", "boot_id", "after_id", "budget_buckets"):
                assert leaked not in body, leaked
                assert leaked not in page, leaked
    _run(_case())


def test_stats_exclude_conformance_traffic_in_both_directions():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            baseline = (await client.get("/stats")).json()
            _, auth, _ = await _register(client, "Stats")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            await _finalize(client, auth, run_id)
            after_run = (await client.get("/stats")).json()
            # A full verification flow — partner→client AND client→partner
            # messages — must not move the public message counter at all.
            # (Behavioral assertion against an independent baseline, not a
            # re-implementation of the endpoint's own filter.)
            assert after_run["messages_total"] == baseline["messages_total"]
            assert after_run["agents_total"] == baseline["agents_total"] + 1
            # One organic broadcast from a normal agent DOES count.
            resp = await client.post(
                "/message/send", headers=auth, json={"subject": "organic", "content": "hello world"}
            )
            assert resp.status_code == 200
            final = (await client.get("/stats")).json()
            assert final["messages_total"] == baseline["messages_total"] + 1
    _run(_case())


def test_boot_change_degrades_timing_check():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Boot")
            run_id = (await _drive_compliant(client, auth, await _open_run(client, auth)))["run_id"]
            # Infrastructure manipulation (labeled): simulate a restart.
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select
            from app.models.verification import VerificationRun
            from app.services.verification.observations import note_boot_id
            async with AsyncSessionLocal() as s:
                run = (await s.execute(select(VerificationRun).where(VerificationRun.id == uuid.UUID(run_id)))).scalar_one()
                note_boot_id(run, "simulated-second-boot")
                await s.commit()
            result = await _finalize(client, auth, run_id)
            report = await _client_get_json(client, result["report_slug"])
            assert report["results"]["polling_discipline"]["state"] == "NOT_OBSERVED"
            assert report["results"]["polling_discipline"]["evidence"]["reason"] == "verifier_restart"
    _run(_case())


def test_observation_purge_deletes_only_aged_rows():
    async def _case():
        await _bootstrap_partner()
        async with _client() as client:
            _, auth, _ = await _register(client, "Purge")
            opened = await _open_run(client, auth)
            assert (await client.get("/message/inbox", headers=auth, params={"after_id": 0})).status_code == 200
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.verification import VerificationObservation
        from app.services.verification.observations import purge_expired_observations
        from app.utils.time import utc_now
        async with AsyncSessionLocal() as s:
            # Infrastructure manipulation (labeled): age one synthetic row.
            aged = VerificationObservation(
                run_id=uuid.UUID(opened["run_id"]), boot_id="old", kind="discovery", payload={},
            )
            aged.created_at = utc_now() - timedelta(days=400)
            s.add(aged)
            await s.commit()
            live_before = (
                await s.execute(select(VerificationObservation.id).where(VerificationObservation.boot_id != "old"))
            ).scalars().all()
            deleted = await purge_expired_observations(s)
            assert deleted == 1
            live_after = (
                await s.execute(select(VerificationObservation.id))
            ).scalars().all()
            assert set(live_before) == set(live_after)
    _run(_case())
