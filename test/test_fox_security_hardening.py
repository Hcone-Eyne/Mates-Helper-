from pathlib import Path
import importlib
import sys

import pytest

def reload_fox_security():
    """Reload the fox security module to avoid pytest caching."""
    for mod_name in list(sys.modules.keys()):
        if 'agent.fox.security' in mod_name:
            del sys.modules[mod_name]
    from agent.fox.security import (
        FoxSecurityBoundary,
        FoxSecurityError,
        PathEscapeError,
        PrivilegedActionError,
        SymlinkEscapeError,
    )
    return FoxSecurityBoundary, FoxSecurityError, PathEscapeError, PrivilegedActionError, SymlinkEscapeError


@pytest.fixture
def fox_security():
    """Fixture that provides fresh imports for each test."""
    return reload_fox_security()

import pytest

from agent.fox.runtime.executor import FileActionExecutor


def make_executor(tmp_path: Path):
    root = tmp_path / "fox"
    boundary = FoxSecurityBoundary(root)
    executor = FileActionExecutor(boundary)
    return root, boundary, executor


def test_empty_trash_rejects_confirm_boolean(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "workspace" / "hello.txt"
    file_path.parent.mkdir()
    file_path.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "workspace/hello.txt"},
    )

    with pytest.raises(PrivilegedActionError):
        executor.execute(
            "empty_trash",
            {"confirm": True},
        )


def test_empty_trash_rejects_missing_authorization(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "workspace" / "hello.txt"
    file_path.parent.mkdir()
    file_path.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "workspace/hello.txt"},
    )

    with pytest.raises(PrivilegedActionError):
        executor.execute(
            "empty_trash",
            {},
        )


def test_empty_trash_accepts_boundary_authorization(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "workspace" / "hello.txt"
    file_path.parent.mkdir()
    file_path.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "workspace/hello.txt"},
    )

    result = executor.execute(
        "empty_trash",
        {
            "authorization_token": boundary,
        },
    )

    assert result["success"] is True
    assert result["deleted_count"] == 1


def test_parent_traversal_rejected(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    with pytest.raises(PathEscapeError):
        boundary.validate_path("../outside.txt")


def test_absolute_outside_path_rejected(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    with pytest.raises(PathEscapeError):
        boundary.validate_path(outside)


def test_absolute_alias_outside_root_rejected(tmp_path, fox_security):
    FoxSecurityBoundary, _, PathEscapeError, _, _ = fox_security
    root = tmp_path / "fox"
    root.mkdir()

    alias = tmp_path / "fox_alias"
    alias.symlink_to(root, target_is_directory=True)

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(PathEscapeError):
        boundary.validate_path(alias / "secret.txt")


def test_similar_prefix_path_rejected(tmp_path):
    root = tmp_path / "fox"
    similar = tmp_path / "fox_evil"

    root.mkdir()
    similar.mkdir()

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(PathEscapeError):
        boundary.validate_path(similar / "secret.txt")


def test_symlink_escape_rejected(tmp_path):
    root = tmp_path / "fox"
    root.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()

    secret = outside / "secret.txt"
    secret.write_text("secret")

    link = root / "link"
    link.symlink_to(outside, target_is_directory=True)

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(SymlinkEscapeError):
        boundary.validate_path(link / "secret.txt")


def test_nested_symlink_escape_rejected(tmp_path):
    root = tmp_path / "fox"
    root.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()

    nested = outside / "nested"
    nested.mkdir()

    link = root / "safe"
    link.mkdir()

    nested_link = link / "escape"
    nested_link.symlink_to(nested, target_is_directory=True)

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(SymlinkEscapeError):
        boundary.validate_path(
            nested_link / "secret.txt"
        )


def test_broken_symlink_rejected(tmp_path):
    root = tmp_path / "fox"
    root.mkdir()

    link = root / "broken"
    link.symlink_to(
        root / "does-not-exist"
    )

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(SymlinkEscapeError):
        boundary.validate_path(link)


def test_delete_trash_destination_stays_inside_root(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "workspace" / "hello.txt"
    file_path.parent.mkdir()
    file_path.write_text("hello")

    result = executor.execute(
        "delete_file",
        {"path": "workspace/hello.txt"},
    )

    trash_path = root / result["trash_path"]

    assert trash_path.exists()
    assert trash_path.is_file()
    assert trash_path.is_relative_to(root)


def test_restore_default_destination_is_inside_root(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    original = root / "workspace" / "hello.txt"
    original.parent.mkdir()
    original.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "workspace/hello.txt"},
    )

    result = executor.execute(
        "restore_file",
        {
            "path": ".fox_trash/workspace/hello.txt"
        },
    )

    restored = root / result["restored_to"]

    assert restored.exists()
    assert restored.read_text() == "hello"
    assert restored.is_relative_to(root)


def test_search_limit_must_be_integer(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError):
        executor.execute(
            "search_files",
            {
                "query": "test",
                "limit": "100",
            },
        )


def test_search_limit_must_be_positive(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError):
        executor.execute(
            "search_files",
            {
                "query": "test",
                "limit": 0,
            },
        )


def test_filename_traversal_rejected(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    with pytest.raises(FoxSecurityError):
        executor.execute(
            "rename_file",
            {
                "path": "hello.txt",
                "new_name": "../evil.txt",
            },
        )


def test_empty_trash_only_operates_inside_trash(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    outside = tmp_path / "outside.txt"
    outside.write_text("DO NOT DELETE")

    executor.execute(
        "empty_trash",
        {
            "authorization_token": boundary,
        },
    )

    assert outside.exists()
    assert outside.read_text() == "DO NOT DELETE"


def test_boundary_root_cannot_be_changed(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError):
        boundary._root = tmp_path / "evil"

    with pytest.raises(FoxSecurityError):
        boundary._trash_dir = tmp_path / "evil-trash"

def test_get_area_workspace(tmp_path):
    boundary = FoxSecurityBoundary(tmp_path / "fox")

    path = boundary.root / "workspace" / "test.txt"

    assert boundary.get_area(path) == "workspace"


def test_get_area_system(tmp_path):
    boundary = FoxSecurityBoundary(tmp_path / "fox")

    path = boundary.root / "system" / "runtime.json"

    assert boundary.get_area(path) == "system"


# ------------------------------------------------------------------
# Regression tests for root-level file operations (executor compatibility)
# ------------------------------------------------------------------

def test_root_level_file_write(tmp_path):
    """Root-level files can be written for executor compatibility."""
    root, boundary, executor = make_executor(tmp_path)

    # validate_write should succeed for root-level file
    file_path = root / "hello.txt"
    file_path.write_text("hello")
    validated = boundary.validate_write("hello.txt")
    assert validated == file_path


def test_root_level_file_read(tmp_path):
    """Root-level files can be read."""
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    validated = boundary.validate_read("hello.txt")
    assert validated == file_path


def test_root_level_file_delete(tmp_path):
    """Root-level files can be deleted (regression for delete_file('hello.txt'))."""
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # This was the failing case: delete_file("hello.txt")
    validated = boundary.validate_delete("hello.txt")
    assert validated == file_path


def test_root_level_file_copy(tmp_path):
    """Root-level files can be copied."""
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # copy_file uses validate_read for source, validate_write for destination
    src = boundary.validate_read("hello.txt")
    dst = boundary.validate_write("hello_copy.txt")
    assert src == file_path
    assert dst == root / "hello_copy.txt"


def test_root_level_file_rename(tmp_path):
    """Root-level files can be renamed."""
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # rename_file uses validate_write for both source and destination
    src = boundary.validate_write("hello.txt")
    dst = boundary.validate_write("hello_renamed.txt")
    assert src == file_path
    assert dst == root / "hello_renamed.txt"


def test_root_level_file_restore(tmp_path):
    """Root-level files can be restored from trash."""
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    executor.execute("delete_file", {"path": "hello.txt"})

    # restore_file uses validate_restore_destination which calls validate_write
    restored_dst = boundary.validate_restore_destination("hello.txt")
    assert restored_dst == file_path


def test_root_level_directory_create_rejected(tmp_path):
    """Arbitrary root-level directories cannot be created."""
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError, match="Arbitrary root-level directories are not allowed"):
        boundary.validate_create("new_dir")


def test_root_level_directory_write_allowed_for_files(tmp_path):
    """validate_write allows root-level paths (for file operations like copy/rename/delete)."""
    root, boundary, executor = make_executor(tmp_path)

    # validate_write allows root-level paths for file operations
    # We can't distinguish file vs directory for non-existent paths
    validated = boundary.validate_write("some_file.txt")
    assert validated == root / "some_file.txt"


def test_root_itself_not_writable(tmp_path):
    """The Fox Space root itself remains non-writable."""
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError, match="root is not writable"):
        boundary.validate_write("")


def test_root_itself_not_readable(tmp_path):
    """The Fox Space root itself remains non-readable."""
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(FoxSecurityError, match="root is not readable"):
        boundary.validate_read("")


