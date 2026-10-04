"""Focused tests for Brain background task execution (P1-6).

The worker is exercised directly with controlled TaskWorker instances
(deterministic timeouts/worker counts) plus real persisted state - no
arbitrary sleeps, no fake asynchrony: blocking run functions use
threading.Events and tests synchronize on DB state with bounded polls.
"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain import task_store
from brain.worker import TaskWorker


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(task_store, "DB_PATH", str(tmp_path / "tasks.db"))
    return tmp_path


def _submit(worker, description, run_fn, provider="ollama"):
    task_id = task_store.add_task(description, provider)
    worker.submit(task_id, description, provider, run_fn)
    return task_id


def _wait_for(task_id, states, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = task_store.get_task(task_id)
        if task is not None and task["status"] in states:
            return task
        time.sleep(0.02)
    pytest.fail(f"task {task_id} never reached {states}")


@pytest.fixture()
def worker():
    worker = TaskWorker(max_workers=4, timeout_seconds=30)
    worker.start()
    yield worker
    worker.shutdown()


class TestSubmissionIsDetached:
    def test_submit_returns_without_waiting(self, db, worker):
        release = threading.Event()
        started = time.time()

        def slow(desc, provider):
            release.wait(10)
            return "slow-done"

        task_id = _submit(worker, "slow", slow)

        assert time.time() - started < 5
        assert task_store.get_task(task_id)["status"] in ("queued", "running")
        release.set()
        assert _wait_for(task_id, ("completed",))["result"] == "slow-done"

    def test_task_ids_still_come_from_the_store(self, db, worker):
        first = _submit(worker, "one", lambda desc, provider: "1")
        second = _submit(worker, "two", lambda desc, provider: "2")
        assert (first, second) == (1, 2)
        assert _wait_for(first, ("completed",))["result"] == "1"
        assert _wait_for(second, ("completed",))["result"] == "2"


class TestExecutionOutcomes:
    def test_failed_task_is_persisted(self, db, worker):
        def explode(desc, provider):
            raise RuntimeError("boom")

        task_id = _submit(worker, "doomed", explode)
        entry = _wait_for(task_id, ("failed",))
        assert "boom" in entry["result"]

    def test_base_exception_becomes_task_failure_not_stuck_running(self, db, worker):
        def abort(desc, provider):
            raise SystemExit("nope")

        task_id = _submit(worker, "abort", abort)
        assert _wait_for(task_id, ("failed",))["status"] == "failed"

    def test_worker_survives_failures(self, db, worker):
        def explode(desc, provider):
            raise RuntimeError("boom")

        bad = _submit(worker, "bad", explode)
        assert _wait_for(bad, ("failed",))["status"] == "failed"
        good = _submit(worker, "good", lambda desc, provider: "fine")
        assert _wait_for(good, ("completed",))["result"] == "fine"


class TestBoundedConcurrency:
    def test_excess_tasks_stay_queued(self, db):
        worker = TaskWorker(max_workers=1, timeout_seconds=30)
        worker.start()
        try:
            release = threading.Event()
            running = threading.Event()

            def first(desc, provider):
                running.set()
                release.wait(10)
                return "first-done"

            one = _submit(worker, "one", first)
            assert running.wait(timeout=10)
            two = _submit(worker, "two", lambda desc, provider: "second-done")

            assert task_store.get_task(two)["status"] == "queued"
            release.set()
            assert _wait_for(one, ("completed",))["result"] == "first-done"
            assert _wait_for(two, ("completed",))["result"] == "second-done"
        finally:
            worker.shutdown()

    def test_concurrent_tasks_all_complete(self, db, worker):
        ids = [_submit(worker, f"task-{i}", lambda desc, provider: desc) for i in range(6)]
        for task_id in ids:
            assert _wait_for(task_id, ("completed",))["status"] == "completed"


class TestTimeout:
    def test_overrunning_task_is_marked_timed_out(self, db):
        worker = TaskWorker(max_workers=2, timeout_seconds=1)
        worker.start()
        try:
            task_id = _submit(
                worker, "hangs", lambda desc, provider: threading.Event().wait(60)
            )
            entry = _wait_for(task_id, ("timed_out",), timeout=10)
            assert "timed out" in entry["result"]
        finally:
            worker.shutdown()

    def test_timeout_does_not_kill_the_pool(self, db):
        worker = TaskWorker(max_workers=2, timeout_seconds=1)
        worker.start()
        try:
            stuck = _submit(
                worker, "hangs", lambda desc, provider: threading.Event().wait(60)
            )
            assert _wait_for(stuck, ("timed_out",), timeout=10)["status"] == "timed_out"
            # the orphaned thread holds no slot: a fresh task still runs
            quick = _submit(worker, "quick", lambda desc, provider: "fast")
            assert _wait_for(quick, ("completed",))["result"] == "fast"
        finally:
            worker.shutdown()


class TestCancellationSemantics:
    def test_queued_cancel_wins_the_race(self, db):
        worker = TaskWorker(max_workers=1, timeout_seconds=30)
        worker.start()
        try:
            release = threading.Event()
            calls = []

            def first(desc, provider):
                release.wait(10)
                return "first-done"

            def second(desc, provider):
                calls.append(desc)
                return "second-done"

            one = _submit(worker, "one", first)
            _wait_for(one, ("running",))
            two = _submit(worker, "two", second)

            assert task_store.cancel_task(two) is True
            release.set()
            assert _wait_for(one, ("completed",))["result"] == "first-done"
            # the cancelled task never executed and stays cancelled
            assert task_store.get_task(two)["status"] == "cancelled"
            assert calls == []
        finally:
            worker.shutdown()

    def test_cancel_after_start_is_too_late(self, db, worker):
        release = threading.Event()

        def slow(desc, provider):
            release.wait(10)
            return "done"

        one = _submit(worker, "one", slow)
        _wait_for(one, ("running",))

        try:
            assert task_store.cancel_task(one) is False
        finally:
            release.set()
        assert _wait_for(one, ("completed",))["result"] == "done"

    def test_cancel_missing_task(self, db):
        assert task_store.cancel_task(999999) is False


class TestStoreLifecycle:
    def test_claim_is_single_winner(self, db):
        task_id = task_store.add_task("race")
        assert task_store.claim_task(task_id) is True
        assert task_store.claim_task(task_id) is False
        assert task_store.get_task(task_id)["status"] == "running"

    def test_recover_interrupted(self, db):
        doomed = task_store.add_task("doomed", "anthropic")
        assert task_store.claim_task(doomed) is True
        waiting = task_store.add_task("waiting", "anthropic")

        requeued = task_store.recover_interrupted("[Fox]: boom.")

        assert task_store.get_task(doomed)["status"] == "failed"
        assert "boom" in task_store.get_task(doomed)["result"]
        assert requeued == [{"id": waiting, "description": "waiting", "provider": "anthropic"}]

    def test_startup_recovery_reenqueues_with_original_provider(self, db):
        worker = TaskWorker(max_workers=2, timeout_seconds=30)
        try:
            waiting = task_store.add_task("waiting", "anthropic")
            requeued = worker.startup_recovery(lambda desc, provider: f"ran:{provider}")
            assert requeued == [waiting]
            entry = _wait_for(waiting, ("completed",))
            assert entry["result"] == "ran:anthropic"
        finally:
            worker.shutdown()

    def test_env_configuration(self, monkeypatch):
        from brain import worker as worker_module

        monkeypatch.setenv("FOX_TASK_TIMEOUT_SECONDS", "45")
        monkeypatch.setenv("FOX_TASK_MAX_WORKERS", "3")
        assert worker_module.task_timeout_seconds() == 45
        assert worker_module.max_workers() == 3

        monkeypatch.setenv("FOX_TASK_TIMEOUT_SECONDS", "nonsense")
        assert worker_module.task_timeout_seconds() == worker_module.TASK_TIMEOUT_SECONDS_DEFAULT


class TestShutdown:
    def test_shutdown_never_hangs_on_stuck_tasks(self, db):
        worker = TaskWorker(max_workers=1, timeout_seconds=30)
        worker.start()
        _submit(worker, "hangs", lambda desc, provider: threading.Event().wait(3600))

        started = time.time()
        worker.shutdown()
        assert time.time() - started < 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
