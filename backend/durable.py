"""Database-owned execution leases; no process-local task registry."""

import json
from uuid import uuid4

from fastapi import HTTPException

from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class DurableRuns:
    def sql(self, db, statement, values=()):
        return db.execute(statement.replace("?", "%s") if self.postgres else statement, values)

    def clock(self, db):
        query = (
            "SELECT EXTRACT(EPOCH FROM clock_timestamp())"
            if self.postgres
            else "SELECT unixepoch()"
        )
        return float(self.sql(db, query).fetchone()[0])

    def load(self, db, owner, run_id):
        row = self.sql(
            db,
            "SELECT payload, lease_token, lease_until FROM runs WHERE owner=? AND id=?",
            (owner, run_id),
        ).fetchone()
        if not row:
            return None
        run, token, until = json.loads(row[0]), row[1], row[2]
        if run["status"] == "running" and (until is None or until <= self.clock(db)):
            run.update(
                status="interrupted",
                failure_reason="lease_expired" if until is not None else "process_restarted",
                usage_complete=False,
                updated_at=now(),
            )
            self.write(db, owner, run, token, until)
        return run, token, until

    def write(self, db, owner, run, token=None, until=None):
        self.sql(
            db,
            "INSERT INTO runs(id,owner,payload,lease_token,lease_until,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, lease_token=excluded.lease_token, lease_until=excluded.lease_until, created_at=excluded.created_at WHERE runs.owner=excluded.owner",
            (run["run_id"], owner, json.dumps(run), token, until, run.get("created_at", "")),
        )

    def save_run(self, owner, run):
        # Creation and legacy fixture import only; active workers use fenced checkpoint.
        with self.transaction() as db:
            self.write(db, owner, run)

    def get_run(self, owner, run_id):
        with self.transaction() as db:
            value = self.load(db, owner, run_id)
            return value[0] if value else None

    def runs(self, owner):
        with self.transaction() as db:
            ids = self.sql(
                db,
                "SELECT id FROM runs WHERE owner=? ORDER BY created_at DESC, id DESC LIMIT 100",
                (owner,),
            ).fetchall()
            return sorted(
                [self.load(db, owner, row[0])[0] for row in ids],
                key=lambda run: run.get("created_at", ""),
                reverse=True,
            )

    def claim_run(self, owner, run_id):
        with self.transaction() as db:
            value = self.load(db, owner, run_id)
            if not value:
                return None, None
            run, token, until = value
            if run["status"] != "queued":
                return run, None
            count = self.sql(
                db,
                "SELECT COUNT(*) FROM runs WHERE lease_token IS NOT NULL AND lease_until>?",
                (self.clock(db),),
            ).fetchone()[0]
            if count >= 4:
                raise HTTPException(429, "run_capacity")
            token = str(uuid4())
            run.update(status="running", updated_at=now(), failure_reason=None)
            self.write(db, owner, run, token, self.clock(db) + 60)
            return run, token

    def checkpoint_run(self, owner, run, token, finished=False):
        with self.transaction() as db:
            value = self.load(db, owner, run["run_id"])
            if not value or value[1] != token:
                return False
            saved, _, until = value
            stopped = saved["status"] in {"cancelled", "interrupted"} or until <= self.clock(db)
            if stopped:
                run.update(
                    status=saved["status"], failure_reason=saved["failure_reason"], result=None
                )
            # Preserve a returned in-flight round's usage even after cancellation/expiry.
            # This is audit-only: it never authorizes another operation or resurrects a run.
            self.write(db, owner, run, None if finished else token, None if finished else until)
            return (finished and saved["status"] == "cancelled") or not stopped

    def execution_allowed(self, owner, run_id, token):
        with self.transaction() as db:
            value = self.load(db, owner, run_id)
            return bool(
                value
                and value[1] == token
                and value[0]["status"] == "running"
                and value[2] > self.clock(db)
            )

    def cancel_run(self, owner, run_id):
        with self.transaction() as db:
            value = self.load(db, owner, run_id)
            if not value:
                return None
            run, token, until = value
            if run["status"] in {"queued", "running"}:
                run.update(
                    status="cancelled",
                    result=None,
                    failure_reason="user_cancelled",
                    updated_at=now(),
                    usage_complete=False if token else run.get("usage_complete", True),
                )
                self.write(db, owner, run, token, until)
            return run

    def delete_run(self, owner, run_id):
        with self.transaction() as db:
            value = self.load(db, owner, run_id)
            if (
                not value
                or value[0]["status"] in {"queued", "running"}
                or (value[1] and value[2] > self.clock(db))
            ):
                return False
            return bool(
                self.sql(db, "DELETE FROM runs WHERE owner=? AND id=?", (owner, run_id)).rowcount
            )

    def charge_model(self):
        with self.transaction() as db:
            current = self.clock(db)
            self.sql(db, "DELETE FROM model_requests WHERE requested_at<?", (current - 60,))
            if self.sql(db, "SELECT COUNT(*) FROM model_requests").fetchone()[0] >= 10:
                raise HTTPException(429, "rate_limited")
            self.sql(db, "INSERT INTO model_requests VALUES(?)", (current,))
