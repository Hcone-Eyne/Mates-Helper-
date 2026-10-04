"""Focused SQLite concurrency tests for brain/task_store.py (P1-7).

Proves the store stays correct when the threaded P1-6 workers hammer it:
single-winner claim/cancel races, contention without database-locked
failures, WAL reads-during-writes, old-DB migration, and honest surfacing
of genuinely unrecoverable errors. Temporary databases only; threads are
synchronized with Barriers, never arbitrary sleeps.
"""

import os
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain import task_store


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(task_store, "DB_PATH", str(tmp_path / "tasks.db"))
    # clear the once-per-process schema cache so each temp DB initializes
    task_store._schema_ready.discard(str(tmp_path / "tasks.db"))
    return tmp_path


def _race(fn, count=16):
    """Run fn() on `count` threads released simultaneously; return results."""
    barrier = threading.Barrier(count)
    results = [None] * count

    def runner(index):
        barrier.wait(timeout=10)
        results[index] = fn()

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)
    return results


class TestSingleWinnerRaces:
    def test_concurrent_claim_has_exactly_one_winner(self, db):
        task_id = task_store.add_task("race")

        results = _race(lambda: task_store.claim_task(task_id))

        assert results.count(True) == 1
        assert results.count(False) == 15
        assert task_store.get_task(task_id)["status"] == "running"

    def test_concurrent_cancel_has_exactly_one_winner(self, db):
        task_id = task_store.add_task("race")

        results = _race(lambda: task_store.cancel_task(task_id))

        assert results.count(True) == 1
        assert results.count(False) == 15
        assert task_store.get_task(task_id)["status"] == "cancelled"

    def test_cancel_loses_once_claimed(self, db):
        task_id = task_store.add_task("race")
        assert task_store.claim_task(task_id) is True
        assert task_store.cancel_task(task_id) is False
        assert task_store.get_task(task_id)["status"] == "running"


class TestContentionWithoutLockFailures:
    def test_concurrent_inserts_never_lock(self, db):
        errors = []
        barrier = threading.Barrier(8)

        def insert_many(worker):
            try:
                barrier.wait(timeout=10)
                for i in range(25):
                    task_store.add_task(f"w{worker}-t{i}")
            except Exception as exc:  # noqa: BLE001 - collected, then asserted
                errors.append(exc)

        threads = [threading.Thread(target=insert_many, args=(w,)) for w in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert errors == []
        rows = task_store.list_task()
        assert len(rows) == 200
        assert len({row["id"] for row in rows}) == 200

    def test_reads_proceed_during_writes(self, db):
        stop = threading.Event()
        errors = []
        reads = []

        def writer():
            try:
                for i in range(50):
                    task_store.add_task(f"row-{i}")
            except Exception as exc:  # noqa: BLE001 - collected, then asserted
                errors.append(exc)
            finally:
                stop.set()

        def reader():
            try:
                while not stop.is_set():
                    reads.append(len(task_store.list_task()))
            except Exception as exc:  # noqa: BLE001 - collected, then asserted
                errors.append(exc)

        writer_thread = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader) for _ in range(4)]
        writer_thread.start()
        for thread in readers:
            thread.start()
        writer_thread.join(timeout=60)
        for thread in readers:
            thread.join(timeout=60)

        assert errors == []
        assert reads, "readers never observed the table"
        assert len(task_store.list_task()) == 50

    def test_file_database_uses_wal(self, db):
        task_store.add_task("wal-check")
        conn = sqlite3.connect(task_store.DB_PATH, timeout=5.0)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        assert mode.lower() == "wal"


class TestMigrationAndHonestErrors:
    def test_provider_migration_on_old_database(self, db):
        path = task_store.DB_PATH
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    result TEXT,
                    status TEXT,
                    created_at REAL
                )"""
            )
            conn.execute(
                "INSERT INTO tasks (description, result, status, created_at)"
                " VALUES (?, ?, ?, ?)",
                ("legacy", None, "queued", 1.0),
            )
            conn.commit()
        finally:
            conn.close()

        task_store._schema_ready.discard(path)
        assert task_store.claim_task(1) is True
        assert task_store.get_task(1)["status"] == "running"
        assert task_store.get_task(1)["provider"] is None
        assert task_store.add_task("new") == 2

    def test_unrecoverable_error_surfaces(self, tmp_path, monkeypatch):
        # A database that cannot be opened at all must raise - never be
        # converted into a fake task state or an empty result.
        monkeypatch.setattr(task_store, "DB_PATH", str(tmp_path))
        with pytest.raises(sqlite3.OperationalError):
            task_store.add_task("doomed")
        with pytest.raises(sqlite3.OperationalError):
            task_store.list_task()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
