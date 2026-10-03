"""Versioned local storage. Replace Store through create_app's storage factory."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


def now():
    return datetime.now(timezone.utc).isoformat()


class Store(Protocol):
    def documents(self) -> list[dict]: ...
    def put_document(self, document: dict) -> dict: ...
    def save_run(self, owner: str, run: dict) -> None: ...
    def runs(self, owner: str) -> list[dict]: ...
    def get_run(self, owner: str, run_id: str) -> dict | None: ...
    def delete_run(self, owner: str, run_id: str) -> bool: ...


class SQLiteStore:
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
        if not self.documents():
            for doc in seeds:
                self.put_document(doc)
        # A single worker owns this store. Restart never silently resumes paid calls.
        for identity, owner, payload in self.db.execute(
            "SELECT id, owner, payload FROM runs"
        ).fetchall():
            run = json.loads(payload)
            if run["status"] in {"queued", "running"}:
                run.update(
                    status="interrupted", failure_reason="process_restarted", updated_at=now()
                )
                self.save_run(owner, run)
        self.db.commit()

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

    def save_run(self, owner, run):
        self.db.execute(
            "INSERT OR REPLACE INTO runs VALUES(?,?,?)", (run["run_id"], owner, json.dumps(run))
        )
        self.db.commit()

    def runs(self, owner):
        return [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT payload FROM runs WHERE owner=? ORDER BY rowid DESC LIMIT 100", (owner,)
            )
        ]

    def get_run(self, owner, run_id):
        row = self.db.execute(
            "SELECT payload FROM runs WHERE id=? AND owner=?", (run_id, owner)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def delete_run(self, owner, run_id):
        cursor = self.db.execute("DELETE FROM runs WHERE id=? AND owner=?", (run_id, owner))
        self.db.commit()
        return bool(cursor.rowcount)
