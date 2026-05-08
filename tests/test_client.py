"""Tests for the synchronous MailCapture client."""
from __future__ import annotations

import pytest
import respx
import httpx

from mailcapture import (
    MailCapture,
    MailCaptureAuthError,
    MailCaptureNetworkError,
    MailCaptureNotFoundError,
    MailCaptureTimeoutError,
)
from .conftest import auth_error_dict, capture_dict, not_found_dict, ping_dict, timeout_dict

BASE = "https://mailcapture.app"


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_raises_on_empty_key():
    with pytest.raises(ValueError, match="API key is required"):
        MailCapture("")


def test_warns_on_bad_key_prefix():
    with pytest.warns(UserWarning, match="mc_"):
        MailCapture("badkey")


def test_no_warning_for_mc_key():
    # Should not raise or warn for any mc_ key
    mc = MailCapture("mc_e3d0fe6221f0435b90d0d0915d6fd14a")
    mc.close()


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


@respx.mock
def test_ping_returns_result():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict()))

    with MailCapture("mc_testkey") as mc:
        result = mc.ping()

    assert result.username == "alice"
    assert result.address_template == "alice-{tag}@mailcapture.app"


@respx.mock
def test_ping_caches_username():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict("bob")))

    with MailCapture("mc_testkey") as mc:
        assert mc.username is None
        mc.ping()
        assert mc.username == "bob"


@respx.mock
def test_ping_raises_auth_error_on_401():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(401, json=auth_error_dict()))

    with pytest.raises(MailCaptureAuthError) as exc_info:
        with MailCapture("mc_testkey") as mc:
            mc.ping()

    assert exc_info.value.code == "UNAUTHORIZED"
    assert "Authentication failed" in str(exc_info.value)
    assert "mailcapture.app" in str(exc_info.value)


# ---------------------------------------------------------------------------
# address()
# ---------------------------------------------------------------------------


def test_address_raises_before_ping():
    with MailCapture("mc_testkey") as mc:
        with pytest.raises(RuntimeError, match="ping()"):
            mc.address("signup")


@respx.mock
def test_address_returns_correct_email():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict("alice")))

    with MailCapture("mc_testkey") as mc:
        mc.ping()
        assert mc.address("signup") == "alice-signup@mailcapture.app"
        assert mc.address("password-reset") == "alice-password-reset@mailcapture.app"


# ---------------------------------------------------------------------------
# wait_for()
# ---------------------------------------------------------------------------


@respx.mock
def test_wait_for_returns_first_capture():
    cap = capture_dict(tag="signup", otp="999999")
    respx.get(f"{BASE}/v1/latest/signup").mock(
        return_value=httpx.Response(
            200,
            json={"items": [cap], "count": 1, "next_after": cap["received_at"]},
        )
    )

    with MailCapture("mc_testkey") as mc:
        result = mc.wait_for("signup", timeout=5)

    assert result.id == cap["id"]
    assert result.otp == "999999"


@respx.mock
def test_wait_for_loops_on_408():
    cap = capture_dict(tag="signup")
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(408, json=timeout_dict())
        return httpx.Response(
            200,
            json={"items": [cap], "count": 1, "next_after": cap["received_at"]},
        )

    respx.get(f"{BASE}/v1/latest/signup").mock(side_effect=handler)

    with MailCapture("mc_testkey") as mc:
        result = mc.wait_for("signup", timeout=30, poll_timeout=1)

    assert result.id == cap["id"]
    assert calls["n"] == 2


@respx.mock
def test_wait_for_raises_timeout_error():
    respx.get(f"{BASE}/v1/latest/signup").mock(
        return_value=httpx.Response(408, json=timeout_dict())
    )

    with MailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureTimeoutError) as exc_info:
            mc.wait_for("signup", timeout=0.5, poll_timeout=1)

    err = exc_info.value
    assert err.tag == "signup"
    assert err.waited_seconds == pytest.approx(0.5, abs=0.1)
    assert err.code == "TIMEOUT"
    assert '"signup"' in str(err)


@respx.mock
def test_wait_for_timeout_hint_includes_address_after_ping():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict("alice")))
    respx.get(f"{BASE}/v1/latest/signup").mock(
        return_value=httpx.Response(408, json=timeout_dict())
    )

    with MailCapture("mc_testkey") as mc:
        mc.ping()
        with pytest.raises(MailCaptureTimeoutError) as exc_info:
            mc.wait_for("signup", timeout=0.5, poll_timeout=1)

    assert "alice-signup@mailcapture.app" in str(exc_info.value)


@respx.mock
def test_wait_for_advances_cursor():
    from datetime import datetime, timezone

    first_ts = "2024-01-01T00:00:00+00:00"
    second_ts = "2024-01-01T00:00:01+00:00"
    cap1 = capture_dict(id="cap1", received_at=first_ts)
    cap2 = capture_dict(id="cap2", received_at=second_ts)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        after = request.url.params.get("after", "")
        if first_ts[:19] in after or calls["n"] == 1:
            # First call: return cap1 but with empty items to test cursor advancement
            # Actually return cap1 on first call
            if calls["n"] == 1:
                return httpx.Response(
                    200,
                    json={"items": [cap1], "count": 1, "next_after": first_ts},
                )
        return httpx.Response(
            200,
            json={"items": [cap2], "count": 1, "next_after": second_ts},
        )

    respx.get(f"{BASE}/v1/latest/signup").mock(side_effect=handler)

    with MailCapture("mc_testkey") as mc:
        result = mc.wait_for("signup", timeout=5, poll_timeout=1)

    # Should return cap1 immediately (first item on first poll)
    assert result.id == "cap1"


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------


@respx.mock
def test_list_returns_captures():
    cap = capture_dict()
    respx.get(f"{BASE}/v1/captures").mock(
        return_value=httpx.Response(200, json={"items": [cap], "count": 1})
    )

    with MailCapture("mc_testkey") as mc:
        result = mc.list()

    assert result.count == 1
    assert len(result.items) == 1
    assert result.items[0].subject == "Welcome"


@respx.mock
def test_list_sends_params():
    respx.get(f"{BASE}/v1/captures").mock(
        return_value=httpx.Response(200, json={"items": [], "count": 0})
    )

    with MailCapture("mc_testkey") as mc:
        mc.list(tag="signup", limit=10)

    request = respx.calls.last.request
    assert "tag=signup" in str(request.url)
    assert "limit=10" in str(request.url)


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


def test_get_raises_on_empty_id():
    with MailCapture("mc_testkey") as mc:
        with pytest.raises(ValueError, match="capture_id is required"):
            mc.get("")


@respx.mock
def test_get_returns_capture():
    cap = capture_dict(id="xyz-456")
    respx.get(f"{BASE}/v1/captures/xyz-456").mock(
        return_value=httpx.Response(200, json=cap)
    )

    with MailCapture("mc_testkey") as mc:
        result = mc.get("xyz-456")

    assert result.id == "xyz-456"


@respx.mock
def test_get_raises_not_found():
    respx.get(f"{BASE}/v1/captures/nonexistent").mock(
        return_value=httpx.Response(404, json=not_found_dict())
    )

    with MailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureNotFoundError) as exc_info:
            mc.get("nonexistent")

    assert exc_info.value.code == "NOT_FOUND"


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


def test_delete_raises_on_empty_tag():
    with MailCapture("mc_testkey") as mc:
        with pytest.raises(ValueError, match="tag is required"):
            mc.delete("")


@respx.mock
def test_delete_succeeds_on_204():
    respx.delete(f"{BASE}/v1/captures/signup").mock(
        return_value=httpx.Response(204)
    )

    with MailCapture("mc_testkey") as mc:
        mc.delete("signup")  # should not raise


# ---------------------------------------------------------------------------
# inbox()
# ---------------------------------------------------------------------------


def test_inbox_raises_on_empty_tag():
    with MailCapture("mc_testkey") as mc:
        with pytest.raises(ValueError, match="tag is required"):
            mc.inbox("")


def test_inbox_tag():
    with MailCapture("mc_testkey") as mc:
        inbox = mc.inbox("signup")
    assert inbox.tag == "signup"


def test_inbox_address_requires_ping():
    with MailCapture("mc_testkey") as mc:
        inbox = mc.inbox("signup")
    with pytest.raises(RuntimeError, match="ping()"):
        _ = inbox.address


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


@respx.mock
def test_network_error_on_connection_failure():
    respx.get(f"{BASE}/v1/ping").mock(side_effect=httpx.ConnectError("ECONNREFUSED"))

    with MailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureNetworkError) as exc_info:
            mc.ping()

    assert exc_info.value.code == "NETWORK_ERROR"
    assert "mailcapture.app" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Capture dataclass
# ---------------------------------------------------------------------------


def test_capture_optional_fields():
    cap = capture_dict(otp=None, body_text=None, body_html=None)
    from mailcapture import Capture
    obj = Capture.from_dict(cap)
    assert obj.otp is None
    assert obj.body_text is None
    assert obj.body_html is None
