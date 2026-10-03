"""The same durable execution contract runs against SQLite and real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
import pytest
from fastapi import HTTPException

from app import create_app
from engine import DOCUMENTS
from postgres import PostgreSQLStore
from storage import SQLiteStore


@pytest.fixture(params=["sqlite", "postgres"])
def durable(request, tmp_path):
    if request.param == "sqlite":
        path = tmp_path / "durable.sqlite3"
        yield lambda: SQLiteStore(path, DOCUMENTS)
        return
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL absent; real PostgreSQL runs in CI")
    schema = "test_" + uuid4().hex
    with psycopg.connect(url) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield lambda: PostgreSQLStore(url, DOCUMENTS, schema)
    finally:
        with psycopg.connect(url) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def queued(identity="run"):
    return {
        "run_id": identity,
        "status": "queued",
        "created_at": "2026",
        "usage_complete": True,
        "usage": {"total_tokens": 22},
        "trace": [{"status": "read"}],
    }


def expire(store, identity):
    with store.transaction() as db:
        store.sql(db, "UPDATE runs SET lease_until=0 WHERE id=?", (identity,))


def test_restart_queue_live_lease_expiry_and_fencing(durable):
    store = durable()
    store.save_run("alice", queued())
    restart = durable()
    assert restart.get_run("alice", "run")["status"] == "queued"
    run, lease = store.claim_run("alice", "run")
    assert lease
    assert restart.get_run("alice", "run")["status"] == "running"
    assert restart.claim_run("alice", "run")[1] is None
    assert restart.claim_run("bob", "run") == (None, None)
    run["read_documents"] = [store.documents()[0]]
    assert store.checkpoint_run("alice", run, lease)
    expire(restart, "run")
    recovered = durable().get_run("alice", "run")
    assert recovered["status"] == "interrupted"
    assert recovered["failure_reason"] == "lease_expired"
    assert recovered["usage_complete"] is False
    assert recovered["read_documents"] == run["read_documents"]
    assert recovered["usage"] == run["usage"]
    run.update(status="completed", result={"answer": "late"})
    assert not store.checkpoint_run("alice", run, lease, finished=True)
    assert restart.get_run("alice", "run")["status"] == "interrupted"
    assert restart.claim_run("alice", "run")[1] is None


def test_cancel_fences_completion_and_delete_until_worker_finishes(durable):
    store, other = durable(), durable()
    store.save_run("alice", queued())
    run, lease = store.claim_run("alice", "run")
    assert other.cancel_run("bob", "run") is None
    assert other.cancel_run("alice", "run")["status"] == "cancelled"
    assert not other.delete_run("alice", "run")
    run.update(status="completed", result={"answer": "late"})
    assert store.checkpoint_run("alice", run, lease, finished=True)
    saved = other.get_run("alice", "run")
    assert saved["status"] == "cancelled"
    assert saved["result"] is None
    assert saved["failure_reason"] == "user_cancelled"
    assert other.delete_run("alice", "run")
    assert not store.checkpoint_run("alice", run, lease, finished=True)


def test_shared_capacity_and_model_budget(durable):
    store, other = durable(), durable()
    for index in range(5):
        store.save_run("alice", queued(str(index)))
    for index in range(4):
        assert store.claim_run("alice", str(index))[1]
    with pytest.raises(HTTPException) as error:
        other.claim_run("alice", "4")
    assert error.value.status_code == 429
    expire(store, "0")
    assert other.claim_run("alice", "4")[1]
    for _ in range(10):
        store.charge_model()
    with pytest.raises(HTTPException) as error:
        other.charge_model()
    assert error.value.status_code == 429


def test_postgres_parallel_claim_and_version_allocation(durable):
    store = durable()
    if not store.postgres:
        pytest.skip("threaded cross-connection PostgreSQL test")
    store.save_run("alice", queued())
    with ThreadPoolExecutor(max_workers=8) as workers:
        claims = list(workers.map(lambda _: durable().claim_run("alice", "run"), range(8)))
    assert sum(bool(token) for _, token in claims) == 1
    with ThreadPoolExecutor(max_workers=4) as workers:
        versions = list(
            workers.map(
                lambda _: durable().put_document({**DOCUMENTS[0], "body": "revision"}), range(4)
            )
        )
    assert sorted(doc["version"] for doc in versions) == [2, 3, 4, 5]
    assert len(durable().documents()) == 5


async def test_api_create_cold_start_execute_repeat_and_identity(durable, monkeypatch):
    monkeypatch.setenv(
        "WORKSPACE_IDENTITIES", json.dumps({"alice": "alice-test", "bob": "bob-test"})
    )
    headers = {"Authorization": "Bearer alice-test"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(storage_factory=durable)),
        base_url="http://test",
    ) as first:
        created = (await first.post("/api/runs", headers=headers, json={"prompt": "API"})).json()
        assert created["status"] == "queued"
        identity = created["run_id"]
    # Entire app recreated between create and execute; nothing depends on memory tasks.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(storage_factory=durable)),
        base_url="http://test",
    ) as restarted:
        assert (
            await restarted.post(
                f"/api/runs/{identity}/execute", headers={"Authorization": "Bearer bob-test"}
            )
        ).status_code == 404
        response = await restarted.post(f"/api/runs/{identity}/execute", headers=headers)
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"
        assert run["model_calls"] == 0
        assert (
            run["read_documents"][0]["content_hash"]
            == created["document_snapshot"][0]["content_hash"]
        )
        assert (
            await restarted.post(f"/api/runs/{identity}/execute", headers=headers)
        ).json() == run
        assert (
            await restarted.get("/api/runs", headers={"Authorization": "Bearer bob-test"})
        ).json() == {"runs": []}


@pytest.mark.parametrize("stop", ["cancel", "timeout", "disconnect"])
async def test_two_instances_duplicate_execution_and_stop_audit(durable, monkeypatch, stop):
    import asyncio
    import workspace
    from fastapi import Request

    monkeypatch.setenv("WORKSPACE_IDENTITIES", '{"alice":"alice-test"}')
    monkeypatch.setenv("PLAYGROUND_ACCESS_TOKEN", "provider-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "mock-only")
    headers = {"Authorization": "Bearer alice-test", "X-Playground-Token": "provider-test"}
    started = asyncio.Event()
    calls, stopped = 0, False

    async def mock_generate(prompt, charge, client_factory, research):
        nonlocal calls, stopped
        calls += 1
        charge()
        research.model_calls = 1
        research.pending_model_call = True
        research.tool("document_search", '{"query":"API"}')
        research.tool("document_read", '{"document_ids":["api"]}')
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped = True

    monkeypatch.setattr(workspace, "generate", mock_generate)
    if stop == "timeout":
        monkeypatch.setattr(workspace, "EXECUTION_SECONDS", 0.15)
    if stop == "disconnect":

        async def disconnected(_request):
            return started.is_set()

        monkeypatch.setattr(Request, "is_disconnected", disconnected)
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(storage_factory=durable)),
            base_url="http://test",
        ) as first,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(storage_factory=durable)),
            base_url="http://test",
        ) as second,
    ):
        identity = (
            await first.post(
                "/api/runs", headers=headers, json={"prompt": "API", "mode": "deepseek"}
            )
        ).json()["run_id"]
        executing = asyncio.create_task(
            first.post(f"/api/runs/{identity}/execute", headers=headers)
        )
        await asyncio.wait_for(started.wait(), 3)
        if stop == "cancel":
            duplicate = await second.post(f"/api/runs/{identity}/execute", headers=headers)
            assert duplicate.status_code == 409
            assert duplicate.json()["error"] == "run_in_progress"
            cancelled = await second.post(f"/api/runs/{identity}/cancel", headers=headers)
            assert cancelled.json()["status"] == "cancelled"
        result = await asyncio.wait_for(executing, 3)
        assert result.status_code == 200
        run = result.json()
        assert run["status"] == "cancelled"
        assert (
            run["failure_reason"]
            == {
                "cancel": "user_cancelled",
                "timeout": "execution_timeout",
                "disconnect": "client_disconnected",
            }[stop]
        )
        assert run["read_documents"][0]["id"] == "api"
        assert run["model_calls"] == 1
        assert run["usage_complete"] is False
        assert stopped and calls == 1
        # Endpoint has returned: worker is already stopped, audit survives a new instance.
        assert durable().get_run("alice", identity) == run
        assert (await second.post(f"/api/runs/{identity}/execute", headers=headers)).json() == run
        assert calls == 1


def test_postgres_bootstrap_is_atomic_and_preserves_maintainer_versions(durable, monkeypatch):
    store = durable()
    if not store.postgres:
        pytest.skip("PostgreSQL bootstrap transaction test")
    original = store.documents()[0]
    revised = store.put_document(
        {**original, "body": "maintainer body", "custom": "preserve exactly"}
    )
    for _ in range(3):
        assert durable().documents()[0] == revised
    with store.transaction() as db:
        db.execute("DELETE FROM documents WHERE id <> 'api'")
    original_put = PostgreSQLStore._put
    count = 0

    def interrupted(self, db, document):
        nonlocal count
        result = original_put(self, db, document)
        count += 1
        if count == 2:
            raise RuntimeError("mock seed interruption")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(PostgreSQLStore, "_put", interrupted)
        with pytest.raises(RuntimeError, match="mock seed interruption"):
            durable()
    with store.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
    repaired = durable()
    assert len(repaired.documents()) == 5
    assert repaired.documents()[0] == revised
    with repaired.transaction() as db:
        history = [
            json.loads(row[0])
            for row in db.execute("SELECT payload FROM documents WHERE id='api' ORDER BY version")
        ]
    assert history == [original, revised]


def test_database_error_does_not_echo_connection_secrets(monkeypatch):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError("mock-secret-must-not-leak")

    monkeypatch.setattr(psycopg, "connect", fail)
    with pytest.raises(HTTPException) as error:
        PostgreSQLStore("unused", DOCUMENTS)
    assert error.value.status_code == 503
    assert error.value.detail == "database_unavailable"


async def test_real_http_disconnect_stops_worker_and_persists_audit(durable, monkeypatch):
    """Real socket disconnect, not a patched Request.is_disconnected."""
    import asyncio
    import socket
    import threading
    import uvicorn
    import workspace

    monkeypatch.setenv("WORKSPACE_IDENTITIES", '{"alice":"alice-test"}')
    monkeypatch.setenv("PLAYGROUND_ACCESS_TOKEN", "provider-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "mock-only")
    started, stopped = threading.Event(), threading.Event()

    async def mock_generate(prompt, charge, client_factory, research):
        research.model_calls = 1
        research.pending_model_call = True
        research.tool("document_search", '{"query":"API"}')
        research.tool("document_read", '{"document_ids":["api"]}')
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(workspace, "generate", mock_generate)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(storage_factory=durable),
            log_level="critical",
            access_log=False,
            timeout_graceful_shutdown=2,
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    headers = {"Authorization": "Bearer alice-test", "X-Playground-Token": "provider-test"}
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            created = (
                await client.post(
                    "/api/runs", headers=headers, json={"prompt": "API", "mode": "deepseek"}
                )
            ).json()
            identity = created["run_id"]
            executing = asyncio.create_task(
                client.post(f"/api/runs/{identity}/execute", headers=headers)
            )
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            executing.cancel()
            await asyncio.gather(executing, return_exceptions=True)
            for _ in range(30):
                saved = (await client.get(f"/api/runs/{identity}", headers=headers)).json()
                if saved["status"] != "running":
                    break
                await asyncio.sleep(0.1)
            assert saved["status"] == "cancelled"
            assert saved["failure_reason"] == "client_disconnected"
            assert stopped.is_set()
            assert saved["usage_complete"] is False
            assert saved["read_documents"][0]["id"] == "api"
            assert durable().get_run("alice", identity) == saved
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 4)
        sock.close()
    assert not thread.is_alive()
