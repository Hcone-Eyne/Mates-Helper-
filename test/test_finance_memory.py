"""Focused tests for finance memory/state handling.

Memory/memory_storer.memory_log is a process-global list shared by the CLI
finance menu, agent tools, MCP tools, and concurrent Brain worker threads.
These tests prove: invalid (None) results never pollute history, history is
capped instead of growing forever, an invalid menu choice no longer erases
history, explicit erase still works, and concurrent appends are safe.
"""

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Memory import memory_storer as m


@pytest.fixture(autouse=True)
def isolated_log(monkeypatch):
    """Run each test against an empty log; restore prior state afterwards."""
    monkeypatch.delenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", raising=False)
    saved = list(m.memory_log)
    m.memory_log.clear()
    yield
    with m._memory_lock:
        m.memory_log[:] = saved


class TestInvalidResultsNeverStored:
    def test_none_result_not_stored(self):
        m.memory_catcher("abc", None)
        assert m.memory_log == []

    def test_none_does_not_erase_existing(self):
        m.memory_catcher("2+2", 4)
        m.memory_catcher("abc", None)
        assert m.memory_log == [{"expression": "2+2", "result": 4}]

    def test_valid_result_still_stored(self):
        m.memory_catcher("2+2", 4)
        assert m.memory_log == [{"expression": "2+2", "result": 4}]

    def test_agent_invalid_calculation_does_not_pollute(self):
        from agent.ollama.tools import dispatch

        result = dispatch("finance_calculate", expression="abc")
        assert "Invalid expression" in result
        assert m.memory_log == []

    def test_agent_valid_calculation_still_recorded(self):
        from agent.ollama.tools import dispatch

        assert dispatch("finance_calculate", expression="2+3") == "[Fox]: Result -> 5"
        assert m.memory_log == [{"expression": "2+3", "result": 5}]


class TestHistoryBound:
    def test_history_stops_growing(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "5")
        for i in range(10):
            m.memory_catcher(f"{i}+{i}", i + i)
        assert len(m.memory_log) == 5

    def test_most_recent_entries_kept(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "5")
        for i in range(10):
            m.memory_catcher(f"{i}+{i}", i + i)
        assert m.memory_log[0] == {"expression": "5+5", "result": 10}
        assert m.memory_log[-1] == {"expression": "9+9", "result": 18}

    def test_short_history_untouched(self):
        m.memory_catcher("1+1", 2)
        m.memory_catcher("2+2", 4)
        assert m.memory_log == [
            {"expression": "1+1", "result": 2},
            {"expression": "2+2", "result": 4},
        ]

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "lots")
        assert m.finance_history_max_entries() == m.FINANCE_HISTORY_MAX_ENTRIES_DEFAULT

    def test_floor_keeps_feature_functional(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "0")
        assert m.finance_history_max_entries() == 1
        m.memory_catcher("1+1", 2)
        m.memory_catcher("2+2", 4)
        assert m.memory_log == [{"expression": "2+2", "result": 4}]


class TestClearBehavior:
    def test_invalid_choice_preserves_history(self, monkeypatch):
        m.memory_catcher("2+2", 4)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "bogus-choice")
        m.memory_lister()
        assert m.memory_log == [{"expression": "2+2", "result": 4}]

    def test_explicit_erase_still_clears(self, monkeypatch):
        m.memory_catcher("2+2", 4)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "4")
        m.memory_lister()
        assert m.memory_log == []

    def test_skip_preserves_history(self, monkeypatch):
        m.memory_catcher("2+2", 4)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "0")
        m.memory_lister()
        assert m.memory_log == [{"expression": "2+2", "result": 4}]

    def test_eraser_still_clears(self):
        m.memory_catcher("2+2", 4)
        m.memory_eraser()
        assert m.memory_log == []


class TestConcurrentAppends:
    def test_concurrent_appends_stay_consistent(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "1000")
        errors = []
        barrier = threading.Barrier(8)

        def worker(w):
            try:
                barrier.wait(timeout=10)
                for i in range(25):
                    m.memory_catcher(f"w{w}+{i}", w + i)
            except Exception as exc:  # noqa: BLE001 - collected, then asserted
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert errors == []
        assert len(m.memory_log) == 200
        assert all(
            set(entry) == {"expression", "result"} and entry["result"] is not None
            for entry in m.memory_log
        )

    def test_concurrent_appends_respect_bound(self, monkeypatch):
        monkeypatch.setenv("FOX_FINANCE_HISTORY_MAX_ENTRIES", "50")
        barrier = threading.Barrier(4)

        def worker(w):
            barrier.wait(timeout=10)
            for i in range(25):
                m.memory_catcher(f"w{w}+{i}", w + i)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert len(m.memory_log) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
