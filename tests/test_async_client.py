"""Tests for the asynchronous MailCapture client."""
from __future__ import annotations

import pytest
import respx
import httpx

from mailcapture import (
    AsyncMailCapture,
    MailCaptureAuthError,
    MailCaptureNetworkError,
    MailCaptureNotFoundError,
    MailCaptureTimeoutError,
)
from .conftest import auth_error_dict, capture_dict, not_found_dict, ping_dict, timeout_dict

BASE = "https://mailcapture.app"


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_ping_returns_result():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict()))

    async with AsyncMailCapture("mc_testkey") as mc:
        result = await mc.ping()

    assert result.username == "alice"


@respx.mock
async def test_async_ping_caches_username():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(200, json=ping_dict("carol")))

    async with AsyncMailCapture("mc_testkey") as mc:
        assert mc.username is None
        await mc.ping()
        assert mc.username == "carol"


@respx.mock
async def test_async_ping_raises_auth_error():
    respx.get(f"{BASE}/v1/ping").mock(return_value=httpx.Response(401, json=auth_error_dict()))

    with pytest.raises(MailCaptureAuthError) as exc_info:
        async with AsyncMailCapture("mc_testkey") as mc:
            await mc.ping()

    assert "Authentication failed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# wait_for()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_wait_for_returns_capture():
    cap = capture_dict(tag="signup", otp="654321")
    respx.get(f"{BASE}/v1/latest/signup").mock(
        return_value=httpx.Response(
            200,
            json={"items": [cap], "count": 1, "next_after": cap["received_at"]},
        )
    )

    async with AsyncMailCapture("mc_testkey") as mc:
        result = await mc.wait_for("signup", timeout=5)

    assert result.otp == "654321"


@respx.mock
async def test_async_wait_for_loops_on_408():
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

    async with AsyncMailCapture("mc_testkey") as mc:
        result = await mc.wait_for("signup", timeout=30, poll_timeout=1)

    assert result.id == cap["id"]
    assert calls["n"] == 2


@respx.mock
async def test_async_wait_for_raises_timeout():
    respx.get(f"{BASE}/v1/latest/signup").mock(
        return_value=httpx.Response(408, json=timeout_dict())
    )

    async with AsyncMailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureTimeoutError) as exc_info:
            await mc.wait_for("signup", timeout=0.5, poll_timeout=1)

    assert exc_info.value.tag == "signup"
    assert exc_info.value.code == "TIMEOUT"


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_list():
    cap = capture_dict()
    respx.get(f"{BASE}/v1/captures").mock(
        return_value=httpx.Response(200, json={"items": [cap], "count": 1})
    )

    async with AsyncMailCapture("mc_testkey") as mc:
        result = await mc.list(tag="signup")

    assert result.count == 1
    assert result.items[0].tag == "signup"


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_get_raises_not_found():
    respx.get(f"{BASE}/v1/captures/missing").mock(
        return_value=httpx.Response(404, json=not_found_dict())
    )

    async with AsyncMailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureNotFoundError):
            await mc.get("missing")


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_delete_on_204():
    respx.delete(f"{BASE}/v1/captures/signup").mock(return_value=httpx.Response(204))

    async with AsyncMailCapture("mc_testkey") as mc:
        await mc.delete("signup")  # should not raise


# ---------------------------------------------------------------------------
# inbox()
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_inbox_wait_for():
    cap = capture_dict(tag="invite")
    respx.get(f"{BASE}/v1/latest/invite").mock(
        return_value=httpx.Response(
            200,
            json={"items": [cap], "count": 1, "next_after": cap["received_at"]},
        )
    )

    async with AsyncMailCapture("mc_testkey") as mc:
        inbox = mc.inbox("invite")
        result = await inbox.wait_for(timeout=5)

    assert result.tag == "invite"


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_network_error():
    respx.get(f"{BASE}/v1/ping").mock(side_effect=httpx.ConnectError("refused"))

    async with AsyncMailCapture("mc_testkey") as mc:
        with pytest.raises(MailCaptureNetworkError):
            await mc.ping()
