"""Tests for FoxDirectoryPolicy."""

from pathlib import Path

import pytest

from agent.fox.security.policy import FoxDirectoryPolicy, FoxPolicyError


class TestFoxDirectoryPolicy:
    """Test FoxDirectoryPolicy class."""

    @pytest.fixture
    def policy(self, tmp_path):
        return FoxDirectoryPolicy(tmp_path / "fox")

    def test_area_read_only(self, policy):
        assert policy.area("system") == "system"
        assert policy.area("apps") == "apps"
        assert policy.area("config") == "config"

    def test_area_writable(self, policy):
        assert policy.area("workspace") == "workspace"
        assert policy.area("storage") == "storage"

    def test_area_rejects_reserved(self, policy):
        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            policy.area(".fox_trash")

        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            policy.area("trash")

    def test_area_rejects_unknown(self, policy):
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            policy.area("unknown_dir")

    def test_validate_read_read_only(self, policy):
        path = policy.validate_read("system/file.txt")
        assert "system" in str(path)

    def test_validate_read_writable(self, policy):
        path = policy.validate_read("workspace/file.txt")
        assert "workspace" in str(path)

    def test_validate_read_rejects_root(self, policy):
        with pytest.raises(FoxPolicyError, match="root is not readable"):
            policy.validate_read("")

    def test_validate_read_rejects_reserved(self, policy):
        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            policy.validate_read(".fox_trash/file.txt")

    def test_validate_write_writable(self, policy):
        path = policy.validate_write("workspace/file.txt")
        assert "workspace" in str(path)

    def test_validate_write_rejects_root(self, policy):
        with pytest.raises(FoxPolicyError, match="root is not writable"):
            policy.validate_write("")

    def test_validate_write_rejects_read_only(self, policy):
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            policy.validate_write("system/file.txt")

    def test_validate_write_rejects_reserved(self, policy):
        with pytest.raises(FoxPolicyError, match="trash is controlled internally"):
            policy.validate_write(".fox_trash/file.txt")

    def test_validate_write_rejects_unknown(self, policy):
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged"):
            policy.validate_write("unknown/file.txt")

    def test_validate_create(self, policy):
        path = policy.validate_create("workspace/new.txt")
        assert "workspace" in str(path)

    def test_validate_delete(self, policy):
        path = policy.validate_delete("workspace/file.txt")
        assert "workspace" in str(path)

    def test_validate_move_source(self, policy):
        path = policy.validate_move_source("workspace/file.txt")
        assert "workspace" in str(path)

    def test_validate_copy_source(self, policy):
        path = policy.validate_copy_source("system/file.txt")
        assert "system" in str(path)

    def test_validate_organise_target_writable(self, policy):
        # Create the workspace directory in the policy root to avoid cwd conflicts
        workspace_dir = policy.root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = policy.validate_organise_target("workspace/test_organise.txt")
        assert "workspace" in str(path)

    def test_validate_organise_target_rejects_read_only(self, policy):
        with pytest.raises(FoxPolicyError, match="Unknown or unmanaged Fox Space directory: system"):
            policy.validate_organise_target("system/file.txt")

    def test_validate_restore_destination(self, policy):
        path = policy.validate_restore_destination("workspace/file.txt")
        assert "workspace" in str(path)

    def test_writable_alias(self):
        assert FoxDirectoryPolicy.WRITABLE_DIRS == FoxDirectoryPolicy.WRITEABLE_DIRS

    def test_relative_path_handling(self, policy):
        path = policy.validate_write("workspace/subdir/file.txt")
        assert "workspace" in str(path)
        assert "subdir" in str(path)


class TestFoxDirectoryPolicyEdgeCases:
    """Edge case tests for FoxDirectoryPolicy."""

    def test_reserved_dirs_case_sensitive(self, tmp_path):
        policy = FoxDirectoryPolicy(tmp_path)
        with pytest.raises(FoxPolicyError):
            policy.area(".FOX_TRASH")

    def test_traversal_rejected(self, tmp_path):
        policy = FoxDirectoryPolicy(tmp_path)
        with pytest.raises(FoxPolicyError):
            policy.validate_write("../outside.txt")