"""Static checks for the Docker build of the brain service.

Docker itself is not available in every environment, so these tests assert the
strongest things that can be checked without a daemon:

1. compose still builds the brain from the repository root (it needs
   File_Manager/ and agent/, which live outside brain/),
2. the Dockerfile copies exactly the trees the brain imports,
3. a copy of that image layout can actually import `brain.app` - i.e. the image
   is structurally capable of starting its CMD.

Offline verification of the real build (no daemon required) was done once by
installing exactly the Dockerfile's pip line into a fresh venv and running the
layout import above with that interpreter - it succeeded. Re-running that by
hand needs network access, so it is not part of the suite.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
COMPOSE = REPO / "docker-compose.yml"
DOCKERFILE = REPO / "brain" / "Dockerfile"
DOCKERIGNORE = REPO / ".dockerignore"


@pytest.fixture(scope="module")
def compose():
    with COMPOSE.open() as fh:
        return yaml.safe_load(fh)


class TestComposeBuild:
    def test_brain_build_uses_repo_root_context(self, compose):
        # ./brain cannot see File_Manager/ or agent/, so the context must be root.
        assert compose["services"]["brain"]["build"] == {
            "context": ".",
            "dockerfile": "brain/Dockerfile",
        }

    def test_brain_still_publishes_exactly_one_port(self, compose):
        # Loopback binding itself is asserted in test_config.py.
        ports = compose["services"]["brain"]["ports"]
        assert len(ports) == 1
        assert ports[0].startswith("127.0.0.1:")

    def test_other_services_still_publish_nothing(self, compose):
        for service in ("agent", "mitm-proxy"):
            assert "ports" not in compose["services"][service], service

    def test_network_and_cap_model_unchanged(self, compose):
        assert compose["services"]["agent"]["cap_add"] == ["NET_ADMIN"]
        assert "volumes" not in compose["services"]["agent"]
        for service in ("agent", "mitm-proxy", "brain"):
            assert compose["services"][service]["networks"] == ["sandbox-net"]


class TestDockerfile:
    def test_copies_every_tree_the_brain_imports(self):
        text = DOCKERFILE.read_text()
        for copy in ("COPY brain/", "COPY File_Manager/", "COPY agent/"):
            assert copy in text, f"missing: {copy}"
        # agent/ollama/tools.py lazily imports these when finance/schedule
        # tools execute - without them the tools fail inside the container.
        for copy in ("COPY Memory/", "COPY Finance_bot/", "COPY bot.py Path_mapper.py"):
            assert copy in text, f"missing: {copy}"

    def test_entrypoint_uses_package_module_path(self):
        text = DOCKERFILE.read_text()
        # Files are copied as packages, not flattened: app.py does
        # `from brain import task_store`, so `uvicorn app:app` would not import.
        assert '"uvicorn", "brain.app:app"' in text
        assert "ENV PYTHONPATH=/app" in text

    def test_installs_the_import_closure_dependencies(self):
        text = DOCKERFILE.read_text()
        for package in (
            "fastapi",
            "uvicorn",
            "anthropic",
            "requests",
            "pandas",
            "rich",
        ):
            assert package in text, f"Dockerfile does not install {package}"

    def test_dockerignore_keeps_the_context_small(self):
        text = DOCKERIGNORE.read_text()
        for pattern in ("venv/", ".git", "**/__pycache__/", "logs/", "data/", "test/"):
            assert pattern in text, f".dockerignore misses {pattern}"

    def test_dockerignore_excludes_user_data_and_host_state(self):
        # The Vault holds user files; file_index.db and user_profs.json hold
        # absolute host paths. Baking any of them into the image would leak
        # user data and ship a stale, wrong-path index.
        text = DOCKERIGNORE.read_text()
        for pattern in (
            "File_Manager/Vault/",
            "File_Manager/file_index.db",
            "File_Manager/user_profs.json",
        ):
            assert pattern in text, f".dockerignore misses {pattern}"


def _build_image_layout(tmp_path: Path) -> Path:
    """Copy the same trees the Dockerfile copies into a fake image root."""
    for tree in ("brain", "File_Manager", "agent", "Memory", "Finance_bot"):
        shutil.copytree(
            REPO / tree,
            tmp_path / tree,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
    for module in ("bot.py", "Path_mapper.py"):
        shutil.copy2(REPO / module, tmp_path / module)
    return tmp_path


class TestImageLayoutImports:
    def test_brain_app_imports_in_image_layout(self, tmp_path):
        """The container layout must be able to import what uvicorn starts."""
        root = _build_image_layout(tmp_path)

        script = (
            "import brain.app\n"
            "from fastapi import FastAPI\n"
            "assert isinstance(brain.app.app, FastAPI), 'uvicorn target missing'\n"
            "print('IMPORT_OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            "image layout cannot import brain.app\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "IMPORT_OK" in result.stdout

    def test_image_layout_has_no_flattened_app_module(self):
        # Guards the regression this file exists to prevent: the old image
        # copied app.py to /app/app.py while app.py imports `brain.*`.
        text = DOCKERFILE.read_text()
        assert "COPY app.py" not in text

    def test_lazy_tool_trees_import_in_image_layout(self, tmp_path):
        """agent/ollama/tools.py lazily imports these at tool-execution time.

        They are not needed for `import brain.app`, but finance/schedule
        tool calls fail inside the container without them - so the layout
        must provide them.
        """
        root = _build_image_layout(tmp_path)

        script = (
            "from Finance_bot.operations_finder import operation_finder\n"
            "from Memory.memory_storer import memory_catcher\n"
            "from bot import query_handler\n"
            "from Path_mapper import SCHEDULE_CSV\n"
            "print('LAZY_IMPORTS_OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            "image layout cannot import lazy tool trees\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "LAZY_IMPORTS_OK" in result.stdout


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_compose_file_validates_without_a_daemon():
    """`docker compose config` parses the file client-side (no daemon needed)."""
    env = {**os.environ, "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "")}
    result = subprocess.run(
        ["docker", "compose", "config", "-q"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
