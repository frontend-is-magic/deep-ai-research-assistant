"""Private single-worker workbench. No network ingestion or arbitrary execution."""

import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import os
import re
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import Header, HTTPException, Response
from pydantic import Field

from engine import DOCUMENTS, Research, StrictModel, demo, generate
from storage import SQLiteStore, now

ALLOWED_HOSTS = {
    "fastapi.tiangolo.com",
    "modelcontextprotocol.io",
    "developers.openai.com",
    "api-docs.deepseek.com",
}


class DocumentInput(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,80}$")
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=1000)
    body: str = Field(min_length=1, max_length=6000)
    keywords: list[str] = Field(min_length=1, max_length=20)
    kind: str = Field(pattern=r"^public-manual$")
    acquisition: str = Field(pattern=r"^manual-transcription$")


def install_workspace(api, question_model, charge, client_factory, storage_factory=None):
    store = None
    tasks = {}

    @api.middleware("http")
    async def private_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/runs", "/api/library")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @asynccontextmanager
    async def lifespan(_api):
        yield
        pending = list(tasks.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    api.router.lifespan_context = lifespan

    def storage():
        nonlocal store
        if store is None:
            if os.getenv("VERCEL") and not storage_factory:
                raise HTTPException(503, "durable_storage_required")
            store = (
                storage_factory
                or (
                    lambda: SQLiteStore(
                        os.getenv("RESEARCH_DB_PATH", "data/research.sqlite3"), DOCUMENTS
                    )
                )
            )()
        return store

    async def identity(authorization: str | None = Header(None)):
        # JSON map is injected by the host; each distinct token maps to a stable user ID.
        try:
            identities = json.loads(os.getenv("WORKSPACE_IDENTITIES", "{}"))
        except ValueError:
            raise HTTPException(503, "identity_not_configured") from None
        if not isinstance(identities, dict):
            raise HTTPException(503, "identity_not_configured")
        token = (
            authorization.removeprefix("Bearer ")
            if authorization and authorization.startswith("Bearer ")
            else ""
        )
        for owner, expected in identities.items():
            if (
                isinstance(expected, str)
                and expected
                and token
                and hmac.compare_digest(token.encode(), expected.encode())
            ):
                return owner
        raise HTTPException(401, "workspace_access_required")

    def owned(owner, run_id):
        run = storage().get_run(owner, run_id)
        if run is None:
            raise HTTPException(404, "run_not_found")
        return run

    def checkpoint(owner, run, research):
        run.update(
            updated_at=now(),
            read_documents=[research.by_id[key] for key in sorted(research.read_ids)],
            trace=research.trace,
            model_calls=research.model_calls,
            tool_calls=research.tool_calls,
            usage=research.usage or None,
            usage_complete=research.usage_complete and not research.pending_model_call,
        )
        storage().save_run(owner, run)

    async def execute(owner, run, research):
        run.update(status="running", updated_at=now())
        checkpoint(owner, run, research)
        try:
            result = (
                demo(run["prompt"], research=research)
                if run["mode"] == "demo"
                else await generate(run["prompt"], charge, client_factory, research)
            )
            result["run_id"] = run["run_id"]
            run.update(status="completed", result=result)
        except asyncio.CancelledError:
            run.update(status="cancelled", failure_reason="user_cancelled")
        except HTTPException as exc:
            run.update(status="failed", failure_reason=exc.detail)
        except Exception:
            run.update(status="failed", failure_reason="internal_error")
        finally:
            if run["status"] != "completed" and research.model_calls:
                research.usage_complete = False
            checkpoint(owner, run, research)
            tasks.pop(run["run_id"], None)

    from fastapi import Depends

    @api.get("/api/library")
    async def library(owner=Depends(identity)):
        return {
            "documents": [
                {key: value for key, value in doc.items() if key != "body"}
                for doc in storage().documents()
            ]
        }

    @api.post("/api/library", status_code=201)
    async def ingest(
        body: DocumentInput, owner=Depends(identity), x_maintainer_token: str | None = Header(None)
    ):
        expected = os.getenv("MAINTAINER_TOKEN", "")
        if (
            not expected
            or not x_maintainer_token
            or not hmac.compare_digest(expected.encode(), x_maintainer_token.encode())
        ):
            raise HTTPException(403, "maintainer_required")
        try:
            url = urlsplit(body.url)
            port = url.port
        except ValueError:
            raise HTTPException(422, "source_not_allowed") from None
        if (
            url.scheme != "https"
            or url.hostname not in ALLOWED_HOSTS
            or url.username
            or url.password
            or port not in {None, 443}
        ):
            raise HTTPException(422, "source_not_allowed")
        if any(not word.strip() or len(word) > 80 for word in body.keywords):
            raise HTTPException(422, "invalid_keywords")
        return storage().put_document(body.model_dump())

    @api.post("/api/runs", status_code=202)
    async def start(
        body: question_model, owner=Depends(identity), x_playground_token: str | None = Header(None)
    ):
        if not body.prompt.strip():
            raise HTTPException(422, "invalid_input")
        if body.mode == "deepseek":
            expected = os.getenv("PLAYGROUND_ACCESS_TOKEN", "")
            if (
                not expected
                or not x_playground_token
                or not hmac.compare_digest(expected.encode(), x_playground_token.encode())
            ):
                raise HTTPException(401, "access_required")
            if not os.getenv("DEEPSEEK_API_KEY"):
                raise HTTPException(503, "provider_not_configured")
        if sum(not task.done() for task in tasks.values()) >= 4:
            raise HTTPException(429, "run_capacity")
        research = Research(storage().documents())
        run = {
            "run_id": str(uuid4()),
            "prompt": body.prompt,
            "mode": body.mode,
            "status": "queued",
            "created_at": now(),
            "updated_at": now(),
            "failure_reason": None,
            "result": None,
            "read_documents": [],
            "trace": [],
            "model_calls": 0,
            "tool_calls": 0,
            "usage": None,
            "usage_complete": True,
        }
        storage().save_run(owner, run)
        research.on_progress = lambda: checkpoint(owner, run, research)
        tasks[run["run_id"]] = asyncio.create_task(execute(owner, run, research))
        return run

    @api.get("/api/runs")
    async def listing(owner=Depends(identity)):
        return {
            "runs": [
                {
                    key: run[key]
                    for key in (
                        "run_id",
                        "prompt",
                        "mode",
                        "status",
                        "created_at",
                        "updated_at",
                        "failure_reason",
                    )
                }
                for run in storage().runs(owner)
            ]
        }

    @api.get("/api/runs/{run_id}")
    async def detail(run_id: str, owner=Depends(identity)):
        return owned(owner, run_id)

    @api.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str, owner=Depends(identity)):
        run = owned(owner, run_id)
        task = tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # A task cancelled before entering execute still needs a terminal record.
            run = owned(owner, run_id)
            if run["status"] in {"queued", "running"}:
                run.update(status="cancelled", failure_reason="user_cancelled", updated_at=now())
                storage().save_run(owner, run)
                tasks.pop(run_id, None)
        return owned(owner, run_id)

    @api.delete("/api/runs/{run_id}", status_code=204)
    async def delete(run_id: str, owner=Depends(identity)):
        run = owned(owner, run_id)
        if run["status"] in {"queued", "running"}:
            raise HTTPException(409, "cancel_before_delete")
        storage().delete_run(owner, run_id)
        return Response(status_code=204)

    @api.get("/api/runs/{run_id}/export")
    async def export(run_id: str, format: str = "json", owner=Depends(identity)):
        run = owned(owner, run_id)
        if format == "json":
            payload = json.dumps(run, ensure_ascii=False, indent=2)
            media = "application/json"
        elif format == "markdown":
            result = run.get("result") or {}
            payload = f"# 技术研究报告\n\n任务：{run['prompt']}\n\nrun_id：{run_id}\n\n状态：{run['status']}\n\n{result.get('answer', run.get('failure_reason') or '')}\n\n## 实际读取资料版本\n\n"
            for doc in run["read_documents"]:
                payload += f"- {doc['title']} · v{doc['version']} · {doc['content_hash']} · {doc.get('url') or '合成练习'}\n"
            payload += "\n## 引用摘录\n\n" + "\n\n".join(
                item["quote"] for item in result.get("citations", [])
            )
            payload += "\n\n## 操作与用量\n\n" + json.dumps(
                {
                    key: run[key]
                    for key in ("trace", "model_calls", "tool_calls", "usage", "usage_complete")
                },
                ensure_ascii=False,
                indent=2,
            )
            media = "text/markdown"
        else:
            raise HTTPException(422, "invalid_export_format")
        safe_id = re.sub(r"[^a-zA-Z0-9-]", "", run_id)
        return Response(
            payload,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="report-{safe_id}.{"md" if format == "markdown" else "json"}"',
                "Cache-Control": "no-store",
            },
        )
