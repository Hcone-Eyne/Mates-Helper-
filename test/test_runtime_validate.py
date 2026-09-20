"""Tests for Runtime validate_target_dir and FileActionExecutor."""

import sys
import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.fox.runtime.runtime import validate_target_dir, Runtime, RuntimeResult, _UnavailableExecutor
from agent.fox.runtime.executor import FileActionExecutor, CATEGORIES


class TestValidateTargetDir:
    """Test validate_target_dir function."""

    def test_empty_string_returns_none(self):
        assert validate_target_dir("") is None
        assert validate_target_dir("   ") is None
        assert validate_target_dir("\t\n") is None

    def test_valid_directory_returns_path(self):
        with TemporaryDirectory() as tmpdir:
            result = validate_target_dir(tmpdir)
            assert result == Path(tmpdir).resolve()

    def test_valid_directory_with_tilde(self):
        with TemporaryDirectory() as tmpdir:
            # Can't easily test tilde expansion in temp dir, but test the path resolution
            result = validate_target_dir(tmpdir)
            assert isinstance(result, Path)
            assert result.is_absolute()

    def test_nonexistent_path_raises(self):
        with pytest.raises(ValueError, match="Path does not exist"):
            validate_target_dir("/this/path/does/not/exist")

    def test_file_not_directory_raises(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test")
            with pytest.raises(ValueError, match="Path is not a directory"):
                validate_target_dir(str(file_path))

    def test_relative_path_resolved(self):
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                subdir = Path("subdir")
                subdir.mkdir()
                result = validate_target_dir("subdir")
                assert result == subdir.resolve()
            finally:
                os.chdir(original_cwd)


class TestUnavailableExecutor:
    """Test _UnavailableExecutor placeholder."""

    def test_execute_raises_runtime_error(self):
        executor = _UnavailableExecutor()
        with pytest.raises(RuntimeError, match="No action executor is configured"):
            executor.execute("any_action", {})


class TestFileActionExecutor:
    """Test FileActionExecutor class."""

    def test_init_creates_target_directory(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "new_target"
            executor = FileActionExecutor(target)
            assert target.exists()
            assert target.is_dir()
            assert executor._target == target.resolve()

    def test_init_with_existing_directory(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            assert executor._target == Path(tmpdir).resolve()

    def test_assert_inside_allows_same_path(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            result = executor._assert_inside(Path(tmpdir))
            assert result == Path(tmpdir).resolve()

    def test_assert_inside_allows_subdirectory(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            result = executor._assert_inside(subdir)
            assert result == subdir.resolve()

    def test_assert_inside_allows_file_in_subdirectory(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            file_path = subdir / "test.txt"
            file_path.write_text("test")
            result = executor._assert_inside(file_path)
            assert result == file_path.resolve()

    def test_assert_inside_rejects_parent_directory(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir"
            executor = FileActionExecutor(target)
            # Target already created by executor
            with pytest.raises(PermissionError, match="escapes the target directory"):
                executor._assert_inside(Path(tmpdir))

    def test_assert_inside_rejects_sibling_directory(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir1"
            executor = FileActionExecutor(target)
            # Create sibling after executor creation
            (Path(tmpdir) / "subdir2").mkdir()
            with pytest.raises(PermissionError, match="escapes the target directory"):
                executor._assert_inside(Path(tmpdir) / "subdir2")

    def test_assert_inside_rejects_absolute_path_outside(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir"
            executor = FileActionExecutor(target)
            with pytest.raises(PermissionError, match="escapes the target directory"):
                executor._assert_inside(Path("/etc/passwd"))

    def test_execute_unknown_action_raises(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            with pytest.raises(RuntimeError, match="Unknown action 'unknown_action'"):
                executor.execute("unknown_action", {})

    def test_execute_case_insensitive(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            # Create a mock for the internal methods
            executor._list_directory = MagicMock(return_value={"summary": "listed"})
            result = executor.execute("LIST_DIRECTORY", {})
            assert result == {"summary": "listed"}
            executor._list_directory.assert_called_once()

    def test_execute_normalizes_action_name(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            executor._organise_folder = MagicMock(return_value={"summary": "organised"})
            result = executor.execute("  Organise Folder  ", {})
            assert result == {"summary": "organised"}
            executor._organise_folder.assert_called_once()


class TestFileActionExecutorOrganiseFolder:
    """Test FileActionExecutor._organise_folder method."""

    def test_organises_files_by_extension(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            # Create test files
            (target / "doc.pdf").write_text("pdf")
            (target / "code.py").write_text("py")
            (target / "image.png").write_text("png")
            (target / "unknown.xyz").write_text("xyz")

            executor = FileActionExecutor(target)
            result = executor._organise_folder({})

            assert result["target"] == str(target.resolve())
            assert "Documents" in result["moved"]
            assert "Code" in result["moved"]
            assert "Images" in result["moved"]
            assert "Other" in result["moved"]
            assert "doc.pdf" in result["moved"]["Documents"]
            assert "code.py" in result["moved"]["Code"]
            assert "image.png" in result["moved"]["Images"]
            assert "unknown.xyz" in result["moved"]["Other"]

    def test_skips_directories(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file.txt").write_text("txt")
            (target / "subdir").mkdir()

            executor = FileActionExecutor(target)
            result = executor._organise_folder({})

            assert "subdir" not in str(result["moved"])
            assert "Notes" in result["moved"]
            assert "file.txt" in result["moved"]["Notes"]

    def test_handles_duplicate_filenames(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file.txt").write_text("txt1")
            # Create a Notes directory with existing file.txt
            notes_dir = target / "Notes"
            notes_dir.mkdir()
            (notes_dir / "file.txt").write_text("existing")

            executor = FileActionExecutor(target)
            result = executor._organise_folder({})

            # The moved dict tracks original filenames, not renamed ones
            # The new file.txt is renamed to file_1.txt on disk but tracked as file.txt
            moved_files = result["moved"]["Notes"]
            assert "file.txt" in moved_files
            # Verify the file was actually moved (count should be 2 but only 1 tracked)
            # The actual renamed file exists on disk
            assert (notes_dir / "file.txt").exists()
            assert (notes_dir / "file_1.txt").exists()

    def test_creates_category_directories(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file.txt").write_text("txt")

            executor = FileActionExecutor(target)
            executor._organise_folder({})

            assert (target / "Notes").exists()
            assert (target / "Notes").is_dir()

    def test_summary_includes_moved_files(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "doc.pdf").write_text("pdf")
            (target / "code.py").write_text("py")

            executor = FileActionExecutor(target)
            result = executor._organise_folder({})

            assert "Documents" in result["summary"]
            assert "Code" in result["summary"]
            assert "doc.pdf" in result["summary"]
            assert "code.py" in result["summary"]

    def test_empty_directory_returns_no_files_summary(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            result = executor._organise_folder({})
            assert result["summary"] == "No files to organise."
            assert result["moved"] == {}


class TestFileActionExecutorListDirectory:
    """Test FileActionExecutor._list_directory method."""

    def test_lists_immediate_children(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file1.txt").write_text("1")
            (target / "file2.pdf").write_text("2")
            (target / "subdir").mkdir()

            executor = FileActionExecutor(target)
            result = executor._list_directory({})

            assert result["count"] == 3
            assert "file1.txt" in result["entries"]
            assert "file2.pdf" in result["entries"]
            assert "subdir" in result["entries"]
            assert result["recursive"] is False
            assert result["summary"] == "3 entries."

    def test_lists_recursive_when_requested(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file1.txt").write_text("1")
            subdir = target / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").write_text("2")

            executor = FileActionExecutor(target)
            result = executor._list_directory({"recursive": True})

            assert result["count"] == 3
            assert "file1.txt" in result["entries"]
            assert "subdir/file2.txt" in result["entries"]
            assert result["recursive"] is True
            assert "recursive" in result["summary"]

    def test_empty_directory(self):
        with TemporaryDirectory() as tmpdir:
            executor = FileActionExecutor(Path(tmpdir))
            result = executor._list_directory({})
            assert result["count"] == 0
            assert result["entries"] == []
            assert result["summary"] == "Directory is empty."

    def test_recursive_false_by_default(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            (target / "file.txt").write_text("txt")
            subdir = target / "subdir"
            subdir.mkdir()
            (subdir / "nested.txt").write_text("nested")

            executor = FileActionExecutor(target)
            result = executor._list_directory({})

            assert result["count"] == 2  # file.txt and subdir
            assert "subdir/nested.txt" not in result["entries"]

    def test_assert_inside_on_recursive_paths(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sub"
            target.mkdir()
            (target / "file.txt").write_text("txt")

            executor = FileActionExecutor(target)
            # This should not raise
            result = executor._list_directory({"recursive": True})
            assert result["count"] == 1


from unittest.mock import MagicMock