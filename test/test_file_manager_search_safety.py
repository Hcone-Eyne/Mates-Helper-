"""Adversarial tests for File Manager FTS5 search input (P1-5).

Raw user input used to flow straight into the FTS5 MATCH expression, so
quotes, parentheses, operators, and column filters caused SQLite syntax
errors (HTTP 500 on direct callers like MCP) or silently changed query
semantics. db.search_files now confines input to keyword terms: terms are
ANDed, a trailing `*` keeps prefix matching, everything else is matched
literally. These tests prove the external behavior, not the implementation.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from File_Manager import db


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    import File_Manager.db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test_index.db"))
    db.upsert_file("/vault/report.pdf", "report.pdf", ".pdf", "Documents", 100, 1.0, "quarterly budget report")
    db.upsert_file("/vault/notes.txt", "notes.txt", ".txt", "Notes", 100, 1.0, "meeting notes summary")
    db.upsert_file("/vault/budget.xlsx", "budget.xlsx", ".xlsx", "Documents", 100, 1.0, "annual budget")
    return tmp_path


class TestLegitimateSearchStillWorks:
    def test_single_keyword(self, seeded_db):
        results = db.search_files("budget", limit=10)
        assert {r["name"] for r in results} == {"report.pdf", "budget.xlsx"}

    def test_multiple_keywords_are_anded(self, seeded_db):
        results = db.search_files("budget report", limit=10)
        assert [r["name"] for r in results] == ["report.pdf"]

    def test_trailing_star_prefix_still_works(self, seeded_db):
        results = db.search_files("budg*", limit=10)
        assert {r["name"] for r in results} == {"report.pdf", "budget.xlsx"}

    def test_no_match_returns_empty(self, seeded_db):
        assert db.search_files("nonexistenttoken", limit=10) == []

    def test_blank_input_returns_empty(self, seeded_db):
        assert db.search_files("", limit=10) == []
        assert db.search_files("   ", limit=10) == []
        assert db.search_files(None, limit=10) == []


class TestAdversarialInputNeverErrors:
    # None of these may raise, leak schema details, or change meaning:
    # every one is treated as literal keyword text.
    @pytest.mark.parametrize("query", [
        '"unbalanced',
        'trailing"',
        '(((',
        ')))',
        '(a OR b)',
        'AND',
        'OR',
        'NOT',
        'a OR b',
        'a AND b',
        'NOT budget',
        'NEAR(budget report)',
        'NEAR',
        '*',
        '**',
        'a:b',
        '{name} : budget',
        '-budget',
        '+budget',
        '^budget',
        'budget^',
        '"budget""report"',
        'semi;colon',
        "quote's",
        'back\\slash',
        '100% sure',
        'a/b',
        'under_score',
        '𝑥𝑦𝑧',
    ])
    def test_adversarial_input_returns_list_without_raising(self, seeded_db, query):
        results = db.search_files(query, limit=10)
        assert isinstance(results, list)
        for row in results:
            assert {"path", "name", "category", "size", "mtime"} <= set(row)

    @pytest.mark.parametrize("query", [
        '"unbalanced',
        '(((',
        'AND',
        'a:b',
        '*',
        'NEAR(budget report)',
    ])
    def test_dangerous_syntax_matches_nothing_unexpected(self, seeded_db, query):
        # With controlled fixtures these literal tokens cannot match, so the
        # only acceptable outcomes are [] - never an error, never a surprise.
        # (Note: '-budget' is intentionally absent here: inside quotes the
        # leading dash is literal text, so it correctly matches "budget".)
        assert db.search_files(query, limit=10) == []

    def test_very_long_input_is_safe(self, seeded_db):
        assert db.search_files("budget " * 5000, limit=10) != []
        assert db.search_files("zzzq " * 5000, limit=10) == []

    def test_sql_injection_string_is_literal_text(self, seeded_db):
        before = db.list_all()
        results = db.search_files("x' OR '1'='1", limit=10)
        assert isinstance(results, list)
        # the files table is untouched: no injection effect whatsoever
        assert db.list_all() == before


class TestCallerPathsStaySafe:
    def test_mcp_direct_call_cannot_crash(self, seeded_db):
        mcp_server = pytest.importorskip("mcp_plugins.mcp_server")

        assert "Nothing matching" in mcp_server.file_find("(((")
        assert "Nothing matching" in mcp_server.file_find("")

    def test_api_search_returns_200_not_500(self, seeded_db):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        brain_app = pytest.importorskip("brain.app")
        client = TestClient(brain_app.app)

        response = client.get("/files/search", params={"q": "((("})
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_cli_wrapper_path_still_works(self, seeded_db):
        from File_Manager import search

        assert [r["name"] for r in search.search("budget report")] == ["report.pdf"]
        assert search.search("") == []
        assert {r["name"] for r in search.search("budg*")} == {"report.pdf", "budget.xlsx"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
