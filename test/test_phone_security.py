"""Tests for Phone Hub security modules (permission.py and isolation.py)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phone.security.permission import PhonePermision, READ_ONLY, ACTION_PERMISSION
from phone.security.isolation import PhoneIsolationError, assert_phone_boundary


class TestPhonePermission:
    """Test PhonePermision enum and permission sets."""

    def test_permission_enum_values(self):
        assert PhonePermision.Status == "status"
        assert PhonePermision.NOTIFICATIONS == "notifications"
        assert PhonePermision.CALLS == "calls"
        assert PhonePermision.MESSAGES == "messages"
        assert PhonePermision.FILES == "files"
        assert PhonePermision.SEND_MESSAGE == "send_message"
        assert PhonePermision.MAKE_CALL == "make_call"

    def test_permission_enum_is_str(self):
        assert isinstance(PhonePermision.Status, str)
        assert isinstance(PhonePermision.NOTIFICATIONS, str)

    def test_read_only_set_contains_expected(self):
        assert PhonePermision.Status in READ_ONLY
        assert PhonePermision.NOTIFICATIONS in READ_ONLY
        assert PhonePermision.CALLS in READ_ONLY
        assert PhonePermision.MESSAGES in READ_ONLY
        assert PhonePermision.FILES in READ_ONLY
        assert len(READ_ONLY) == 5

    def test_action_permission_set_contains_expected(self):
        assert PhonePermision.SEND_MESSAGE in ACTION_PERMISSION
        assert PhonePermision.MAKE_CALL in ACTION_PERMISSION
        assert len(ACTION_PERMISSION) == 2

    def test_read_only_and_action_are_disjoint(self):
        assert READ_ONLY.isdisjoint(ACTION_PERMISSION)

    def test_permission_enum_iteration(self):
        all_perms = list(PhonePermision)
        assert len(all_perms) == 7


class TestPhoneIsolation:
    """Test assert_phone_boundary function."""

    def test_fox_raises(self):
        with pytest.raises(PhoneIsolationError, match="Phone data is isolated from agent"):
            assert_phone_boundary("fox")

    def test_fox_agent_raises(self):
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("fox_agent")

    def test_agent_raises(self):
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("agent")

    def test_ollama_raises(self):
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("ollama")

    def test_case_insensitive(self):
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("FOX")
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("Fox")
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("Fox_Agent")

    def test_whitespace_handling(self):
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("  fox  ")
        with pytest.raises(PhoneIsolationError):
            assert_phone_boundary("\tfox\n")

    def test_allowed_sources(self):
        # These should not raise
        assert_phone_boundary("user")
        assert_phone_boundary("system")
        assert_phone_boundary("phone_cli")
        assert_phone_boundary("kdeconnect")
        assert_phone_boundary("")

    def test_empty_string_allowed(self):
        assert_phone_boundary("")

    def test_phone_isolation_error_is_permission_error(self):
        assert issubclass(PhoneIsolationError, PermissionError)

    def test_error_message(self):
        try:
            assert_phone_boundary("fox")
        except PhoneIsolationError as e:
            assert "Phone data is isolated from agent" in str(e)


import pytest  # needed for pytest.raises