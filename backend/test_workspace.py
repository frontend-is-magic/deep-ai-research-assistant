import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app
from engine import DOCUMENTS, Research, demo
from storage import SQLiteStore


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "WORKSPACE_IDENTITIES", json.dumps({"alice": "alice-test", "bob": "bob-test"})
    )
    monkeypatch.setenv("MAINTAINER_TOKEN", "maintainer-test")
    path = tmp_path / "workspace.sqlite3"

    def factory():
        return SQLiteStore(path, DOCUMENTS)

    return create_app(storage_factory=factory), factory


HEADERS = {"Authorization": "Bearer alice-test"}
OTHER = {"Authorization": "Bearer bob-test"}


async def completed(client, run_id):
    for _ in range(100):
        run = (await client.get(f"/api/runs/{run_id}", headers=HEADERS)).json()
        if run["status"] not in {"queued", "running"}:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError("run did not finish")


@pytest.mark.parametrize(
    "prompt,outcome",
    [
        ("API 超时", "complete"),
        ("zzzz unmatched", "insufficient_evidence"),
        ("取消计费冲突", "conflicting_evidence"),
    ],
)
async def test_private_reports_exports_restart(setup, prompt, outcome):
    api, factory = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        assert (await client.get("/api/runs")).status_code == 401
        created = await client.post("/api/runs", headers=HEADERS, json={"prompt": prompt})
        assert created.status_code == 202
        identity = created.json()["run_id"]
        run = await completed(client, identity)
        assert run["status"] == "completed"
        assert run["result"]["outcome"] == outcome
        assert run["result"]["run_id"] == identity
        assert len(run["read_documents"]) == len(run["result"]["sources"])
        for doc in run["read_documents"]:
            assert len(doc["content_hash"]) == 64
            assert doc["version"] == 1
        assert (await client.get(f"/api/runs/{identity}", headers=OTHER)).status_code == 404
        assert (await client.get("/api/runs", headers=OTHER)).json() == {"runs": []}
        for format in ("json", "markdown"):
            response = await client.get(
                f"/api/runs/{identity}/export?format={format}", headers=HEADERS
            )
            assert response.status_code == 200
            assert identity in response.text
            assert "alice-test" not in response.text
            assert response.headers["cache-control"] == "no-store"
    with TestClient(create_app(storage_factory=factory)) as restarted:
        assert restarted.get(f"/api/runs/{identity}", headers=HEADERS).json() == run
        assert restarted.delete(f"/api/runs/{identity}", headers=OTHER).status_code == 404
        assert restarted.delete(f"/api/runs/{identity}", headers=HEADERS).status_code == 204
        assert restarted.get(f"/api/runs/{identity}", headers=HEADERS).status_code == 404


async def test_library_permissions_and_snapshot(setup):
    api, factory = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        identity = (
            await client.post("/api/runs", headers=HEADERS, json={"prompt": "API 超时"})
        ).json()["run_id"]
        original = await completed(client, identity)
        doc = {
            "id": "api",
            "title": "公开人工摘录",
            "url": "https://fastapi.tiangolo.com/tutorial/",
            "body": "API 新版本说明。",
            "keywords": ["api"],
            "kind": "public-manual",
            "acquisition": "manual-transcription",
        }
        assert (await client.post("/api/library", headers=HEADERS, json=doc)).status_code == 403
        headers = {**HEADERS, "X-Maintainer-Token": "maintainer-test"}
        for url in (
            "http://127.0.0.1",
            "https://evil.example",
            "https://fastapi.tiangolo.com.evil.example",
            "https://user@fastapi.tiangolo.com",
            "https://fastapi.tiangolo.com:444",
        ):
            assert (
                await client.post("/api/library", headers=headers, json={**doc, "url": url})
            ).status_code == 422
        updated = (await client.post("/api/library", headers=headers, json=doc)).json()
        assert updated["version"] == 2
        saved = (await client.get(f"/api/runs/{identity}", headers=HEADERS)).json()
        assert saved == original
        next_id = (await client.post("/api/runs", headers=HEADERS, json={"prompt": "API"})).json()[
            "run_id"
        ]
        next_run = await completed(client, next_id)
        assert next_run["read_documents"][0]["version"] == 2
        assert next_run["result"]["citations"][0]["quote"] == doc["body"]


def test_restart_interruption_and_migration(setup):
    _, factory = setup
    store = factory()
    store.save_run("alice", {"run_id": "interrupted", "status": "running"})
    recovered = factory()
    run = recovered.get_run("alice", "interrupted")
    assert run["status"] == "interrupted"
    assert run["failure_reason"] == "process_restarted"
    assert recovered.db.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
    assert recovered.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 5


async def test_cancel_running_and_provider_failure(setup, monkeypatch):
    api, _ = setup
    monkeypatch.setenv("PLAYGROUND_ACCESS_TOKEN", "provider-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    import workspace
    from fastapi import HTTPException

    async def fail(*args):
        args[-1].model_calls = 1
        args[-1].usage_complete = False
        raise HTTPException(502, "provider_unavailable")

    async def slow(*args):
        args[-1].model_calls = 1
        args[-1].tool("document_search", '{"query":"API"}')
        args[-1].tool("document_read", '{"document_ids":["api"]}')
        await asyncio.sleep(30)

    monkeypatch.setattr(workspace, "generate", slow)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        run_id = (
            await client.post(
                "/api/runs",
                headers={**HEADERS, "X-Playground-Token": "provider-test"},
                json={"prompt": "API", "mode": "deepseek"},
            )
        ).json()["run_id"]
        run = (await client.post(f"/api/runs/{run_id}/cancel", headers=HEADERS)).json()
        assert run["status"] == "cancelled"
        assert run["failure_reason"] == "user_cancelled"
        assert run["usage_complete"] is False
        assert run["read_documents"][0]["id"] == "api"
        monkeypatch.setattr(workspace, "generate", fail)
        run_id = (
            await client.post(
                "/api/runs",
                headers={**HEADERS, "X-Playground-Token": "provider-test"},
                json={"prompt": "API", "mode": "deepseek"},
            )
        ).json()["run_id"]
        run = await completed(client, run_id)
        assert run["status"] == "failed"
        assert run["failure_reason"] == "provider_unavailable"
        assert run["model_calls"] == 1
        assert run["usage_complete"] is False


def test_frozen_validator_rejects_unread_and_fake():
    run = Research(DOCUMENTS)
    with pytest.raises(ValueError):
        run.result(
            {"answer": "invented", "citations": [{"document_id": "api", "quote": "API"}]}, "demo"
        )
    run.tool("document_search", '{"query":"API"}')
    run.tool("document_read", '{"document_ids":["api"]}')
    with pytest.raises(ValueError):
        run.result(
            {"answer": "invented", "citations": [{"document_id": "api", "quote": "fake quote"}]},
            "demo",
        )
    assert demo("API", DOCUMENTS)["outcome"] == "complete"


def test_vercel_fails_closed_without_durable_store(monkeypatch):
    monkeypatch.setenv("WORKSPACE_IDENTITIES", '{"alice":"alice-test"}')
    monkeypatch.setenv("VERCEL", "1")
    with TestClient(create_app()) as client:
        assert client.get("/api/runs", headers=HEADERS).status_code == 503


async def test_inflight_read_and_usage_checkpoint_survives_restart(setup, monkeypatch):
    _, factory = setup
    monkeypatch.setenv("PLAYGROUND_ACCESS_TOKEN", "provider-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    waiting = asyncio.Event()
    calls = 0

    async def provider(request):
        nonlocal calls
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        calls += 1
        if calls == 3:
            waiting.set()
            await asyncio.Event().wait()
        name = "document_search" if calls == 1 else "document_read"
        arguments = '{"query":"API"}' if calls == 1 else '{"document_ids":["api"]}'
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": f"call-{calls}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": arguments},
                                }
                            ]
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
            },
        )

    def client_factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(provider), **kwargs)

    api = create_app(client_factory=client_factory, storage_factory=factory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://test"
    ) as client:
        identity = (
            await client.post(
                "/api/runs",
                headers={**HEADERS, "X-Playground-Token": "provider-test"},
                json={"prompt": "API", "mode": "deepseek"},
            )
        ).json()["run_id"]
        await asyncio.wait_for(waiting.wait(), timeout=2)
        run = (await client.get(f"/api/runs/{identity}", headers=HEADERS)).json()
        assert run["status"] == "running"
        assert run["model_calls"] == 3
        assert run["tool_calls"] == 2
        assert run["read_documents"][0]["version"] == 1
        assert run["usage"] == {"prompt_tokens": 20, "completion_tokens": 2, "total_tokens": 22}
        assert run["usage_complete"] is False
        # Open storage as after a crash; pending model call is never replayed.
        recovered = factory().get_run("alice", identity)
        assert recovered["status"] == "interrupted"
        assert recovered["read_documents"] == run["read_documents"]
        assert recovered["usage"] == run["usage"]
        assert recovered["usage_complete"] is False
        await client.post(f"/api/runs/{identity}/cancel", headers=HEADERS)
