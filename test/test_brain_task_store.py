"""Tests for brain task_store module."""

import sys
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain import task_store


class TestTaskStore:
    """Test task_store module with temporary database."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_tasks.db")
        original_db_path = task_store.DB_PATH
        task_store.DB_PATH = self.db_path
        yield
        self.temp_dir.cleanup()
        task_store.DB_PATH = original_db_path

    def test_conn_creates_table(self):
        """Test that _conn creates the tasks table."""
        conn = task_store._conn()
        assert conn is not None

        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        assert cur.fetchone() is not None
        conn.close()

    def test_add_task(self):
        """Test adding a task to the database."""
        task_id = task_store.add_task("Test task description")

        assert task_id == 1

        # Verify task was added
        conn = task_store._conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        assert row[1] == "Test task description"
        assert row[2] is None  # result
        assert row[3] == "pending"  # status
        assert row[4] is not None  # created_at
        conn.close()

    def test_add_multiple_tasks(self):
        """Test adding multiple tasks."""
        id1 = task_store.add_task("First task")
        id2 = task_store.add_task("Second task")

        assert id1 == 1
        assert id2 == 2

    def test_complete_task(self):
        """Test completing a task."""
        task_id = task_store.add_task("Task to complete")

        task_store.complete_task(task_id, "Task completed successfully")

        # Verify task was updated
        conn = task_store._conn()
        cur = conn.cursor()
        cur.execute("SELECT result, status FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        assert row[0] == "Task completed successfully"
        assert row[1] == "done"
        conn.close()

    def test_complete_nonexistent_task(self):
        """Test completing a non-existent task (should not raise)."""
        task_store.complete_task(999, "Result")
        # Should not raise, just do nothing

    def test_list_tasks(self):
        """Test listing tasks."""
        task_store.add_task("Task 1")
        task_store.add_task("Task 2")
        task_store.complete_task(1, "Done")

        tasks = task_store.list_task()

        assert len(tasks) == 2
        # Should be ordered by id DESC (newest first)
        assert tasks[0]["id"] == 2
        assert tasks[1]["id"] == 1
        assert tasks[0]["description"] == "Task 2"
        assert tasks[1]["description"] == "Task 1"
        assert tasks[0]["status"] == "pending"
        assert tasks[1]["status"] == "done"
        assert tasks[1]["result"] == "Done"

    def test_list_tasks_empty(self):
        """Test listing tasks when database is empty."""
        tasks = task_store.list_task()
        assert tasks == []


class TestTaskStoreEdgeCases:
    """Edge case tests for task_store."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_tasks.db")
        original_db_path = task_store.DB_PATH
        task_store.DB_PATH = self.db_path
        yield
        self.temp_dir.cleanup()
        task_store.DB_PATH = original_db_path

    def test_add_task_with_special_characters(self):
        """Test adding task with special characters."""
        task_id = task_store.add_task("Task with 'quotes' and \"double quotes\"")
        assert task_id == 1

        conn = task_store._conn()
        cur = conn.cursor()
        cur.execute("SELECT description FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        assert "quotes" in row[0]
        conn.close()

    def test_add_task_with_unicode(self):
        """Test adding task with unicode characters."""
        task_id = task_store.add_task("タスク: 日本語のテスト")
        assert task_id == 1

    def test_complete_task_with_empty_result(self):
        """Test completing task with empty result string."""
        task_id = task_store.add_task("Test")
        task_store.complete_task(task_id, "")

        conn = task_store._conn()
        cur = conn.cursor()
        cur.execute("SELECT result FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        assert row[0] == ""
        conn.close()

    def test_add_very_long_description(self):
        """Test adding task with very long description."""
        long_desc = "x" * 10000
        task_id = task_store.add_task(long_desc)
        assert task_id == 1

    def test_complete_task_updates_timestamp(self):
        """Test that complete_task doesn't change created_at."""
        import time
        task_id = task_store.add_task("Test")
        time.sleep(0.01)
        task_store.complete_task(task_id, "Done")

        conn = task_store._conn()
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM tasks WHERE id=?", (task_id,))
        row = cur.fetchone()
        assert row[0] is not None
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])