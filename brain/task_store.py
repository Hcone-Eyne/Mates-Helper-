# this program is use to store the tasks and agent gets them from here and does the work!

# importing the nessary modules
import os
import sqlite3
import time

# adding the DATA_BASE path!
# /data is the compose volume; set FOX_TASK_DB_PATH to point somewhere else
# (e.g. a temp file) when running the brain outside the container.
_DOCKER_DB_PATH = "/data/tasks.db"
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOST_DB_PATH = os.path.join(_REPO_ROOT, "data", "tasks.db")


def default_db_path() -> str:
    """Pick a task DB path that is actually writable here.

    Priority:
      1. FOX_TASK_DB_PATH - always wins (tests, containers, CI).
      2. /data/tasks.db - only when the compose volume directory exists, so
         the container keeps its published database.
      3. <repo>/data/tasks.db - the development/host fallback. Hardcoding
         /data here made every host run of POST /submit_task fail with
         "unable to open database file".
    """
    override = os.environ.get("FOX_TASK_DB_PATH")
    if override:
        return override

    docker_dir = os.path.dirname(_DOCKER_DB_PATH)
    if os.path.isdir(docker_dir) and os.access(docker_dir, os.W_OK):
        return _DOCKER_DB_PATH

    return _HOST_DB_PATH


DB_PATH = default_db_path()

# conn = _conn is like connection to database and conn.close Ahh that name itself mention that!

# this function is going to handle/ stores data in the db also
# this function is like one way to get access / connection to db
def _conn():
    conn = sqlite3.connect(DB_PATH)
    # this part is where it contains instruction to fetch the existing things in database
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            result TEXT,
            status TEXT,
            created_at REAL,
            provider TEXT
        )"""
    )
    # additive migration for databases created before the provider column:
    # a single ALTER TABLE, never a rebuild, so old rows keep working.
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)")]
    if "provider" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN provider TEXT")
    return conn

# Task lifecycle states. There is exactly one state system:
#   queued     - accepted, waiting for a worker
#   running    - claimed by exactly one worker
#   completed  - worker finished successfully
#   failed     - worker raised or the row was orphaned by a shutdown
#   cancelled  - cancelled while still queued (never ran)
#   timed_out  - worker gave up waiting past FOX_TASK_TIMEOUT_SECONDS
#
# Transitions are guarded so they stay deterministic under concurrency:
# only the worker that atomically claimed queued->running may write the
# terminal state, and only a queued task may become cancelled. A task can
# therefore never go cancelled->running or be executed twice.

# this function is ment to add task to db
def add_task(description: str, provider: str = "ollama") -> int:
    conn = _conn()
    # again its like instruction of insert task in db
    cur = conn.execute(
        "INSERT INTO tasks (description, result, status, created_at, provider) VALUES (?, ?, ?, ?, ?)",
        (description, None, "queued", time.time(), provider),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id

# this function is used to update task which got completed by agent
def complete_task(task_id: int, result:str):
    conn = _conn()
    # again its instruction for execution of sql query!
    conn.execute(
        "UPDATE tasks SET result = ?, status = 'completed' WHERE id = ?",
        (result, task_id),
    )
    conn.commit()
    conn.close()

# this function records a terminal failure so a task never stays "queued"
def fail_task(task_id: int, error: str):
    conn = _conn()
    conn.execute(
        "UPDATE tasks SET result = ?, status = 'failed' WHERE id = ?",
        (str(error), task_id),
    )
    conn.commit()
    conn.close()

# this function is used to list the task stored in db to the agent
def list_task():
    conn = _conn()
    # same again used to execute sql query
    rows = conn.execute(
        "SELECT id, description, result, status, created_at, provider FROM tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return[
        {"id": r[0], "description": r[1], "result": r[2], "status": r[3], "created_at": r[4], "provider": r[5]}
        # yes its a for loop iterate through the above!
        for r in rows
    ]

# this function fetches one task by id (None when it does not exist)
def get_task(task_id: int):
    conn = _conn()
    row = conn.execute(
        "SELECT id, description, result, status, created_at, provider FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "description": row[1], "result": row[2], "status": row[3], "created_at": row[4], "provider": row[5]}

# this function atomically claims a queued task for execution.
# only one worker can win the race: the UPDATE only matches queued rows,
# so a task cancelled first can never start, and a task started first can
# never be cancelled afterwards.
def claim_task(task_id: int) -> bool:
    conn = _conn()
    cur = conn.execute(
        "UPDATE tasks SET status = 'running' WHERE id = ? AND status = 'queued'",
        (task_id,),
    )
    conn.commit()
    claimed = cur.rowcount > 0
    conn.close()
    return claimed

# this function cancels a task that has not started yet.
# returns True only when this call performed queued->cancelled.
def cancel_task(task_id: int) -> bool:
    conn = _conn()
    cur = conn.execute(
        "UPDATE tasks SET status = 'cancelled' WHERE id = ? AND status = 'queued'",
        (task_id,),
    )
    conn.commit()
    cancelled = cur.rowcount > 0
    conn.close()
    return cancelled

# this function records a task that outran FOX_TASK_TIMEOUT_SECONDS.
# the worker owns the row (it claimed queued->running first), so this is
# a plain terminal write like complete_task/fail_task.
def timeout_task(task_id: int, message: str):
    conn = _conn()
    conn.execute(
        "UPDATE tasks SET result = ?, status = 'timed_out' WHERE id = ?",
        (str(message), task_id),
    )
    conn.commit()
    conn.close()

# this function reconciles rows left behind by a dead process.
# running rows could never have finished, so they become failed; queued
# rows never started, so they are returned (with their provider) for
# re-enqueueing. called once at worker startup, never in the request path.
def recover_interrupted(message: str) -> list:
    conn = _conn()
    conn.execute(
        "UPDATE tasks SET result = ?, status = 'failed' WHERE status = 'running'",
        (str(message),),
    )
    rows = conn.execute(
        "SELECT id, description, provider FROM tasks WHERE status = 'queued' ORDER BY id"
    ).fetchall()
    conn.commit()
    conn.close()
    return [{"id": row[0], "description": row[1], "provider": row[2] or "ollama"} for row in rows]
