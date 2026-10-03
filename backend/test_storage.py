"""Interrupted bootstrap repairs missing IDs without replacing maintainer revisions."""

import pytest

from engine import DOCUMENTS
from storage import SQLiteStore


@pytest.mark.parametrize("committed_count", [1, 3])
def test_restart_repairs_seed_batch_after_committed_write(tmp_path, monkeypatch, committed_count):
    path = tmp_path / "interrupted.sqlite3"
    original = SQLiteStore.put_document
    connections = []
    count = 0

    def interrupted(store, document):
        nonlocal count
        connections.append(store.db)
        result = original(store, document)
        count += 1
        if count == committed_count:
            raise RuntimeError("simulated bootstrap interruption after commit")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, "put_document", interrupted)
        with pytest.raises(RuntimeError, match="simulated bootstrap"):
            SQLiteStore(path, DOCUMENTS)
        for connection in connections:
            connection.close()

    repaired = SQLiteStore(path, DOCUMENTS)
    assert {doc["id"] for doc in repaired.documents()} == {doc["id"] for doc in DOCUMENTS}
    assert repaired.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 5
    assert repaired.db.execute("SELECT version FROM schema_migrations").fetchall() == [(1,), (2,)]
    original_doc = next(doc for doc in repaired.documents() if doc["id"] == "api")
    updated = repaired.put_document({**original_doc, "body": "maintainer revision must survive"})
    repaired.db.close()
    restarted = SQLiteStore(path, DOCUMENTS)
    assert next(doc for doc in restarted.documents() if doc["id"] == "api") == updated
    assert restarted.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 6
    restarted.db.close()


def test_existing_maintainer_revision_and_missing_seeds_are_preserved(tmp_path):
    path = tmp_path / "customized.sqlite3"
    partial = SQLiteStore(path, [])
    first = partial.put_document({**DOCUMENTS[0], "body": "maintainer content"})
    revised = partial.put_document({**first, "body": "maintainer updated content"})
    partial.db.close()
    complete = SQLiteStore(path, DOCUMENTS)
    assert len(complete.documents()) == 5
    assert next(doc for doc in complete.documents() if doc["id"] == "api") == revised
    assert complete.db.execute("SELECT COUNT(*) FROM documents WHERE id='api'").fetchone()[0] == 2
    complete.db.close()
