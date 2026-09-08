# this program sets up and manages the sqlite index, and is used to keep track of every file in Vault
# cmd: from File_Manager.db import upsert_file, search_files, list_all
# cmd: upsert_file("/tmp/file.pdf", "file.pdf", ".pdf", "Documents", 123, 1700000000.0, "sample")

# importing the necessary modules
import sqlite3
import time
from pathlib import Path
 
# path location of DB, auto-detected by pathlib
DB_PATH = Path(__file__).resolve().parent / "file_index.db"
 
 
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_scheme(conn)
    return conn
 
 
def _ensure_scheme(conn):
    # main SQL schema contains all the necessary tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           path TEXT UNIQUE NOT NULL,
           name TEXT NOT NULL,
           ext TEXT,
           category TEXT,
           size INTEGER,
           mtime REAL,
           snippet TEXT,
           added_at REAL
        )
    """)
 
    # FTS5 gives us fast keyword search over filenames + a short content snippet
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
           name, snippet, content='files', content_rowid='id'
        )
    """)
 
 
def upsert_file(path, name, ext, category, size, mtime, snippet=""):
    # cmd: upsert_file(Path("/tmp/example.txt"), "example.txt", ".txt", "Notes", 42, 1700000000.0)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM files WHERE path = ?", (str(path),))
    row = cur.fetchone()
 
    if row:
        file_id = row["id"]
        cur.execute(
           "UPDATE files SET name=?, ext=?, category=?, size=?, mtime=?, snippet=? WHERE id=?",
           (name, ext, category, size, mtime, snippet, file_id),
        )
    else:
        cur.execute(
           """INSERT INTO files (path, name, ext, category, size, mtime, snippet, added_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
           (str(path), name, ext, category, size, mtime, snippet, time.time()),
        )
        file_id = cur.lastrowid
 
    cur.execute("DELETE FROM files_fts WHERE rowid = ?", (file_id,))
    cur.execute("INSERT INTO files_fts (rowid, name, snippet) VALUES (?, ?, ?)", (file_id, name, snippet))
    conn.commit()
    conn.close()
    return file_id
 
 
def remove_file(path):
    # cmd: remove_file(Path("/tmp/example.txt"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM files WHERE path = ?", (str(path),))
    row = cur.fetchone()
 
    if row is not None:
        file_id = row["id"]
        cur.execute("DELETE FROM files WHERE id = ?", (file_id,))
        cur.execute("DELETE FROM files_fts WHERE rowid = ?", (file_id,))
        conn.commit()
 
    conn.close()
    return row is not None
 
 
def search_files(query, limit=10):
    # cmd: search_files("report", 5)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT files.path, files.name, files.category, files.size, files.mtime
          FROM files_fts JOIN files ON files.id = files_fts.rowid
          WHERE files_fts MATCH ? ORDER BY rank LIMIT ?
        """,
        (query, limit),
    )
 
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results
 
 
def list_all(category=None):
    # cmd: list_all("Documents")
    conn = get_connection()
    cur = conn.cursor()
 
    if category:
        cur.execute("SELECT * FROM files WHERE category = ? ORDER BY name", (category,))
    else:
        cur.execute("SELECT * FROM files ORDER BY category, name")
 
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results

# this function is used to get the file in the directory.....
def get_file(path):
    """Return one indexed file by its master path"""

    # getting the connection alive for db
    conn = get_connection()
    cur = conn.cursor()

    # this is a sql cmd used to select a paticular path and find path
    conn.execute(
        "SELECT * FROM files WHERE path = ?",
        (str(Path(path).resolve()),)
    )

    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None

# this function is used to remove file whoes existence no longer required.....
def remove_file(root, seen_paths):
    """Remove indexed files under root that no longer exist on disk."""
    root = Path(root).resolve()

    # getting the connection alive for db
    conn = get_connection()
    cur = conn.cursor()

    # this is a sql cmd used to fetch path directions
    cur.execute(
        "SELECT id, path FROM files WHERE path LIKE ?",
        (str(root) + "/%",)
    )

    rows = cur.fetchall()
    removed = 0

    for row in rows:
        if row["path"] not in seen_paths:
            cur.execute(
                "DELETE FROM files_fts WHERE rowid = ?",
                (row["id"],)
            )
            cur.execute(
                "DELETE FROM files WHERE id = ?",
                (row["id"],)
            )
            removed += 1

    conn.commit()
    conn.close()

    return removed

