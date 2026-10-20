"""Regression tests for Vault recoverable deletion and restoration (Task 1).

Covers:
- Vault delete moves files into recoverable `.fox_trash` via shared Fox executor
- Deleted files do not remain at their original path and are removed from DB
- Scanner ignores `.fox_trash` so trashed files are not re-indexed
- Restore returns files to original location with intact contents and re-indexes DB
- Restore handles filename collisions without overwriting existing user data
- Trash handles repeated deletions of the same path without overwriting
- Path traversal, outside-Vault paths, and empty paths are rejected
- Symlink escapes (external file symlink, external dir symlink, broken symlink,
  internal symlink) are rejected without deleting target files
- Vault root and directories cannot be deleted
- Missing files and filesystem failures raise errors and never fall back to unlink
- HTTP `/files/delete` and `/files/restore` enforce X-API-Token authentication
- Shared Fox Club `FileActionExecutor` continues enforcing Fox Space area policy
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import File_Manager.db as fm_db
import File_Manager.modify_files as fm_mod
import File_Manager.organizer as fm_org
import File_Manager.scanner as fm_scanner
from agent.fox.runtime.executor import FileActionExecutor
from agent.fox.security import FoxPolicyError, FoxSecurityBoundary
from brain.app import app

TEST_TOKEN = "test-vault-trash-token-998877"


@pytest.fixture
def isolated_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect Vault root and SQLite index DB to an isolated temporary directory."""
    vault = tmp_path / "Vault"
    vault.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "file_index.db"

    monkeypatch.setattr(fm_org, "VAULT_ROOT", vault)
    monkeypatch.setattr(fm_mod, "VAULT_ROOT", vault)
    monkeypatch.setattr(fm_scanner, "VAULT_ROOT", vault)
    monkeypatch.setattr(fm_db, "DB_PATH", db_path)
    fm_db.get_connection().close()
    return vault


@pytest.fixture
def authed_client(
    isolated_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
    return TestClient(app)


class TestVaultTrashAndRestoreUnit:
    def test_delete_moves_file_to_trash_and_restore_recovers_it(
        self, isolated_vault: Path
    ) -> None:
        doc = isolated_vault / "Documents" / "report.txt"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("quarterly numbers: 42", encoding="utf-8")
        fm_scanner.scan_file(doc)
        assert fm_db.get_file(doc) is not None

        trash_path = fm_mod.delete_file(doc)

        # Deleted file is removed from original location and DB, but preserved in trash
        assert not doc.exists()
        assert fm_db.get_file(doc) is None
        assert trash_path.exists()
        assert trash_path.read_text(encoding="utf-8") == "quarterly numbers: 42"
        assert isolated_vault / ".fox_trash" in trash_path.parents

        # Scanner does not re-index trashed files
        fm_scanner.scan()
        assert fm_db.get_file(trash_path) is None

        # Restore by original path returns file and re-indexes it
        restored = fm_mod.restore_file(doc)
        assert restored == doc.resolve()
        assert doc.exists()
        assert not trash_path.exists()
        assert doc.read_text(encoding="utf-8") == "quarterly numbers: 42"
        assert fm_db.get_file(doc) is not None

    def test_restore_accepts_trash_path_directly(self, isolated_vault: Path) -> None:
        note = isolated_vault / "Documents" / "notes.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("# Important note", encoding="utf-8")

        trash_path = fm_mod.delete_file(note)
        assert not note.exists()

        restored = fm_mod.restore_file(trash_path)
        assert restored == note.resolve()
        assert note.exists()
        assert note.read_text(encoding="utf-8") == "# Important note"

    def test_restore_collision_does_not_overwrite_existing_file(
        self, isolated_vault: Path
    ) -> None:
        target = isolated_vault / "Documents" / "budget.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("original v1", encoding="utf-8")

        trash_path = fm_mod.delete_file(target)
        assert not target.exists()

        # A new file is created at the original location before restore
        target.write_text("replacement v2", encoding="utf-8")

        restored = fm_mod.restore_file(trash_path)
        assert restored != target.resolve()
        assert restored.name == "budget_1.txt"
        assert target.read_text(encoding="utf-8") == "replacement v2"
        assert restored.read_text(encoding="utf-8") == "original v1"
        assert fm_db.get_file(restored) is not None

    def test_repeated_delete_of_same_path_preserves_both_in_trash(
        self, isolated_vault: Path
    ) -> None:
        item = isolated_vault / "Documents" / "draft.txt"
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text("first draft", encoding="utf-8")
        trash_1 = fm_mod.delete_file(item)

        item.write_text("second draft", encoding="utf-8")
        trash_2 = fm_mod.delete_file(item)

        assert trash_1 != trash_2
        assert trash_1.read_text(encoding="utf-8") == "first draft"
        assert trash_2.read_text(encoding="utf-8") == "second draft"

        # Restoring by original path restores the most recently trashed copy
        restored_latest = fm_mod.restore_file(item)
        assert restored_latest == item.resolve()
        assert item.read_text(encoding="utf-8") == "second draft"

        # Restoring the earlier trash entry does not overwrite the restored file
        restored_first = fm_mod.restore_file(trash_1)
        assert restored_first.name == "draft_1.txt"
        assert restored_first.read_text(encoding="utf-8") == "first draft"
        assert item.read_text(encoding="utf-8") == "second draft"

    def test_rejects_traversal_and_outside_paths(
        self, isolated_vault: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside_secret.txt"
        outside.write_text("do not touch", encoding="utf-8")

        for bad_path in (
            outside,
            isolated_vault / ".." / "outside_secret.txt",
            "../outside_secret.txt",
            "../../etc/passwd",
            "",
            "   ",
        ):
            with pytest.raises(ValueError):
                fm_mod.delete_file(bad_path)
            with pytest.raises(ValueError):
                fm_mod.restore_file(bad_path)

        assert outside.exists()
        assert outside.read_text(encoding="utf-8") == "do not touch"

    def test_rejects_symlink_escapes(
        self, isolated_vault: Path, tmp_path: Path
    ) -> None:
        outside_file = tmp_path / "host_file.txt"
        outside_file.write_text("host content", encoding="utf-8")

        outside_dir = tmp_path / "host_dir"
        outside_dir.mkdir()
        nested_outside = outside_dir / "nested.txt"
        nested_outside.write_text("nested host content", encoding="utf-8")

        inside_target = isolated_vault / "Documents" / "real.txt"
        inside_target.parent.mkdir(parents=True, exist_ok=True)
        inside_target.write_text("real vault file", encoding="utf-8")

        # 1. Leaf symlink to outside file
        ext_link = isolated_vault / "Documents" / "ext_link.txt"
        ext_link.symlink_to(outside_file)
        with pytest.raises(ValueError):
            fm_mod.delete_file(ext_link)
        assert outside_file.exists()

        # 2. Intermediate symlinked directory to outside directory
        dir_link = isolated_vault / "Documents" / "linked_dir"
        dir_link.symlink_to(outside_dir)
        with pytest.raises(ValueError):
            fm_mod.delete_file(dir_link / "nested.txt")
        assert nested_outside.exists()

        # 3. Broken symlink
        broken_link = isolated_vault / "Documents" / "broken.txt"
        broken_link.symlink_to(tmp_path / "nonexistent_target.txt")
        with pytest.raises(ValueError):
            fm_mod.delete_file(broken_link)

        # 4. Internal symlink pointing to another file inside Vault
        int_link = isolated_vault / "Documents" / "int_link.txt"
        int_link.symlink_to(inside_target)
        with pytest.raises(ValueError):
            fm_mod.delete_file(int_link)
        assert inside_target.exists()

    def test_rejects_vault_root_and_directory_deletion(
        self, isolated_vault: Path
    ) -> None:
        subdir = isolated_vault / "Documents"
        subdir.mkdir(parents=True, exist_ok=True)
        keep = subdir / "keep.txt"
        keep.write_text("still here", encoding="utf-8")

        for dir_target in (isolated_vault, ".", subdir, "Documents"):
            with pytest.raises(IsADirectoryError):
                fm_mod.delete_file(dir_target)

        assert isolated_vault.exists()
        assert subdir.exists()
        assert keep.exists()

    def test_missing_file_and_filesystem_failure_never_fallback_to_unlink(
        self, isolated_vault: Path
    ) -> None:
        missing = isolated_vault / "Documents" / "ghost.txt"
        with pytest.raises(FileNotFoundError):
            fm_mod.delete_file(missing)
        with pytest.raises(FileNotFoundError):
            fm_mod.restore_file(missing)

        # Simulate OS-level failure during move to trash
        real_file = isolated_vault / "Documents" / "precious.txt"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text("cannot lose this", encoding="utf-8")
        fm_scanner.scan_file(real_file)

        with patch("agent.fox.runtime.executor.shutil.move", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                fm_mod.delete_file(real_file)

        # File and DB record must remain untouched when trash fails
        assert real_file.exists()
        assert real_file.read_text(encoding="utf-8") == "cannot lose this"
        assert fm_db.get_file(real_file) is not None


class TestVaultTrashAndRestoreHTTP:
    def test_http_delete_and_restore_roundtrip(
        self, authed_client: TestClient, isolated_vault: Path
    ) -> None:
        doc = isolated_vault / "Documents" / "api_doc.txt"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("api payload", encoding="utf-8")
        fm_scanner.scan_file(doc)

        del_res = authed_client.post(
            "/files/delete",
            json={"path": str(doc)},
            headers={"X-API-Token": TEST_TOKEN},
        )
        assert del_res.status_code == 200
        body = del_res.json()
        assert body["success"] is True
        assert body["trashed"] is True
        assert not doc.exists()
        assert Path(body["trash_path"]).exists()

        res_res = authed_client.post(
            "/files/restore",
            json={"path": str(doc)},
            headers={"X-API-Token": TEST_TOKEN},
        )
        assert res_res.status_code == 200
        res_body = res_res.json()
        assert res_body["success"] is True
        assert Path(res_body["restored_to"]) == doc.resolve()
        assert doc.exists()
        assert doc.read_text(encoding="utf-8") == "api payload"

    def test_http_delete_and_restore_reject_unauthorized(
        self, isolated_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        doc = isolated_vault / "Documents" / "protected.txt"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("secret", encoding="utf-8")

        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        client = TestClient(app)

        for endpoint in ("/files/delete", "/files/restore"):
            # Missing header
            assert client.post(endpoint, json={"path": str(doc)}).status_code == 401
            # Wrong token
            assert (
                client.post(
                    endpoint,
                    json={"path": str(doc)},
                    headers={"X-API-Token": "wrong-token"},
                ).status_code
                == 401
            )

        # Unset FOX_API_TOKEN fails closed
        monkeypatch.delenv("FOX_API_TOKEN", raising=False)
        for endpoint in ("/files/delete", "/files/restore"):
            assert (
                client.post(
                    endpoint,
                    json={"path": str(doc)},
                    headers={"X-API-Token": TEST_TOKEN},
                ).status_code
                == 401
            )

        assert doc.exists()

    def test_http_delete_and_restore_reject_invalid_paths(
        self, authed_client: TestClient, isolated_vault: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("outside", encoding="utf-8")

        for endpoint in ("/files/delete", "/files/restore"):
            r_out = authed_client.post(
                endpoint,
                json={"path": str(outside)},
                headers={"X-API-Token": TEST_TOKEN},
            )
            assert r_out.status_code == 400

            r_root = authed_client.post(
                endpoint,
                json={"path": str(isolated_vault)},
                headers={"X-API-Token": TEST_TOKEN},
            )
            assert r_root.status_code == 400

        assert outside.exists()


class TestFoxClubTrashCompatibility:
    def test_fox_club_boundary_and_executor_remain_intact(
        self, tmp_path: Path
    ) -> None:
        fox_root = tmp_path / "fox_space"
        boundary = FoxSecurityBoundary(fox_root, create=True)
        executor = FileActionExecutor(boundary)

        # Standard Fox Space workspace delete + restore works
        executor.execute("create_folder", {"path": "workspace/notes"})
        todo_path = fox_root / "workspace" / "notes" / "todo.txt"
        todo_path.write_text("buy coffee", encoding="utf-8")
        del_result = executor.execute(
            "delete_file", {"path": "workspace/notes/todo.txt"}
        )
        assert not (fox_root / "workspace/notes/todo.txt").exists()
        assert (fox_root / del_result["trash_path"]).exists()

        res_result = executor.execute(
            "restore_file", {"path": del_result["trash_path"]}
        )
        assert res_result["restored_to"] == "workspace/notes/todo.txt"
        assert (fox_root / "workspace/notes/todo.txt").read_text(
            encoding="utf-8"
        ) == "buy coffee"

        # Strict Fox Space area policy still blocks deleting from system/
        sys_file = fox_root / "system" / "kernel.cfg"
        sys_file.parent.mkdir(parents=True, exist_ok=True)
        sys_file.write_text("locked", encoding="utf-8")
        with pytest.raises(FoxPolicyError):
            executor.execute("delete_file", {"path": "system/kernel.cfg"})
        assert sys_file.exists()


class TestTrashDurabilityAndConcurrency:
    def test_trash_metadata_persists_across_restart(
        self, isolated_vault: Path
    ) -> None:
        from agent.fox.runtime import executor as ex

        test_file = isolated_vault / "Documents" / "reboot_doc.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("survives restart", encoding="utf-8")
        fm_scanner.scan_file(test_file)

        trash_path = fm_mod.delete_file(test_file)
        assert trash_path.exists()
        assert not test_file.exists()

        # Wipe in-memory caches to simulate server restart / worker recycle
        ex._TRASH_METADATA.clear()
        ex._ORIGINAL_TO_TRASH.clear()

        # Restore using the trash path
        restored = fm_mod.restore_file(trash_path)
        assert restored == test_file
        assert restored.exists()
        assert restored.read_text(encoding="utf-8") == "survives restart"

    def test_concurrent_restores_resolve_collisions_safely(
        self, isolated_vault: Path
    ) -> None:
        import threading
        from agent.fox.runtime import executor as ex

        doc = isolated_vault / "Documents" / "parallel_doc.txt"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("content_alpha", encoding="utf-8")
        fm_scanner.scan_file(doc)
        trash_a = fm_mod.delete_file(doc)

        doc.write_text("content_beta", encoding="utf-8")
        fm_scanner.scan_file(doc)
        trash_b = fm_mod.delete_file(doc)

        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def worker(trash_p: Path) -> None:
            try:
                barrier.wait(timeout=5)
                fm_mod.restore_file(trash_p)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker, args=(trash_a,))
        t2 = threading.Thread(target=worker, args=(trash_b,))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors
        restored_files = sorted(p for p in (isolated_vault / "Documents").iterdir() if p.is_file())
        assert len(restored_files) == 2
        contents = {p.read_text(encoding="utf-8") for p in restored_files}
        assert contents == {"content_alpha", "content_beta"}

