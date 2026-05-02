from __future__ import annotations

import time
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ._errors import MailCaptureNetworkError, MailCaptureTimeoutError
from ._http import parse_datetime_param, raise_api_error
from ._inbox import Inbox
from ._types import Capture, CaptureList, LatestResult, PingResult

_DEFAULT_BASE_URL = "https://mailcapture.app"
_DEFAULT_REQUEST_TIMEOUT = 10.0
_MAX_SERVER_POLL_SECONDS = 30
_SERVER_POLL_BUFFER = 5.0


class MailCapture:
    """Synchronous MailCapture client.

    Use as a context manager to ensure the underlying connection is closed::

        with MailCapture(api_key) as mc:
            mc.ping()
            email = mc.wait_for("signup", timeout=15)

    Or manage the lifecycle manually::

        mc = MailCapture(api_key)
        try:
            email = mc.wait_for("signup")
        finally:
            mc.close()

    Args:
        api_key: Your MailCapture API key (``mc_live_...``).
        base_url: API base URL. Override for local development.
        request_timeout: Default timeout in seconds for non-polling requests.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        request_timeout: float = _DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError(
                "MailCapture: API key is required.\n"
                '  MailCapture("mc_live_...")\n'
                "  or\n"
                '  MailCapture(os.environ["MAILCAPTURE_API_KEY"])'
            )
        if not api_key.startswith(("mc_live_", "mc_test_")):
            warnings.warn(
                '[mailcapture] API key does not start with "mc_live_" or "mc_test_". '
                "Make sure you copied the full key from https://mailcapture.app/admin/api-keys",
                stacklevel=2,
            )

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._request_timeout = request_timeout
        self._username: str | None = None
        self._http = httpx.Client(
            base_url=self._base_url,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=request_timeout,
        )

    def __enter__(self) -> MailCapture:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._http.close()

    @property
    def username(self) -> str | None:
        """Your MailCapture username. Set after a successful :meth:`ping` call."""
        return self._username

    # -------------------------------------------------------------------------
    # Public API

    def ping(self) -> PingResult:
        """Validate your API key and get your capture address template.

        Also caches your username internally so :meth:`address` works without
        a network call.

        Example::

            result = mc.ping()
            print(result.username)          # "alice"
            print(result.address_template)  # "alice-{tag}@mailcapture.app"

        :raises MailCaptureAuthError: if the API key is invalid.
        """
        data = self._request("GET", "/v1/ping")
        result = PingResult(**data)
        self._username = result.username
        return result

    def wait_for(
        self,
        tag: str,
        *,
        timeout: float = 30.0,
        poll_timeout: int = 10,
        after: datetime | str | None = None,
    ) -> Capture:
        """Wait for an email to arrive at the given tag and return it.

        Long-polls the API — the server holds the connection open and responds
        the moment an email arrives. No busy-waiting.

        Args:
            tag: The capture tag to wait on (e.g. "signup").
            timeout: Total time to wait in seconds (default 30).
            poll_timeout: Per-poll server timeout in seconds (max 30, default 10).
            after: Only return captures received after this datetime.
                   Defaults to 60 seconds ago, so recent emails are included
                   but stale ones from previous runs are ignored.

        Returns:
            The first :class:`Capture` that arrives.

        Raises:
            MailCaptureTimeoutError: if no email arrives before ``timeout``.
            MailCaptureAuthError: if the API key is invalid.

        Example::

            # Basic
            email = mc.wait_for("signup", timeout=15)
            assert email.otp == "123456"

            # Maximum isolation — clear first, then wait
            mc.delete("signup")
            trigger_signup(email)
            email = mc.wait_for("signup", timeout=15)
        """
        poll_timeout = min(max(1, poll_timeout), _MAX_SERVER_POLL_SECONDS)
        deadline = time.monotonic() + timeout

        if after is None:
            after_dt = datetime.now(timezone.utc) - timedelta(seconds=60)
        elif isinstance(after, str):
            after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
        else:
            after_dt = after if after.tzinfo else after.replace(tzinfo=timezone.utc)

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            effective_poll = min(poll_timeout, max(1, int(remaining)))

            result = self._latest(tag, timeout=effective_poll, after=after_dt)
            if result is not None:
                if result.items:
                    return result.items[0]
                after_dt = datetime.fromisoformat(
                    result.next_after.replace("Z", "+00:00")
                )

        hint = (
            f"Make sure you're sending to {self._username}-{tag}@mailcapture.app."
            if self._username
            else "Check that you're sending to the right address (call ping() first to get your username)."
        )
        raise MailCaptureTimeoutError(tag, timeout, hint)

    def list(
        self,
        *,
        tag: str | None = None,
        after: datetime | str | None = None,
        limit: int | None = None,
    ) -> CaptureList:
        """List recent captures (newest first).

        Args:
            tag: Filter by tag.
            after: Only return captures received after this datetime.
            limit: Maximum results to return (1-100, default 25).

        Example::

            result = mc.list(tag="signup", limit=10)
            for email in result.items:
                print(email.subject)
        """
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if limit is not None:
            params["limit"] = str(limit)
        if after is not None:
            params["after"] = parse_datetime_param(after)
        return CaptureList.from_dict(self._request("GET", "/v1/captures", params=params))

    def get(self, capture_id: str) -> Capture:
        """Get a single capture by ID.

        :raises ValueError: if ``capture_id`` is empty.
        :raises MailCaptureNotFoundError: if the capture does not exist.

        Example::

            email = mc.get("e0f5922d-d8a9-4b03-bc60-9507b2e2f665")
        """
        if not capture_id:
            raise ValueError("capture_id is required")
        return Capture.from_dict(self._request("GET", f"/v1/captures/{capture_id}"))

    def delete(self, tag: str) -> None:
        """Delete all captures for a tag.

        Call this before each test to start with a clean inbox.

        :raises ValueError: if ``tag`` is empty.

        Example::

            mc.delete("signup")
            # or via inbox:
            mc.inbox("signup").clear()
        """
        if not tag:
            raise ValueError("tag is required")
        self._request("DELETE", f"/v1/captures/{tag}")

    def inbox(self, tag: str) -> Inbox:
        """Get a scoped :class:`Inbox` for a specific tag.

        Example::

            inbox = mc.inbox("password-reset")
            inbox.clear()
            trigger_password_reset(inbox.address)
            email = inbox.wait_for(timeout=10)
            assert email.otp is not None

        :raises ValueError: if ``tag`` is empty.
        """
        if not tag:
            raise ValueError("tag is required")
        return Inbox(self, tag)

    def address(self, tag: str) -> str:
        """Get the capture email address for a tag.

        Synchronous — requires :meth:`ping` to have been called first.

        :raises RuntimeError: if :meth:`ping` hasn't been called yet.

        Example::

            mc.ping()
            print(mc.address("signup"))  # "alice-signup@mailcapture.app"
        """
        if not self._username:
            raise RuntimeError(
                "Cannot generate address: username is not known yet. "
                "Call mc.ping() first, then use mc.address(tag)."
            )
        return f"{self._username}-{tag}@mailcapture.app"

    # -------------------------------------------------------------------------
    # Internals

    def _latest(
        self, tag: str, *, timeout: int, after: datetime
    ) -> LatestResult | None:
        params = {"timeout": str(timeout), "after": after.isoformat()}
        client_timeout = timeout + _SERVER_POLL_BUFFER
        try:
            response = self._http.get(
                f"/v1/latest/{tag}", params=params, timeout=client_timeout
            )
        except httpx.TransportError as exc:
            raise MailCaptureNetworkError(self._base_url, exc) from exc

        if response.status_code == 408:
            return None  # server-side timeout — loop again
        if not response.is_success:
            raise_api_error(response)
        return LatestResult.from_dict(response.json())

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, params=params)
        except httpx.TransportError as exc:
            raise MailCaptureNetworkError(self._base_url, exc) from exc

        if response.status_code == 204:
            return {}

        try:
            body: dict[str, Any] = response.json()
        except Exception as exc:
            from ._errors import MailCaptureApiError
            raise MailCaptureApiError(
                response.status_code,
                "INVALID_RESPONSE",
                f"Received a non-JSON response from {self._base_url}{path} "
                f"(HTTP {response.status_code})",
            ) from exc

        if not response.is_success:
            raise_api_error(response)

        return body
