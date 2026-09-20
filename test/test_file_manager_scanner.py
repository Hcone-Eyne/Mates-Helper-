"""Tests for File_Manager scanner module."""

import sys
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from File_Manager import scanner
from File_Manager import db
from File_Manager.organizer import CATEGORIES, VAULT_ROOT


class TestScanner:
    """Test scanner module with temporary database."""

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

    def test_scan_empty_vault(self):
        """Test scanning an empty vault directory."""
        root = Path(self.temp_dir.name) / "empty_vault"
        root.mkdir(parents=True)

        result = scanner.scan(root)

        assert result["root"] == str(root.resolve())
        assert result["indexed"] == 0
        assert result["removed"] == 0

    def test_scan_with_files(self):
        """Test scanning a vault with files."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        # Create category directories and files
        for cat in CATEGORIES[:3]:  # Documents, Notes, Code
            cat_dir = root / cat
            cat_dir.mkdir()
            (cat_dir / f"file_{cat.lower()}.txt").write_text(f"content for {cat}")

        result = scanner.scan(root)

        assert result["indexed"] == 3
        assert result["removed"] == 0

        # Verify files were indexed with correct categories
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, category FROM files")
        rows = cur.fetchall()
        assert len(rows) == 3
        categories = {row["category"] for row in rows}
        assert "Documents" in categories
        assert "Notes" in categories
        assert "Code" in categories
        conn.close()

    def test_scan_skips_directories(self):
        """Test that directories are not indexed as files."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        # Create a subdirectory (not a category)
        subdir = root / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        result = scanner.scan(root)

        # Only the nested file should be indexed, not the directory
        assert result["indexed"] == 1

    def test_scan_skips_symlinks(self):
        """Test that symbolic links are skipped."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        target = root / "real.txt"
        target.write_text("real")

        link = root / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        result = scanner.scan(root)

        # Only the real file should be indexed
        assert result["indexed"] == 1

    def test_scan_categorizes_by_parent_folder(self):
        """Test that files are categorized by their parent folder name."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        docs_dir = root / "Documents"
        docs_dir.mkdir()
        (docs_dir / "report.pdf").write_text("pdf content")

        notes_dir = root / "Notes"
        notes_dir.mkdir()
        (notes_dir / "note.txt").write_text("txt content")

        other_dir = root / "UnknownCategory"
        other_dir.mkdir()
        (other_dir / "mystery.xyz").write_text("unknown")

        result = scanner.scan(root)

        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, category FROM files ORDER BY name")
        rows = cur.fetchall()
        conn.close()

        categories = {row["name"]: row["category"] for row in rows}
        assert categories["report.pdf"] == "Documents"
        assert categories["note.txt"] == "Notes"
        assert categories["mystery.xyz"] == "Other"  # Unknown category -> Other

    def test_scan_removes_missing_files(self):
        """Test that files no longer on disk are removed from index."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        docs_dir = root / "Documents"
        docs_dir.mkdir()

        # Create and index initial files
        file1 = docs_dir / "keep.txt"
        file1.write_text("keep")
        file2 = docs_dir / "remove.txt"
        file2.write_text("remove")

        scanner.scan(root)

        # Delete one file
        file2.unlink()

        # Rescan
        result = scanner.scan(root)

        assert result["indexed"] == 1  # Only keep.txt remains
        assert result["removed"] == 1  # remove.txt was removed from index

    def test_scan_file_outside_vault_raises(self):
        """Test that scan_file raises for files outside vault."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        outside = Path(self.temp_dir.name) / "outside.txt"
        outside.write_text("outside")

        with pytest.raises(ValueError, match="outside the File Manager Vault"):
            scanner.scan_file(outside)

    @pytest.mark.skip(reason="scan_file uses hardcoded VAULT_ROOT, not testable with temp dirs")
    def test_scan_file_nonexistent_raises(self):
        """Test that scan_file raises for nonexistent files."""
        pass

    @pytest.mark.skip(reason="scan_file uses hardcoded VAULT_ROOT, not testable with temp dirs")
    def test_scan_file_indexes_single_file(self):
        """Test that scan_file indexes a single file."""
        pass


class TestScannerEdgeCases:
    """Edge case tests for scanner."""

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

    def test_scan_with_special_filenames(self):
        """Test scanning files with special characters in names."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        docs_dir = root / "Documents"
        docs_dir.mkdir()

        special_names = [
            "file with spaces.txt",
            "file'with'quotes.txt",
            "file(with)parens.txt",
            "file[with]brackets.txt",
            "файл.txt",  # Unicode
        ]

        for name in special_names:
            (docs_dir / name).write_text("content")

        result = scanner.scan(root)
        assert result["indexed"] == len(special_names)

    def test_scan_with_large_file(self):
        """Test scanning a large file."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        docs_dir = root / "Documents"
        docs_dir.mkdir()

        large_file = docs_dir / "large.txt"
        large_file.write_text("x" * 100000)  # 100KB

        result = scanner.scan(root)
        assert result["indexed"] == 1

    def test_scan_updates_existing_files(self):
        """Test that re-scanning updates modified files."""
        root = Path(self.temp_dir.name) / "vault"
        root.mkdir(parents=True)

        docs_dir = root / "Documents"
        docs_dir.mkdir()

        test_file = docs_dir / "test.txt"
        test_file.write_text("version 1")

        scanner.scan(root)

        # Modify file
        test_file.write_text("version 2")

        result = scanner.scan(root)

        # Should still be 1 file indexed (updated, not duplicated)
        assert result["indexed"] == 1
        assert result["removed"] == 0

        # Verify content updated
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT snippet FROM files WHERE name = 'test.txt'")
        row = cur.fetchone()
        conn.close()
        assert "version 2" in row["snippet"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])