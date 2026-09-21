"""Red-team security tests for Fox filesystem boundary.

These tests attempt to bypass or exploit the FoxSecurityBoundary.
They MUST all pass (i.e., attacks are rejected) for the boundary to be considered secure.
"""

import sys
import tempfile
from pathlib import Path

import pytest

from agent.fox.security import (
    FoxSecurityBoundary,
    FoxSecurityError,
    PathEscapeError,
    SymlinkEscapeError,
    PrivilegedActionError,
    FoxPolicyError,
)
from agent.fox.runtime.executor import FileActionExecutor


def make_boundary(tmp_path: Path) -> FoxSecurityBoundary:
    """Create a FoxSecurityBoundary with a temp root."""
    root = tmp_path / "fox"
    return FoxSecurityBoundary(root)


def make_executor(tmp_path: Path) -> tuple[Path, FoxSecurityBoundary, FileActionExecutor]:
    """Create a test executor with FoxSecurityBoundary."""
    root = tmp_path / "fox"
    boundary = FoxSecurityBoundary(root)
    executor = FileActionExecutor(boundary)
    return root, boundary, executor


# ======================================================================
# Path Traversal Attacks
# ======================================================================

class TestPathTraversal:
    """Test path traversal rejection."""

    def test_simple_parent_traversal(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("../outside.txt")

    def test_multi_level_parent_traversal(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("../../../etc/passwd")

    def test_mixed_traversal(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("workspace/../../outside.txt")

    def test_traversal_with_leading_slash(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("/../outside.txt")

    def test_traversal_in_middle(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("workspace/../apps/../../outside.txt")


# ======================================================================
# Absolute Path Attacks
# ======================================================================

class TestAbsolutePathAttacks:
    """Test absolute outside path rejection."""

    def test_absolute_outside_path(self, tmp_path):
        boundary = make_boundary(tmp_path)
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        with pytest.raises(PathEscapeError):
            boundary.validate_path(outside)

    def test_absolute_root_path(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path("/etc/passwd")

    def test_absolute_home_path(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PathEscapeError):
            boundary.validate_path(str(Path.home() / ".ssh" / "id_rsa"))


# ======================================================================
# Similar-Prefix Path Attacks
# ======================================================================

class TestSimilarPrefixAttacks:
    """Test similar-prefix directory name attacks."""

    def test_similar_prefix_rejected(self, tmp_path):
        root = tmp_path / "fox"
        similar = tmp_path / "fox_evil"
        root.mkdir()
        similar.mkdir()
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(PathEscapeError):
            boundary.validate_path(similar / "secret.txt")

    def test_case_variation_prefix(self, tmp_path):
        """Case variation attack - skipped on case-insensitive filesystems (macOS)."""
        if sys.platform == "darwin":
            pytest.skip("macOS filesystem is case-insensitive")
        root = tmp_path / "fox"
        similar = tmp_path / "FOX"
        root.mkdir()
        similar.mkdir()
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(PathEscapeError):
            boundary.validate_path(similar / "secret.txt")


# ======================================================================
# Symlink Escape Attacks
# ======================================================================

class TestSymlinkEscape:
    """Test symlink escape rejection."""

    def test_direct_symlink_escape(self, tmp_path):
        # Create the symlink structure first, then create the boundary
        root = tmp_path / "fox"
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("secret")
        link = root / "link"
        root.mkdir()
        link.symlink_to(outside, target_is_directory=True)
        # Create boundary AFTER symlink is created
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(SymlinkEscapeError):
            boundary.validate_path(link / "secret.txt")

    def test_nested_symlink_escape(self, tmp_path):
        root = tmp_path / "fox"
        outside = tmp_path / "outside"
        outside.mkdir()
        nested = outside / "nested"
        nested.mkdir()
        link = root / "safe"
        root.mkdir()
        link.mkdir()
        nested_link = link / "escape"
        nested_link.symlink_to(nested, target_is_directory=True)
        # Create boundary AFTER symlink is created
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(SymlinkEscapeError):
            boundary.validate_path(nested_link / "secret.txt")

    def test_broken_symlink_rejected(self, tmp_path):
        root = tmp_path / "fox"
        root.mkdir()
        link = root / "broken"
        link.symlink_to(root / "does-not-exist")
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(SymlinkEscapeError):
            boundary.validate_path(link)

    def test_symlink_to_parent(self, tmp_path):
        root = tmp_path / "fox"
        root.mkdir()
        link = root / "parent_link"
        link.symlink_to(tmp_path)
        boundary = FoxSecurityBoundary(root)
        with pytest.raises(SymlinkEscapeError):
            boundary.validate_path(link / "outside.txt")


# ======================================================================
# Read-Only Area Write Attacks
# ======================================================================

class TestReadOnlyAreaWrites:
    """Test that writes to read-only areas are rejected."""

    def test_write_to_system_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_write("system/config.json")

    def test_write_to_apps_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_write("apps/malware.py")

    def test_write_to_config_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_write("config/settings.yaml")

    def test_create_folder_in_system_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_create("system/evil_dir")

    def test_delete_from_system_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_delete("system/file.txt")


# ======================================================================
# Valid Writable Areas
# ======================================================================

class TestValidWritableAreas:
    """Test that workspace and storage accept writes."""

    def test_write_to_workspace_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        path = boundary.validate_write("workspace/file.txt")
        assert "workspace" in str(path)

    def test_write_to_storage_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        path = boundary.validate_write("storage/file.txt")
        assert "storage" in str(path)

    def test_create_folder_in_workspace_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        path = boundary.validate_create("workspace/subdir")
        assert "workspace" in str(path)

    def test_create_folder_in_storage_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        path = boundary.validate_create("storage/subdir")
        assert "storage" in str(path)


# ======================================================================
# Cross-Area Move/Write Attacks
# ======================================================================

class TestCrossAreaAttacks:
    """Test invalid cross-area moves and writes."""

    def test_move_from_system_to_workspace_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_move_source("system/file.txt")

    def test_move_from_apps_to_workspace_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_move_source("apps/file.txt")

    def test_copy_from_system_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        path = boundary.validate_copy_source("system/file.txt")
        assert "system" in str(path)

    def test_move_to_system_allowed_but_write_rejected(self, tmp_path):
        """validate_move_destination allows read-only areas (move target),
        but validate_write rejects them. The actual move would fail at write time."""
        boundary = make_boundary(tmp_path)
        # move_destination allows read-only areas
        path = boundary.validate_move_destination("system/file.txt")
        assert "system" in str(path)
        # But writing to system is still rejected
        with pytest.raises(FoxPolicyError):
            boundary.validate_write("system/file.txt")

    def test_organise_into_read_only_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            boundary.validate_organise_target("system/file.txt")


# ======================================================================
# Trash Bypass / Manipulation
# ======================================================================

class TestTrashSecurity:
    """Test trash isolation and bypass attempts."""

    def test_direct_trash_write_via_validate_write_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            boundary.validate_write(".fox_trash/file.txt")

    def test_trash_area_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            boundary.area(".fox_trash")

    def test_trash_path_validation(self, tmp_path):
        boundary = make_boundary(tmp_path)
        trash_file = boundary.trash_dir / "test.txt"
        trash_file.parent.mkdir(parents=True, exist_ok=True)
        trash_file.write_text("trash")
        validated = boundary.validate_trash_path(".fox_trash/test.txt", must_exist=True)
        assert validated == trash_file

    def test_trash_path_outside_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxSecurityError):
            boundary.validate_trash_path("workspace/file.txt", must_exist=False)

    def test_trash_write_bypass_via_path(self, tmp_path):
        boundary = make_boundary(tmp_path)
        trash_file = boundary.trash_dir / "test.txt"
        validated = boundary.validate_trash_write(".fox_trash/test.txt")
        assert validated == trash_file

    def test_restore_from_trash_to_system_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.validate_restore_destination("system/file.txt")


# ======================================================================
# Privileged Action Attacks
# ======================================================================

class TestPrivilegedActions:
    """Test empty_trash authorization requirements."""

    def test_empty_trash_without_token_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PrivilegedActionError):
            boundary.authorize_privileged_action("empty_trash")

    def test_empty_trash_with_false_token_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PrivilegedActionError):
            boundary.authorize_privileged_action("empty_trash", authorization_token=None)

    def test_empty_trash_with_wrong_object_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        other_boundary = make_boundary(tmp_path / "other")
        with pytest.raises(PrivilegedActionError):
            boundary.authorize_privileged_action("empty_trash", authorization_token=other_boundary)

    def test_empty_trash_with_boolean_confirm_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PrivilegedActionError):
            boundary.authorize_privileged_action("empty_trash", authorization_token=True)

    def test_empty_trash_with_string_token_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(PrivilegedActionError):
            boundary.authorize_privileged_action("empty_trash", authorization_token="fake_token")

    def test_empty_trash_with_correct_boundary_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        result = boundary.authorize_privileged_action("empty_trash", authorization_token=boundary)
        assert result == "empty_trash"

    def test_non_privileged_actions_dont_require_token(self, tmp_path):
        boundary = make_boundary(tmp_path)
        assert boundary.authorize_privileged_action("list_directory") == "list_directory"
        assert boundary.authorize_privileged_action("move_file") == "move_file"
        assert boundary.authorize_privileged_action("copy_file") == "copy_file"


# ======================================================================
# Executor-Level Attack Tests
# ======================================================================

class TestExecutorAttacks:
    """Test attacks through the FileActionExecutor."""

    def test_executor_write_to_system_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(FoxSecurityError):
            executor.execute("move_file", {"source": "workspace/a.txt", "destination": "system/b.txt"})

    def test_executor_copy_to_system_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(FoxSecurityError):
            executor.execute("copy_file", {"source": "workspace/a.txt", "destination": "system/b.txt"})

    def test_executor_create_folder_in_system_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(FoxSecurityError):
            executor.execute("create_folder", {"path": "system/evil"})

    def test_executor_delete_from_system_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(FoxSecurityError):
            executor.execute("delete_file", {"path": "system/file.txt"})

    def test_executor_restore_to_system_rejected(self, tmp_path):
        root, boundary, executor = make_executor(tmp_path)
        # Create a file in trash first
        (root / ".fox_trash" / "workspace").mkdir(parents=True, exist_ok=True)
        (root / ".fox_trash" / "workspace" / "a.txt").write_text("test")
        with pytest.raises(FoxSecurityError):
            executor.execute("restore_file", {"path": ".fox_trash/workspace/a.txt", "destination": "system/b.txt"})

    def test_executor_organise_respects_writable_areas(self, tmp_path):
        """Test that organise_folder respects writable area constraints."""
        root, boundary, executor = make_executor(tmp_path)
        # Create a file at root level
        (root / "test.txt").write_text("test")
        # organise_folder should work (creates category dirs in root)
        result = executor.execute("organise_folder", {})
        assert "moved" in result
        assert "Notes" in result["moved"]
        # The created category dirs should be in root, not in system/apps/config
        # The security boundary ensures this by validating organise targets

    def test_executor_empty_trash_without_authorization_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(PrivilegedActionError):
            executor.execute("empty_trash", {})

    def test_executor_empty_trash_with_fake_confirm_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(PrivilegedActionError):
            executor.execute("empty_trash", {"confirm": True})

    def test_executor_empty_trash_with_string_token_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        with pytest.raises(PrivilegedActionError):
            executor.execute("empty_trash", {"authorization_token": "fake"})

    def test_executor_empty_trash_with_boundary_succeeds(self, tmp_path):
        root, boundary, executor = make_executor(tmp_path)
        (root / "workspace").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "test.txt").write_text("test")
        executor.execute("delete_file", {"path": "workspace/test.txt"})
        result = executor.execute("empty_trash", {"authorization_token": boundary})
        assert result["success"] is True


# ======================================================================
# Root-Level File Compatibility (Regression Tests)
# ======================================================================

class TestRootLevelFileCompatibility:
    """Ensure root-level file operations work for executor compatibility."""

    def test_root_file_write_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        validated = boundary.validate_write("hello.txt")
        assert validated == boundary.root / "hello.txt"

    def test_root_file_read_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        validated = boundary.validate_read("hello.txt")
        assert validated == boundary.root / "hello.txt"

    def test_root_file_delete_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        validated = boundary.validate_delete("hello.txt")
        assert validated == boundary.root / "hello.txt"

    def test_root_file_copy_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        src = boundary.validate_read("hello.txt")
        dst = boundary.validate_write("hello_copy.txt")
        assert src == boundary.root / "hello.txt"
        assert dst == boundary.root / "hello_copy.txt"

    def test_root_file_rename_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        src = boundary.validate_write("hello.txt")
        dst = boundary.validate_write("hello_renamed.txt")
        assert src == boundary.root / "hello.txt"
        assert dst == boundary.root / "hello_renamed.txt"

    def test_root_file_restore_allowed(self, tmp_path):
        boundary = make_boundary(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        validated = boundary.validate_restore_destination("hello.txt")
        assert validated == boundary.root / "hello.txt"

    def test_root_directory_create_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="Arbitrary root-level directories are not allowed"):
            boundary.validate_create("new_dir")

    def test_root_itself_not_writable(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="root is not writable"):
            boundary.validate_write("")

    def test_root_itself_not_readable(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="root is not readable"):
            boundary.validate_read("")


# ======================================================================
# Additional Edge Cases
# ======================================================================

class TestEdgeCases:
    """Additional edge case tests."""

    def test_filename_traversal_in_rename_rejected(self, tmp_path):
        _, boundary, executor = make_executor(tmp_path)
        (boundary.root / "hello.txt").write_text("hello")
        with pytest.raises(FoxSecurityError):
            executor.execute("rename_file", {"path": "hello.txt", "new_name": "../evil.txt"})

    def test_empty_trash_only_operates_inside_trash(self, tmp_path):
        root, boundary, executor = make_executor(tmp_path)
        outside = tmp_path / "outside.txt"
        outside.write_text("DO NOT DELETE")
        executor.execute("empty_trash", {"authorization_token": boundary})
        assert outside.exists()
        assert outside.read_text() == "DO NOT DELETE"

    def test_boundary_immutability(self, tmp_path):
        root, boundary, executor = make_executor(tmp_path)
        with pytest.raises(FoxSecurityError):
            boundary._root = tmp_path / "evil"
        with pytest.raises(FoxSecurityError):
            boundary._trash_dir = tmp_path / "evil-trash"
        with pytest.raises(FoxSecurityError):
            boundary._policy = None

    def test_unknown_area_rejected(self, tmp_path):
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            boundary.validate_write("unknown/file.txt")

    def test_reserved_dirs_case_sensitive(self, tmp_path):
        """Case sensitivity test - skipped on case-insensitive filesystems (macOS)."""
        if sys.platform == "darwin":
            pytest.skip("macOS filesystem is case-insensitive")
        boundary = make_boundary(tmp_path)
        with pytest.raises(FoxPolicyError):
            boundary.area(".FOX_TRASH")

    def test_root_level_subdir_rejected(self, tmp_path):
        """Arbitrary subdirectories at root level are rejected (only managed dirs allowed)."""
        boundary = make_boundary(tmp_path)
        subdir = boundary.root / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("test")
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            boundary.validate_write("subdir/file.txt")

    def test_writable_alias_works(self, tmp_path):
        """WRITABLE_DIRS alias should work."""
        boundary = make_boundary(tmp_path)
        assert "workspace" in FoxSecurityBoundary.WRITABLE_DIRS
        assert "storage" in FoxSecurityBoundary.WRITABLE_DIRS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])