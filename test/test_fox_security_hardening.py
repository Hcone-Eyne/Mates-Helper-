from pathlib import Path

import pytest

from agent.fox.runtime.executor import FileActionExecutor
from agent.fox.security import (
    FoxSecurityBoundary,
    FoxSecurityError,
    PathEscapeError,
    PrivilegedActionError,
    SymlinkEscapeError,
)


def make_executor(tmp_path: Path):
    root = tmp_path / "fox"
    boundary = FoxSecurityBoundary(root)
    executor = FileActionExecutor(boundary)
    return root, boundary, executor


def test_empty_trash_rejects_confirm_boolean(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "hello.txt"},
    )

    with pytest.raises(PrivilegedActionError):
        executor.execute(
            "empty_trash",
            {"confirm": True},
        )


def test_empty_trash_rejects_missing_authorization(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    with pytest.raises(PrivilegedActionError):
        executor.execute(
            "empty_trash",
            {},
        )


def test_empty_trash_accepts_boundary_authorization(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "hello.txt"},
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

    file_path = root / "hello.txt"
    file_path.write_text("hello")

    result = executor.execute(
        "delete_file",
        {"path": "hello.txt"},
    )

    trash_path = root / result["trash_path"]

    assert trash_path.exists()
    assert trash_path.is_file()
    assert trash_path.is_relative_to(root)


def test_restore_default_destination_is_inside_root(tmp_path):
    root, boundary, executor = make_executor(tmp_path)

    original = root / "folder" / "hello.txt"
    original.parent.mkdir()
    original.write_text("hello")

    executor.execute(
        "delete_file",
        {"path": "folder/hello.txt"},
    )

    result = executor.execute(
        "restore_file",
        {
            "path": ".fox_trash/folder/hello.txt"
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

    assert boundary._get_area(path) == "workspace"


def test_get_area_system(tmp_path):
    boundary = FoxSecurityBoundary(tmp_path / "fox")

    path = boundary.root / "system" / "runtime.json"

    assert boundary._get_area(path) == "system"


