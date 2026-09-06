# this program sets up and manages the sqlite index , and Fox uses to keep track of every file in Vault

# importing the nessary modules
import sqlite3
import time
from pathlib import Path

# Path location of DB, auto done by pathlib
DB_PATH = Path(__file__).resolve().parent / "file_index.db"

# this function handles the connection!
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_scheme(conn)
    return conn

# this contains the execution instruction of sql query
def _ensure_scheme(conn):
    # main sql squery contains all the nessary tables
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
    """
    )

    # FTS5 gives us fast keyword search over filenames + a short content snippet
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
            name, snippet, content='files', content_rowid='id'
        )
    """)

# this function is used to do operations like, file upload, delete, modify
def upsert_file(path, name, ext, category, size, mtime, snippet =""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM files WHERE path = ?", (str(path),))
    row = cur.fetchone()

    # condition to check the row in sqlite and if present updaet with new info else ask user to add them (ask more info)!
    if row:
        file_id = row["id"]
        cur.execute("UPDATE files SET name=?, ext=?, category=?, size=?, mtime=?, snippet=? WHERE id=?",
                    (name, ext, category, size, mtime, snippet, file_id))
    else:
        cur.execute("""INSERT INTO files (path, name, ext, category, size, mtime, snippet, added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(path), name, ext, category, size, mtime, snippet, time.time()))
        file_id = cur.lastrowid
        cur.execute("DELETE FROM files_fts WHERE rowid = ?", (file_id,))
        cur.execute("INSERT INTO files_fts (rowid, name, snippet) VALUES (?, ?, ?)", (file_id, name, snippet))
        conn.commit()
        conn.close()
        return file_id

# this function is used to remove data from the sql table
def remove_file(path):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM files WHERE path = ?", (str(path),)) # yes "," is used like next varible is unknowwn and its like optional but need it
    conn.commit()
    row = cur.fetchall()

    # this condition is responsible for deleting those data
    if row:
        cur.execute("DELETE FROM file WHERE id = ?", (row["id"],))
        cur.execute("DELETE FROM files_fts WHERE rowid = ?", (row["id"],))
        conn.commit()
    conn.close()

# this function is responsible for searching required file
def search_files(query, limit = 10):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT files.path, files.name, files.category, files.size, files.mtime
        FROM files_fts JOIN files ON files.id = files_fts.rowid
        WHERE files_fts MATCH ? ORDER BY rank LIMIT ?
    """, (query, limit))

    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results

# this function used to list all the stored idems
def list_all(category = None):
    conn = get_connection()
    cur = conn.cursor()

    # this condition list the stored items
    if category:
        cur.execute("ELECT * FROM files WHERE category = ? ORDER BY name", (category,))
    else:
        cur.execute("SELECT * FROM files ORDER BY category, name")

    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results
                    
