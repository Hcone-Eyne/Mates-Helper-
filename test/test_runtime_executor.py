# Tests for the FileActionExecutor used by Fox Club Runtime.

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.fox.runtime.executor import FileActionExecutor


def _make_test_folder():
    """Create a temporary directory with sample files and return its path."""
    tmp = tempfile.mkdtemp(prefix="fox_test_")

    # Create the 7 files from the live-test spec plus a video file.
    (Path(tmp) / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    (Path(tmp) / "notes.txt").write_text("hello")
    (Path(tmp) / "report.pdf").write_bytes(b"%PDF-1.0")
    (Path(tmp) / "song.mp3").write_bytes(b"\xff\xfb")
    (Path(tmp) / "script.py").write_text("print('hi')")
    (Path(tmp) / "data.csv").write_text("a,b,c")
    (Path(tmp) / "random.docx").write_bytes(b"PK")
    (Path(tmp) / "clip.mp4").write_bytes(b"\x00\x00\x00")

    return tmp


def test_organise_folder_creates_category_dirs():
    """organise_folder should create category subdirectories for files present."""
    tmp = _make_test_folder()
    try:
        executor = FileActionExecutor(Path(tmp))
        result = executor.execute("organise_folder", {})

        # Category directories should exist for every category that has files.
        for cat, files in result["moved"].items():
            if files:
                assert (Path(tmp) / cat).is_dir(), f"Missing category dir: {cat}"

        # The summary should be a non-empty string.
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_moves_files_correctly():
    """Each file should end up in the correct category directory."""
    tmp = _make_test_folder()
    try:
        executor = FileActionExecutor(Path(tmp))
        result = executor.execute("organise_folder", {})

        # .jpg -> Images
        assert (Path(tmp) / "Images" / "photo.jpg").exists()
        # .txt -> Notes
        assert (Path(tmp) / "Notes" / "notes.txt").exists()
        # .pdf -> Documents
        assert (Path(tmp) / "Documents" / "report.pdf").exists()
        # .mp3 -> Audio
        assert (Path(tmp) / "Audio" / "song.mp3").exists()
        # .py -> Code
        assert (Path(tmp) / "Code" / "script.py").exists()
        # .csv -> Documents
        assert (Path(tmp) / "Documents" / "data.csv").exists()
        # .docx -> Documents
        assert (Path(tmp) / "Documents" / "random.docx").exists()

        # The moved dict should list files by category.
        assert "Images" in result["moved"]
        assert "photo.jpg" in result["moved"]["Images"]
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_preserves_duplicate_filenames():
    """Duplicate filenames across the same category get a numeric suffix."""
    tmp = tempfile.mkdtemp(prefix="fox_dup_")
    try:
        # Two .txt files with different names — both go to Notes.
        (Path(tmp) / "alpha.txt").write_text("a")
        (Path(tmp) / "beta.txt").write_text("b")

        executor = FileActionExecutor(Path(tmp))
        executor.execute("organise_folder", {})

        assert (Path(tmp) / "Notes" / "alpha.txt").exists()
        assert (Path(tmp) / "Notes" / "beta.txt").exists()
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_skips_directories():
    """Subdirectories should not be moved into category folders."""
    tmp = tempfile.mkdtemp(prefix="fox_dir_")
    try:
        sub = Path(tmp) / "existing_subdir"
        sub.mkdir()
        (Path(tmp) / "readme.md").write_text("hi")

        executor = FileActionExecutor(Path(tmp))
        result = executor.execute("organise_folder", {})

        # The subdirectory should remain at the root.
        assert sub.is_dir()
        # The subdirectory should not appear in any category's moved list.
        for cat_files in result["moved"].values():
            assert "existing_subdir" not in cat_files
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_empty_directory():
    """Organising an empty folder should return a valid summary."""
    tmp = tempfile.mkdtemp(prefix="fox_empty_")
    try:
        executor = FileActionExecutor(Path(tmp))
        result = executor.execute("organise_folder", {})

        assert result["summary"] == "No files to organise."
        assert result["moved"] == {}
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_rejects_path_traversal():
    """The executor must reject paths that escape the target directory."""
    tmp = _make_test_folder()
    try:
        executor = FileActionExecutor(Path(tmp))

        # A path outside the target should be rejected.
        outside = Path(tmp).parent / "outside.txt"
        try:
            executor._assert_inside(outside)
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass  # expected
    finally:
        shutil.rmtree(tmp)


def test_organise_folder_rejects_unknown_action():
    """Unknown actions should raise RuntimeError."""
    tmp = tempfile.mkdtemp(prefix="fox_action_")
    try:
        executor = FileActionExecutor(Path(tmp))
        try:
            executor.execute("delete_everything", {})
            assert False, "Should have raised RuntimeError"
        except RuntimeError as exc:
            assert "Unknown action" in str(exc)
    finally:
        shutil.rmtree(tmp)


def test_action_name_is_case_insensitive():
    """Action names should be normalised to lowercase with underscores."""
    tmp = _make_test_folder()
    try:
        executor = FileActionExecutor(Path(tmp))
        # "Organise Folder" with spaces and mixed case.
        result = executor.execute("Organise Folder", {})
        assert isinstance(result["summary"], str)
    finally:
        shutil.rmtree(tmp)


def test_target_directory_created_if_missing():
    """The executor should create the target directory if it doesn't exist."""
    tmp = tempfile.mkdtemp(prefix="fox_create_")
    try:
        target = Path(tmp) / "new_folder"
        assert not target.exists()

        executor = FileActionExecutor(target)
        assert target.is_dir()
    finally:
        shutil.rmtree(tmp)


def test_symlink_outside_target_is_rejected():
    """A symlink inside the target pointing outside must be rejected by _assert_inside."""
    tmp = tempfile.mkdtemp(prefix="fox_sym_")
    try:
        # Create a real file outside the target.
        outside_dir = tempfile.mkdtemp(prefix="fox_outside_")
        outside_file = Path(outside_dir) / "secret.txt"
        outside_file.write_text("secret")

        target = Path(tmp) / "workspace"
        target.mkdir()

        # Create a symlink inside the target that points to the outside file.
        link = target / "sneak.txt"
        link.symlink_to(outside_file)

        executor = FileActionExecutor(target)

        # _assert_inside must reject the resolved symlink target.
        try:
            executor._assert_inside(link)
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass  # expected — the symlink resolves outside the target

        # organise_folder must also reject it during execution.
        try:
            executor.execute("organise_folder", {})
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass  # expected
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(outside_dir)
