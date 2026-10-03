"""Short, bounded transactions on independent connections (pooler compatible)."""

from contextlib import contextmanager
import hashlib
import json

import psycopg
from psycopg import sql
from fastapi import HTTPException

from durable import DurableRuns, now


class PostgreSQLStore(DurableRuns):
    postgres = True

    def __init__(self, url, seeds, schema="public"):
        self.url, self.schema = url, schema
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS documents(id TEXT,version INTEGER,payload TEXT NOT NULL,PRIMARY KEY(id,version))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,payload TEXT NOT NULL,lease_token TEXT,lease_until DOUBLE PRECISION,created_at TEXT NOT NULL DEFAULT '')"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS model_requests(requested_at DOUBLE PRECISION NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS runs_owner ON runs(owner,created_at DESC)")
            db.execute("INSERT INTO schema_migrations VALUES(1),(2) ON CONFLICT DO NOTHING")
            existing = {row[0] for row in db.execute("SELECT DISTINCT id FROM documents")}
            for doc in seeds:
                if doc["id"] not in existing:
                    self._put(db, doc)
                    existing.add(doc["id"])

    @contextmanager
    def transaction(self):
        try:
            with psycopg.connect(
                self.url,
                connect_timeout=3,
                options="-c statement_timeout=3000 -c lock_timeout=2000",
                prepare_threshold=None,
            ) as db:
                db.execute(
                    sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(self.schema))
                )
                # Serializes short transitions, migrations and version allocation across cold starts.
                db.execute("SELECT pg_advisory_xact_lock(73190421)")
                yield db
        except psycopg.Error:
            raise HTTPException(503, "database_unavailable") from None

    def documents(self):
        with self.transaction() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM documents d WHERE version=(SELECT MAX(version) FROM documents WHERE id=d.id) ORDER BY id"
                )
            ]

    def _put(self, db, document):
        doc = dict(document)
        version = db.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM documents WHERE id=%s", (doc["id"],)
        ).fetchone()[0]
        doc.update(
            version=version,
            recorded_at=now(),
            content_hash=hashlib.sha256(doc["body"].encode()).hexdigest(),
        )
        doc.setdefault("acquisition", "maintainer-authored")
        db.execute("INSERT INTO documents VALUES(%s,%s,%s)", (doc["id"], version, json.dumps(doc)))
        return doc

    def put_document(self, document):
        with self.transaction() as db:
            return self._put(db, document)
