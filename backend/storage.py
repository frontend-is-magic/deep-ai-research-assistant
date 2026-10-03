"""Versioned local storage. Replace Store through create_app's storage factory."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from contextlib import contextmanager


def now():
    return datetime.now(timezone.utc).isoformat()


from durable import DurableRuns  # noqa: E402


class Store(Protocol):
    def documents(self) -> list[dict]: ...
    def put_document(self, document: dict) -> dict: ...
    def save_run(self, owner: str, run: dict) -> None: ...
    def runs(self, owner: str) -> list[dict]: ...
    def get_run(self, owner: str, run_id: str) -> dict | None: ...
    def delete_run(self, owner: str, run_id: str) -> bool: ...
    def claim_run(self, owner: str, run_id: str) -> tuple: ...
    def checkpoint_run(self, owner: str, run: dict, token: str, finished=False) -> bool: ...
    def cancel_run(self, owner: str, run_id: str) -> dict | None: ...
    def charge_model(self) -> None: ...


class SQLiteStore(DurableRuns):
    postgres = False

    def __init__(self, path, seeds):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_migrations VALUES(1);
            CREATE TABLE IF NOT EXISTS documents(
                id TEXT, version INTEGER, payload TEXT NOT NULL, PRIMARY KEY(id, version));
            CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        # A partially committed first boot must be repairable on the next boot.
        # Existing IDs (including maintainer revisions) are never reseeded.
        existing_ids = {row[0] for row in self.db.execute("SELECT DISTINCT id FROM documents")}
        for doc in seeds:
            if doc["id"] not in existing_ids:
                self.put_document(doc)
                existing_ids.add(doc["id"])
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(runs)")}
        if "lease_token" not in columns:
            self.db.execute("ALTER TABLE runs ADD COLUMN lease_token TEXT")
            self.db.execute("ALTER TABLE runs ADD COLUMN lease_until REAL")
        if "created_at" not in columns:
            self.db.execute("ALTER TABLE runs ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
            self.db.execute(
                "UPDATE runs SET created_at=COALESCE(json_extract(payload, '$.created_at'), '')"
            )
        self.db.execute("CREATE TABLE IF NOT EXISTS model_requests(requested_at REAL NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO schema_migrations VALUES(2)")
        self.db.commit()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def documents(self):
        return [
            json.loads(row[0])
            for row in self.db.execute("""
            SELECT payload FROM documents d WHERE version=(
                SELECT MAX(version) FROM documents WHERE id=d.id) ORDER BY id
        """)
        ]

    def put_document(self, document):
        doc = dict(document)
        version = self.db.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM documents WHERE id=?", (doc["id"],)
        ).fetchone()[0]
        doc.update(
            version=version,
            recorded_at=now(),
            content_hash=hashlib.sha256(doc["body"].encode()).hexdigest(),
        )
        doc.setdefault("acquisition", "maintainer-authored")
        self.db.execute(
            "INSERT INTO documents VALUES(?,?,?)", (doc["id"], version, json.dumps(doc))
        )
        self.db.commit()
        return doc
