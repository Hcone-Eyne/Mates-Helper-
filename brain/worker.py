# Background task execution for the Brain HTTP API.
#
# Design (stdlib only, no broker): one daemon dispatcher thread feeds a
# bounded set of daemon worker threads from an in-memory queue. Task state
# lives in brain/task_store.py (SQLite) - never duplicated in memory.
#
# Honest timeout semantics: Python threads cannot be killed safely, so a
# task that outruns FOX_TASK_TIMEOUT_SECONDS is marked `timed_out` and its
# slot is released, while the underlying call keeps running detached until
# it returns. The status never lies about physical termination.
#
# Shutdown semantics: all threads are daemons, so shutdown never hangs.
# In-flight tasks are left detached and the process may exit; rows still
# marked `running` are reconciled to `failed` on the next startup, and rows
# still `queued` are re-enqueued (they never ran, so resuming them is safe).

import os
import queue
import threading

from brain import task_store

TASK_TIMEOUT_SECONDS_DEFAULT = 600
TASK_MAX_WORKERS_DEFAULT = 2


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def task_timeout_seconds() -> int:
    """Per-task execution budget; see FOX_TASK_TIMEOUT_SECONDS."""
    return _int_env("FOX_TASK_TIMEOUT_SECONDS", TASK_TIMEOUT_SECONDS_DEFAULT)


def max_workers() -> int:
    """Concurrently executing tasks; see FOX_TASK_MAX_WORKERS."""
    return _int_env("FOX_TASK_MAX_WORKERS", TASK_MAX_WORKERS_DEFAULT)


class TaskWorker:
    """Bounded background executor for Brain tasks."""

    def __init__(self, max_workers: int = TASK_MAX_WORKERS_DEFAULT,
                 timeout_seconds: int = TASK_TIMEOUT_SECONDS_DEFAULT):
        self._max_workers = max(1, max_workers)
        self._timeout_seconds = max(1, timeout_seconds)
        self._queue: queue.Queue = queue.Queue()
        self._slots = threading.Semaphore(self._max_workers)
        self._stopping = threading.Event()
        self._dispatcher: threading.Thread | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "TaskWorker":
        return cls(max_workers=max_workers(), timeout_seconds=task_timeout_seconds())

    def start(self) -> None:
        """Start the dispatcher thread (idempotent)."""
        with self._lock:
            self._stopping.clear()
            if self._dispatcher is not None and self._dispatcher.is_alive():
                return
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop, daemon=True, name="fox-task-dispatcher"
            )
            self._dispatcher.start()
        # NOTE: if a previous dispatcher is still exiting from shutdown, the
        # two briefly share this worker's queue and semaphore. That is safe
        # (queue/semaphore are thread-safe; a task is never taken twice),
        # and the old thread exits on its own within one queue poll.

    def submit(self, task_id: int, description: str, provider, run_fn) -> None:
        """Enqueue an already-persisted (queued) task for background execution."""
        self.start()
        self._queue.put((task_id, description, provider, run_fn))

    def shutdown(self) -> None:
        """Stop accepting dispatcher work. Bounded and never hangs: the
        dispatcher exits on its next queue poll, and workers are daemons,
        so in-flight tasks detach and the process can exit promptly."""
        self._stopping.set()
        with self._lock:
            thread, self._dispatcher = self._dispatcher, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _dispatch_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            # Bounded concurrency: at most max_workers runner threads exist.
            # Excess tasks wait in the queue (and stay `queued` in the DB).
            self._slots.acquire()
            thread = threading.Thread(
                target=self._run_item_guarded, args=(item,), daemon=True,
                name=f"fox-task-{item[0]}",
            )
            thread.start()

    def _run_item_guarded(self, item) -> None:
        try:
            self._run_item(item)
        except Exception as exc:
            # A worker failure becomes a task failure - never a stuck
            # `running` row and never a dead dispatcher.
            try:
                task_store.fail_task(item[0], f"[Fox]: Worker failure: {exc}")
            except Exception:
                pass
        finally:
            self._slots.release()

    def _run_item(self, item) -> None:
        task_id, description, provider, run_fn = item
        if not task_store.claim_task(task_id):
            # Lost the race (cancelled first): never execute.
            return
        outcome, payload = self._run_with_timeout(
            lambda: run_fn(description, provider)
        )
        if outcome == "ok":
            task_store.complete_task(task_id, payload)
        elif outcome == "timeout":
            task_store.timeout_task(
                task_id,
                f"[Fox]: Task timed out after {self._timeout_seconds}s.",
            )
        else:
            task_store.fail_task(task_id, f"[Fox]: Task failed: {payload}")

    def _run_with_timeout(self, fn):
        """Run fn with a timeout. Returns ("ok", result), ("timeout", None),
        or ("error", exception). On timeout the orphaned call keeps running
        detached - it is never force-killed."""
        outcome: dict = {}

        def target():
            try:
                outcome["result"] = fn()
            except BaseException as exc:  # never let a task kill its thread silently
                outcome["error"] = exc

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(self._timeout_seconds)
        if thread.is_alive():
            return ("timeout", None)
        if "error" in outcome:
            return ("error", outcome["error"])
        return ("ok", outcome.get("result"))

    def startup_recovery(self, run_fn) -> list:
        """Reconcile rows orphaned by a previous process, then re-enqueue
        tasks that never started. Returns the re-enqueued task ids."""
        self.start()
        requeued = []
        for task in task_store.recover_interrupted(
            "[Fox]: Task interrupted by shutdown."
        ):
            self._queue.put((task["id"], task["description"], task["provider"], run_fn))
            requeued.append(task["id"])
        return requeued


# Module singleton used by the HTTP layer. Tests construct TaskWorker
# directly for deterministic control instead of touching this global.
_default_worker: TaskWorker | None = None
_default_lock = threading.Lock()


def get_worker() -> TaskWorker:
    global _default_worker
    with _default_lock:
        if _default_worker is None:
            _default_worker = TaskWorker.from_env()
        return _default_worker


def enqueue(task_id: int, description: str, provider, run_fn) -> None:
    get_worker().submit(task_id, description, provider, run_fn)


def startup(run_fn) -> list:
    return get_worker().startup_recovery(run_fn)


def shutdown() -> None:
    global _default_worker
    with _default_lock:
        worker, _default_worker = _default_worker, None
    if worker is not None:
        worker.shutdown()
