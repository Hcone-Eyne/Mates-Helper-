"""Tests for File_Manager search module."""

import sys
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from File_Manager import search
from File_Manager import db


class TestSearch:
    """Test search module with mocked database."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_file_index.db"
        import File_Manager.db as db_module
        self.original_db_path = db_module.DB_PATH
        db_module.DB_PATH = self.db_path
        yield
        self.temp_dir.cleanup()
        db_module.DB_PATH = self.original_db_path

    def test_search_empty_query(self):
        """Test search with empty query returns empty list."""
        result = search.search("")
        assert result == []

    def test_search_whitespace_query(self):
        """Test search with whitespace-only query returns empty list."""
        result = search.search("   ")
        assert result == []

    def test_search_none_query(self):
        """Test search with None query returns empty list."""
        result = search.search(None)
        assert result == []

    def test_search_calls_db_search_files(self):
        """Test that search calls db.search_files with correct parameters."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = [{"name": "test.txt", "path": "/tmp/test.txt"}]
            result = search.search("test query", limit=5)
            mock_search.assert_called_once_with("test query", 5)
            assert len(result) == 1

    def test_search_strips_query(self):
        """Test that search strips whitespace from query."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = []
            search.search("  test query  ", limit=10)
            mock_search.assert_called_once_with("test query", 10)

    def test_search_limit_clamped(self):
        """Test that search clamps limit to valid range."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = []
            search.search("query", limit=0)
            mock_search.assert_called_once_with("query", 1)

            mock_search.reset_mock()
            search.search("query", limit=200)
            mock_search.assert_called_once_with("query", 100)

    def test_search_category(self):
        """Test search_category function."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": "test.txt", "category": "Documents"}]
            result = search.search_category("Documents", limit=50)
            mock_list.assert_called_once_with("Documents")
            assert len(result) == 1

    def test_search_category_limit(self):
        """Test search_category respects limit."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": f"file{i}.txt"} for i in range(200)]
            result = search.search_category("Documents", limit=50)
            assert len(result) == 50

    def test_list_files(self):
        """Test list_files function."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": "test.txt"}]
            result = search.list_files("Documents", limit=10)
            mock_list.assert_called_once_with("Documents")
            assert len(result) == 1

    def test_list_files_no_category(self):
        """Test list_files with no category filter."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": "test.txt"}]
            result = search.list_files(limit=10)
            mock_list.assert_called_once_with(None)
            assert len(result) == 1


class TestSearchEdgeCases:
    """Edge case tests for search module."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_file_index.db"
        import File_Manager.db as db_module
        self.original_db_path = db_module.DB_PATH
        db_module.DB_PATH = self.db_path
        yield
        self.temp_dir.cleanup()
        db_module.DB_PATH = self.original_db_path

    def test_search_with_special_characters(self):
        """Test search with special characters in query."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = []
            search.search("test'query\"with;special")
            mock_search.assert_called_once()

    def test_search_unicode_query(self):
        """Test search with unicode query."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = []
            search.search("日本語検索")
            mock_search.assert_called_once()

    def test_search_very_long_query(self):
        """Test search with very long query."""
        with patch("File_Manager.search.db.search_files") as mock_search:
            mock_search.return_value = []
            long_query = "x" * 10000
            search.search(long_query)
            mock_search.assert_called_once()

    def test_search_category_not_found(self):
        """Test search_category with non-existent category."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = []
            result = search.search_category("NonExistent", limit=10)
            assert result == []

    def test_list_files_limit_not_clamped(self):
        """Test list_files doesn't clamp limit, just slices results."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": f"file{i}"} for i in range(200)]
            result = search.list_files(None, limit=150)
            assert len(result) == 150

    def test_search_category_limit_not_clamped(self):
        """Test search_category doesn't clamp limit, just slices results."""
        with patch("File_Manager.search.db.list_all") as mock_list:
            mock_list.return_value = [{"name": f"file{i}"} for i in range(200)]
            result = search.search_category("Documents", limit=150)
            assert len(result) == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])