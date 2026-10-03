"""Focused SSRF-safety tests for the LLM-controlled web_browse tool.

Every test mocks DNS and network access - nothing here may make a real
external request. Validation is exercised through
`agent.ollama.tools._validate_url_for_fetch`, redirect handling through
`_SafeRedirectHandler`, and the end-to-end fail-closed wiring through
`_web_browse` with a mocked opener.
"""

import socket
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

import agent.ollama.tools as tools


PUBLIC_IP = "93.184.216.34"
BLOCKED_IP = "10.9.8.7"


def _addrinfo(ip, port=80):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def _resolve_to(ip):
    def _resolve(host, port, *args, **kwargs):
        return _addrinfo(ip, port or 80)

    return _resolve


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestSchemeValidation:
    def test_https_example_com_accepted(self):
        with patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)):
            assert tools._validate_url_for_fetch("https://example.com") is None

    def test_http_example_com_accepted(self):
        with patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)):
            assert tools._validate_url_for_fetch("http://example.com") is None

    def test_file_url_rejected(self):
        assert tools._validate_url_for_fetch("file:///etc/passwd").startswith("[Fox]")

    def test_ftp_url_rejected(self):
        assert tools._validate_url_for_fetch("ftp://example.com").startswith("[Fox]")


class TestBlockedLiterals:
    def test_localhost_rejected(self):
        with patch("socket.getaddrinfo", side_effect=_resolve_to("127.0.0.1")):
            assert tools._validate_url_for_fetch("http://localhost").startswith("[Fox]")

    def test_loopback_ipv4_rejected(self):
        with patch("socket.getaddrinfo") as resolve:
            assert tools._validate_url_for_fetch("http://127.0.0.1").startswith("[Fox]")
            resolve.assert_not_called()

    def test_loopback_ipv6_rejected(self):
        with patch("socket.getaddrinfo") as resolve:
            assert tools._validate_url_for_fetch("http://[::1]").startswith("[Fox]")
            resolve.assert_not_called()

    def test_private_ipv4_rejected(self):
        with patch("socket.getaddrinfo") as resolve:
            assert tools._validate_url_for_fetch("http://192.168.1.10/").startswith("[Fox]")
            resolve.assert_not_called()

    def test_link_local_ipv4_rejected(self):
        with patch("socket.getaddrinfo") as resolve:
            assert tools._validate_url_for_fetch("http://169.254.169.254/").startswith("[Fox]")
            resolve.assert_not_called()

    def test_multicast_rejected(self):
        assert tools._validate_url_for_fetch("http://224.0.0.1/").startswith("[Fox]")

    def test_unspecified_rejected(self):
        assert tools._validate_url_for_fetch("http://0.0.0.0/").startswith("[Fox]")


class TestResolvedAddresses:
    def test_hostname_resolving_to_blocked_address_rejected(self):
        with patch("socket.getaddrinfo", side_effect=_resolve_to(BLOCKED_IP)):
            error = tools._validate_url_for_fetch("http://files.example.com/")
        assert error.startswith("[Fox]")
        assert "blocked" in error

    def test_hostname_resolution_is_actually_consulted(self):
        with patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)) as resolve:
            assert tools._validate_url_for_fetch("http://example.com/") is None
        assert resolve.called

    def test_unresolvable_hostname_fails_closed(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
            assert tools._validate_url_for_fetch("http://does-not-exist.invalid/").startswith("[Fox]")


class TestRedirectValidation:
    def _request(self):
        return urllib.request.Request("http://example.com/", headers={"User-Agent": "test"})

    def test_redirect_to_blocked_literal_rejected(self):
        handler = tools._SafeRedirectHandler()
        with pytest.raises(tools._BlockedURLError, match=r"\[Fox\]"):
            handler.redirect_request(self._request(), None, 302, "Found", {}, "http://127.0.0.1/secret")

    def test_redirect_to_host_resolving_to_blocked_address_rejected(self):
        handler = tools._SafeRedirectHandler()
        with patch("socket.getaddrinfo", side_effect=_resolve_to(BLOCKED_IP)):
            with pytest.raises(tools._BlockedURLError, match=r"\[Fox\]"):
                handler.redirect_request(
                    self._request(), None, 302, "Found", {}, "http://evil.example/"
                )

    def test_redirect_to_public_target_allowed(self):
        handler = tools._SafeRedirectHandler()
        with patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)):
            result = handler.redirect_request(
                self._request(), None, 302, "Found", {}, "https://example.com/next"
            )
        assert result.get_full_url() == "https://example.com/next"

    def test_web_browse_redirect_failure_fails_closed(self):
        opener = MagicMock()
        opener.open.side_effect = tools._BlockedURLError(
            "[Fox]: URL is not allowed because it resolves to a blocked address."
        )
        with (
            patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)),
            patch("urllib.request.build_opener", return_value=opener),
        ):
            result = tools._web_browse("http://example.com/")
        assert result.startswith("[Fox]")
        assert "blocked" in result


class TestAllowedFetchBehavior:
    def test_successful_fetch_keeps_4000_char_limit(self):
        payload = b"<html><body><p>" + b"x" * 5000 + b"</p></body></html>"
        opener = MagicMock()
        opener.open.return_value = _FakeResponse(payload)
        with (
            patch("socket.getaddrinfo", side_effect=_resolve_to(PUBLIC_IP)),
            patch("urllib.request.build_opener", return_value=opener),
        ):
            result = tools._web_browse("https://example.com/article")
        assert len(result) <= 4003
        assert result.endswith("...")

    def test_blocked_url_never_reaches_the_opener(self):
        with patch("urllib.request.build_opener") as build_opener:
            result = tools._web_browse("file:///etc/passwd")
        build_opener.assert_not_called()
        assert result.startswith("[Fox]")
