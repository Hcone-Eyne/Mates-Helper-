from pathlib import Path

import pytest

from agent.fox.security import (
    FoxSecurityBoundary,
    FoxSecurityError,
    PathEscapeError,
    PrivilegedActionError,
    SymlinkEscapeError,
)


@pytest.fixture
def fox_security():
    """Fixture that provides security classes for each test."""
    return FoxSecurityBoundary, FoxSecurityError, PathEscapeError, PrivilegedActionError, SymlinkEscapeError

import pytest

from agent.fox.runtime.executor import FileActionExecutor


def make_executor(tmp_path: Path, fox_security):
    FoxSecurityBoundary, _, _, _, _ = fox_security
    root = tmp_path / "fox"
    boundary = FoxSecurityBoundary(root)
    executor = FileActionExecutor(boundary)
    return root, boundary, executor


def test_empty_trash_rejects_confirm_boolean(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_empty_trash_rejects_missing_authorization(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_empty_trash_accepts_boundary_authorization(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_parent_traversal_rejected(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    with pytest.raises(PathEscapeError):
        boundary.validate_path("../outside.txt")


def test_absolute_outside_path_rejected(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    with pytest.raises(PathEscapeError):
        boundary.validate_path(outside)


def test_absolute_alias_outside_root_allowed(tmp_path, fox_security):
    FoxSecurityBoundary, _, _, _, _ = fox_security
    root = tmp_path / "fox"
    root.mkdir()

    alias = tmp_path / "fox_alias"
    alias.symlink_to(root, target_is_directory=True)
    
    boundary = FoxSecurityBoundary(root)

    # The symlink is outside the root but points inside - should be allowed
    # because the resolved path is inside the Fox Space
    result = boundary.validate_path(alias / "secret.txt")
    assert result.is_relative_to(root)


def test_similar_prefix_path_rejected(tmp_path, fox_security):
    root = tmp_path / "fox"
    similar = tmp_path / "fox_evil"

    root.mkdir()
    similar.mkdir()

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(PathEscapeError):
        boundary.validate_path(similar / "secret.txt")


def test_symlink_escape_rejected(tmp_path, fox_security):
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


def test_nested_symlink_escape_rejected(tmp_path, fox_security):
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


def test_broken_symlink_rejected(tmp_path, fox_security):
    root = tmp_path / "fox"
    root.mkdir()

    link = root / "broken"
    link.symlink_to(
        root / "does-not-exist"
    )

    boundary = FoxSecurityBoundary(root)

    with pytest.raises(SymlinkEscapeError):
        boundary.validate_path(link)


def test_macos_tmp_symlink_alias_accepted(tmp_path, fox_security):
    """
    Regression test for macOS /tmp -> /private/tmp symlink.

    On macOS, /tmp is a symlink to /private/tmp. When the Fox root is created
    at /tmp/fox, its resolved path becomes /private/tmp/fox. A candidate path
    supplied through the /tmp alias (e.g., /tmp/fox/workspace/file.txt) must be
    accepted even though it's lexically different from the resolved root.
    """
    FoxSecurityBoundary, _, _, _, _ = fox_security

    # Simulate macOS structure: /private/tmp exists, /tmp -> /private/tmp
    private_tmp = tmp_path / "private" / "tmp"
    private_tmp.mkdir(parents=True)

    tmp_link = tmp_path / "tmp"
    tmp_link.symlink_to(private_tmp, target_is_directory=True)

    # Fox root created at /tmp/fox (non-resolved path)
    root = tmp_link / "fox"
    root.mkdir()

    boundary = FoxSecurityBoundary(root)

    # Candidate via /tmp alias should be accepted
    candidate_via_tmp = tmp_link / "fox" / "workspace" / "test.txt"
    candidate_via_tmp.parent.mkdir(parents=True, exist_ok=True)
    candidate_via_tmp.write_text("test")

    validated = boundary.validate_path(candidate_via_tmp)
    assert validated.is_relative_to(boundary.root_resolved)

    # Candidate via /private/tmp (resolved form) should also be accepted
    candidate_via_private = private_tmp / "fox" / "workspace" / "test2.txt"
    candidate_via_private.parent.mkdir(parents=True, exist_ok=True)
    candidate_via_private.write_text("test2")

    validated2 = boundary.validate_path(candidate_via_private)
    assert validated2.is_relative_to(boundary.root_resolved)


def test_macos_tmp_internal_symlink_accepted(tmp_path, fox_security):
    """
    Regression test for internal symlinks under macOS /tmp structure.

    A symlink inside the Fox root that points to another location inside the
    same root (via the resolved /private/tmp path) must be accepted.
    """
    FoxSecurityBoundary, _, _, _, _ = fox_security

    # Simulate macOS structure
    private_tmp = tmp_path / "private" / "tmp"
    private_tmp.mkdir(parents=True)

    tmp_link = tmp_path / "tmp"
    tmp_link.symlink_to(private_tmp, target_is_directory=True)

    # Fox root at /tmp/fox
    root = tmp_link / "fox"
    root.mkdir()

    # Create a directory inside the root via resolved path
    inner_dir = private_tmp / "fox" / "inner"
    inner_dir.mkdir(parents=True)
    (inner_dir / "file.txt").write_text("content")

    # Create a symlink inside the root (via /tmp alias) pointing to the inner directory
    link = tmp_link / "fox" / "link_to_inner"
    link.symlink_to(inner_dir, target_is_directory=True)

    boundary = FoxSecurityBoundary(root)

    # Access through the symlink should be accepted (target is inside Fox root)
    candidate = tmp_link / "fox" / "link_to_inner" / "file.txt"
    validated = boundary.validate_path(candidate)
    assert validated.is_relative_to(boundary.root_resolved)


def test_macos_tmp_external_symlink_rejected(tmp_path, fox_security):
    """
    Regression test: external symlinks under macOS /tmp structure are still rejected.

    A symlink inside the Fox root that points outside the root must be rejected,
    even when using the macOS /tmp -> /private/tmp alias structure.
    """
    FoxSecurityBoundary, _, _, _, _ = fox_security

    # Simulate macOS structure
    private_tmp = tmp_path / "private" / "tmp"
    private_tmp.mkdir(parents=True)

    tmp_link = tmp_path / "tmp"
    tmp_link.symlink_to(private_tmp, target_is_directory=True)

    # Fox root at /tmp/fox
    root = tmp_link / "fox"
    root.mkdir()

    # Create an outside directory
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")

    # Create a symlink inside the root pointing outside
    link = tmp_link / "fox" / "escape_link"
    link.symlink_to(outside, target_is_directory=True)

    boundary = FoxSecurityBoundary(root)

    # Access through the symlink should be rejected
    candidate = tmp_link / "fox" / "escape_link" / "secret.txt"
    with pytest.raises(SymlinkEscapeError):
        boundary.validate_path(candidate)


def test_delete_trash_destination_stays_inside_root(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_restore_default_destination_is_inside_root(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_search_limit_must_be_integer(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError):
        executor.execute(
            "search_files",
            {
                "query": "test",
                "limit": "100",
            },
        )


def test_search_limit_must_be_positive(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError):
        executor.execute(
            "search_files",
            {
                "query": "test",
                "limit": 0,
            },
        )


def test_filename_traversal_rejected(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_empty_trash_only_operates_inside_trash(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

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


def test_boundary_root_cannot_be_changed(tmp_path, fox_security):
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError):
        boundary._root = tmp_path / "evil"

    with pytest.raises(FoxSecurityError):
        boundary._trash_dir = tmp_path / "evil-trash"

def test_get_area_workspace(tmp_path, fox_security):
    FoxSecurityBoundary, _, _, _, _ = fox_security
    boundary = FoxSecurityBoundary(tmp_path / "fox")

    path = boundary.root / "workspace" / "test.txt"

    assert boundary.get_area(path) == "workspace"


def test_get_area_system(tmp_path, fox_security):
    FoxSecurityBoundary, _, _, _, _ = fox_security
    boundary = FoxSecurityBoundary(tmp_path / "fox")

    path = boundary.root / "system" / "runtime.json"

    assert boundary.get_area(path) == "system"


# ------------------------------------------------------------------
# Regression tests for root-level file operations (executor compatibility)
# ------------------------------------------------------------------

def test_root_level_file_write(tmp_path, fox_security):
    """Root-level files can be written for executor compatibility."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    # validate_write should succeed for root-level file
    file_path = root / "hello.txt"
    file_path.write_text("hello")
    validated = boundary.validate_write("hello.txt")
    assert validated == file_path


def test_root_level_file_read(tmp_path, fox_security):
    """Root-level files can be read."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    validated = boundary.validate_read("hello.txt")
    assert validated == file_path


def test_root_level_file_delete(tmp_path, fox_security):
    """Root-level files can be deleted (regression for delete_file('hello.txt'))."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # This was the failing case: delete_file("hello.txt")
    validated = boundary.validate_delete("hello.txt")
    assert validated == file_path


def test_root_level_file_copy(tmp_path, fox_security):
    """Root-level files can be copied."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # copy_file uses validate_read for source, validate_write for destination
    src = boundary.validate_read("hello.txt")
    dst = boundary.validate_write("hello_copy.txt")
    assert src == file_path
    assert dst == root / "hello_copy.txt"


def test_root_level_file_rename(tmp_path, fox_security):
    """Root-level files can be renamed."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    # rename_file uses validate_write for both source and destination
    src = boundary.validate_write("hello.txt")
    dst = boundary.validate_write("hello_renamed.txt")
    assert src == file_path
    assert dst == root / "hello_renamed.txt"


def test_root_level_file_restore(tmp_path, fox_security):
    """Root-level files can be restored from trash."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    executor.execute("delete_file", {"path": "hello.txt"})

    # restore_file uses validate_restore_destination which calls validate_write
    restored_dst = boundary.validate_restore_destination("hello.txt")
    assert restored_dst == file_path


def test_root_level_directory_create_rejected(tmp_path, fox_security):
    """Arbitrary root-level directories cannot be created."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError, match="Arbitrary root-level directories are not allowed"):
        boundary.validate_create("new_dir")


def test_root_level_directory_write_allowed_for_files(tmp_path, fox_security):
    """validate_write allows root-level paths (for file operations like copy/rename/delete)."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    # validate_write allows root-level paths for file operations
    # We can't distinguish file vs directory for non-existent paths
    validated = boundary.validate_write("some_file.txt")
    assert validated == root / "some_file.txt"


def test_root_itself_not_writable(tmp_path, fox_security):
    """The Fox Space root itself remains non-writable."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError, match="root is not writable"):
        boundary.validate_write("")


def test_root_itself_not_readable(tmp_path, fox_security):
    """The Fox Space root itself remains non-readable."""
    root, boundary, executor = make_executor(tmp_path, fox_security)

    with pytest.raises(FoxSecurityError, match="root is not readable"):
        boundary.validate_read("")


