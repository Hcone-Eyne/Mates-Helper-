"""Tests for the brain <-> agent HTTP surface (brain/app.py).

Covers the task API the brain exposes (submit/list/health) and the fact that
the File Manager router is mounted next to it. Task persistence is redirected
to a temp database so nothing touches /data.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

TEST_TOKEN = "test-token"
AUTH = {"X-API-Token": TEST_TOKEN}
WRONG_AUTH = {"X-API-Token": "wrong-token"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from brain import task_store

    monkeypatch.setattr(task_store, "DB_PATH", str(tmp_path / "tasks.db"))
    monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)

    brain_app = pytest.importorskip("brain.app")
    return TestClient(brain_app.app)


class TestTaskApi:

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_submit_task_records_and_runs(self, client, monkeypatch):
        monkeypatch.setattr("brain.app.run_task", lambda desc, provider: "done: " + desc)

        response = client.post(
            "/submit_task", json={"description": "list files", "provider": "ollama"},
            headers=AUTH,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["result"] == "done: list files"
        assert isinstance(body["id"], int)

    def test_tasks_endpoint_lists_submitted_work(self, client, monkeypatch):
        monkeypatch.setattr("brain.app.run_task", lambda desc, provider: "ok")
        client.post("/submit_task", json={"description": "hello"}, headers=AUTH)

        response = client.get("/tasks", headers=AUTH)

        assert response.status_code == 200
        entries = response.json()
        assert entries[0]["description"] == "hello"
        assert entries[0]["status"] == "done"

    def test_submit_task_rejects_missing_description(self, client):
        response = client.post("/submit_task", json={}, headers=AUTH)
        assert response.status_code == 422

    def test_task_store_database_path_is_configurable(self):
        from brain import task_store

        assert isinstance(task_store.DB_PATH, str)
        assert "FOX_TASK_DB_PATH" in open(task_store.__file__).read()

    def test_a_failed_run_task_is_not_left_pending(self, client, monkeypatch):
        # submit_task used to wrap run_task in try/except/raise while only
        # ever calling complete_task on success, so a provider crash left the
        # task stuck at "pending" with no explanation.
        def explode(description, provider):
            raise RuntimeError("llm unavailable")

        monkeypatch.setattr("brain.app.run_task", explode)

        with pytest.raises(RuntimeError):
            client.post(
                "/submit_task",
                json={"description": "doomed", "provider": "ollama"},
                headers=AUTH,
            )

        entry = client.get("/tasks", headers=AUTH).json()[0]
        assert entry["status"] == "failed"
        assert "llm unavailable" in entry["result"]

    def test_a_successful_run_task_is_still_marked_done(self, client, monkeypatch):
        monkeypatch.setattr(
            "brain.app.run_task", lambda description, provider: "all good"
        )

        client.post("/submit_task", json={"description": "fine", "provider": "ollama"}, headers=AUTH)

        entry = client.get("/tasks", headers=AUTH).json()[0]
        assert entry["status"] == "done"
        assert entry["result"] == "all good"


class TestFileManagerRoutesMounted:

    def test_file_manager_health_is_reachable(self, client):
        response = client.get("/files/health")
        assert response.status_code == 200
        assert response.json()["service"] == "file-manager"

    def test_file_manager_routes_are_listed(self, client):
        paths = set(client.app.openapi()["paths"])
        assert {"/files/health", "/files/scan", "/files/search", "/files/delete"} <= paths

    def test_task_and_file_routes_share_one_app(self, client):
        paths = set(client.app.openapi()["paths"])
        assert "/submit_task" in paths
        assert "/tasks" in paths


class TestDestructiveFileEndpointIsConfined:
    """/files/delete is permanent (no trash), so it must stay inside the Vault."""

    def test_delete_outside_the_vault_is_rejected(self, client, tmp_path):
        outside = tmp_path / "not-in-the-vault.txt"
        outside.write_text("keep me")

        response = client.post("/files/delete", json={"path": str(outside)}, headers=AUTH)

        assert response.status_code == 400
        assert "outside the File Manager Vault" in response.json()["detail"]
        assert outside.exists(), "file outside the Vault must never be deleted"

    def test_delete_inside_the_vault_still_works(self, client, tmp_path, monkeypatch):
        import File_Manager.db as file_db
        from File_Manager.organizer import VAULT_ROOT

        monkeypatch.setattr(file_db, "DB_PATH", str(tmp_path / "index.db"))
        VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        victim = VAULT_ROOT / "_brain_api_delete_test.txt"
        victim.write_text("temp")

        try:
            response = client.post("/files/delete", json={"path": str(victim)}, headers=AUTH)
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert not victim.exists()
        finally:
            if victim.exists():
                victim.unlink()


class TestApiAuthorization:
    """Every mutating/task route requires the server-side API token.

    Health endpoints stay public. A missing server token, a missing client
    header, and a wrong token must all fail closed with HTTP 401 - and an
    unauthenticated delete must leave the Vault file untouched.
    """

    def test_unauthenticated_submit_task_is_rejected(self, client):
        response = client.post("/submit_task", json={"description": "hello"})
        assert response.status_code == 401
        assert TEST_TOKEN not in response.text

    def test_unauthenticated_tasks_is_rejected(self, client):
        assert client.get("/tasks").status_code == 401

    def test_unauthenticated_file_mutation_is_rejected(self, client, tmp_path):
        victim = tmp_path / "keep-me.txt"
        victim.write_text("keep me")

        for path, payload in [
            ("/files/delete", {"path": str(victim)}),
            ("/files/move", {"source": str(victim), "destination": str(victim)}),
            ("/files/copy", {"source": str(victim), "destination": str(victim)}),
            ("/files/rename", {"source": str(victim), "new_name": "x.txt"}),
            ("/files/folder", {"path": str(tmp_path / "new-dir")}),
            ("/files/scan", None),
        ]:
            response = client.post(path, json=payload) if payload is not None else client.post(path)
            assert response.status_code == 401, path
            assert TEST_TOKEN not in response.text

        assert victim.exists(), "unauthenticated delete must not touch the file"

    def test_invalid_token_is_rejected(self, client, tmp_path):
        victim = tmp_path / "keep-me.txt"
        victim.write_text("keep me")

        assert client.post(
            "/submit_task", json={"description": "hello"}, headers=WRONG_AUTH
        ).status_code == 401
        assert client.get("/tasks", headers=WRONG_AUTH).status_code == 401
        assert client.post(
            "/files/delete", json={"path": str(victim)}, headers=WRONG_AUTH
        ).status_code == 401
        assert victim.exists(), "wrong-token delete must not touch the file"

    def test_unconfigured_server_token_fails_closed(self, client, monkeypatch):
        monkeypatch.delenv("FOX_API_TOKEN", raising=False)

        assert client.post(
            "/submit_task", json={"description": "hello"}, headers=AUTH
        ).status_code == 401
        assert client.get("/tasks", headers=AUTH).status_code == 401

    def test_health_endpoints_remain_public(self, client):
        assert client.get("/health").status_code == 200
        assert client.get("/files/health").status_code == 200

    def test_authenticated_mutation_still_works(self, client, tmp_path, monkeypatch):
        import File_Manager.db as file_db
        from File_Manager.organizer import VAULT_ROOT

        monkeypatch.setattr(file_db, "DB_PATH", str(tmp_path / "index.db"))
        VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        target = VAULT_ROOT / "_brain_api_auth_test_dir"
        if target.exists():
            import shutil
            shutil.rmtree(target)

        try:
            response = client.post("/files/folder", json={"path": str(target)}, headers=AUTH)
            assert response.status_code == 200
            assert target.is_dir()
        finally:
            if target.exists():
                import shutil
                shutil.rmtree(target)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
