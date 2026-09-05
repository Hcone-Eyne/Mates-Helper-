# this program is use to store the tasks and agent gets them from here and does the work!

# importing the nessary modules
import sqlite3
import time

# adding the DATA_BASE path!
DB_PATH = "/data/tasks.db"

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
            created_at REAL
        )"""
    )
    return conn

# this function is ment to add task to db
def add_task(description: str) -> int:
    conn = _conn()
    # again its like instruction of insert task in db
    cur = conn.execute(
        "INSERT INTO tasks (description, result, status, created_at) VALUES (?, ?, ?, ?)",
        (description, None, "pending", time.time()),
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
        "UPDATE tasks SET result = ?, status = 'done' WHERE id = ?",
        (result, task_id),
    )
    conn.commit()
    conn.close()

# this function is used to list the task stored in db to the agent
def list_task():
    conn = _conn()
    # same again used to execute sql query
    rows = conn.execute(
        "SELECT id, description, result, status, created_at FROM tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return[
        {"id": r[0], "description": r[1], "result": r[2], "status": r[3], "created_at": r[4]}
        # yes its a for loop iterate through the above!
        for r in rows
    ]
