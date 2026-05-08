from __future__ import annotations

import time
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ._errors import MailCaptureNetworkError, MailCaptureTimeoutError
from ._generate import generate_tag
from ._http import parse_datetime_param, raise_api_error
from ._inbox import AsyncInbox
from ._types import Capture, CaptureList, GenerateResult, LatestResult, PingResult

_DEFAULT_BASE_URL = "https://mailcapture.app"
_DEFAULT_REQUEST_TIMEOUT = 10.0
_MAX_SERVER_POLL_SECONDS = 30
_SERVER_POLL_BUFFER = 5.0


class AsyncMailCapture:
    """Asynchronous MailCapture client.

    Use as an async context manager::

        async with AsyncMailCapture(api_key) as mc:
            await mc.ping()
            email = await mc.wait_for("signup", timeout=15)

    Or manage the lifecycle manually::

        mc = AsyncMailCapture(api_key)
        try:
            email = await mc.wait_for("signup")
        finally:
            await mc.aclose()

    Args:
        api_key: Your MailCapture API key (``mc_...``).
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
                "AsyncMailCapture: API key is required.\n"
                '  AsyncMailCapture("mc_...")\n'
                "  or\n"
                '  AsyncMailCapture(os.environ["MAILCAPTURE_API_KEY"])'
            )
        if not api_key.startswith("mc_"):
            warnings.warn(
                '[mailcapture] API key does not start with "mc_". Are you sure you copied the full key? '
                "Make sure you copied the full key from https://mailcapture.app/admin/api-keys",
                stacklevel=2,
            )

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._request_timeout = request_timeout
        self._username: str | None = None
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=request_timeout,
        )

    async def __aenter__(self) -> AsyncMailCapture:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP connection."""
        await self._http.aclose()

    @property
    def username(self) -> str | None:
        """Your MailCapture username. Set after a successful :meth:`ping` call."""
        return self._username

    # -------------------------------------------------------------------------
    # Public API

    async def ping(self) -> PingResult:
        """Validate your API key and get your capture address template.

        Example::

            result = await mc.ping()
            print(result.username)          # "alice"
            print(result.address_template)  # "alice-{tag}@mailcapture.app"

        :raises MailCaptureAuthError: if the API key is invalid.
        """
        data = await self._request("GET", "/v1/ping")
        result = PingResult(**data)
        self._username = result.username
        return result

    async def wait_for(
        self,
        tag: str,
        *,
        timeout: float = 60.0,
        poll_timeout: int = 10,
        after: datetime | str | None = None,
    ) -> Capture:
        """Wait for an email to arrive at the given tag and return it.

        Args:
            tag: The capture tag to wait on (e.g. "signup").
            timeout: Total time to wait in seconds (default 60).
            poll_timeout: Per-poll server timeout in seconds (max 30, default 10).
            after: Only return captures received after this datetime.

        :raises MailCaptureTimeoutError: if no email arrives before ``timeout``.

        Example::

            await mc.delete("signup")
            await trigger_signup(email)
            email = await mc.wait_for("signup", timeout=15)
            assert email.otp is not None
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

            result = await self._latest(tag, timeout=effective_poll, after=after_dt)
            if result is not None:
                if result.items:
                    return result.items[0]
                after_dt = datetime.fromisoformat(
                    result.next_after.replace("Z", "+00:00")
                )

        hint = (
            f"Make sure you're sending to {self._username}-{tag}@mailcapture.app."
            if self._username
            else "Check that you're sending to the right address (call await ping() first to get your username)."
        )
        raise MailCaptureTimeoutError(tag, timeout, hint)

    async def list(
        self,
        *,
        tag: str | None = None,
        after: datetime | str | None = None,
        limit: int | None = None,
    ) -> CaptureList:
        """List recent captures (newest first).

        Example::

            result = await mc.list(tag="signup", limit=10)
        """
        params: dict[str, str] = {}
        if tag is not None:
            params["tag"] = tag
        if limit is not None:
            params["limit"] = str(limit)
        if after is not None:
            params["after"] = parse_datetime_param(after)
        return CaptureList.from_dict(await self._request("GET", "/v1/captures", params=params))

    async def get(self, capture_id: str) -> Capture:
        """Get a single capture by ID.

        :raises MailCaptureNotFoundError: if the capture does not exist.
        """
        if not capture_id:
            raise ValueError("capture_id is required")
        return Capture.from_dict(await self._request("GET", f"/v1/captures/{capture_id}"))

    async def delete(self, tag: str) -> None:
        """Delete all captures for a tag."""
        if not tag:
            raise ValueError("tag is required")
        await self._request("DELETE", f"/v1/captures/{tag}")

    def inbox(self, tag: str) -> AsyncInbox:
        """Get a scoped :class:`AsyncInbox` for a specific tag.

        Example::

            inbox = mc.inbox("signup")
            await inbox.clear()
            await trigger_signup(inbox.address)
            email = await inbox.wait_for(timeout=10)
        """
        if not tag:
            raise ValueError("tag is required")
        return AsyncInbox(self, tag)

    def address(self, tag: str) -> str:
        """Get the capture email address for a tag.

        Requires ``await ping()`` to have been called first.

        :raises RuntimeError: if :meth:`ping` hasn't been called yet.
        """
        if not self._username:
            raise RuntimeError(
                "Cannot generate address: username is not known yet. "
                "Call `await mc.ping()` first, then use `mc.address(tag)`."
            )
        return f"{self._username}-{tag}@mailcapture.app"

    def generate(self) -> "GenerateResult":
        """Generate a unique tag and its capture email address.

        Synchronous — requires ``await ping()`` to have been called first.

        Example::

            await mc.ping()
            result = mc.generate()
            # result.tag:   "funky-otter-a3f2b8"
            # result.email: "alice-funky-otter-a3f2b8@mailcapture.app"
            await register_user(result.email)
            email = await mc.wait_for(result.tag, timeout=15)
        """
        tag = generate_tag()
        return GenerateResult(tag=tag, email=self.address(tag))

    # -------------------------------------------------------------------------
    # Internals

    async def _latest(
        self, tag: str, *, timeout: int, after: datetime
    ) -> LatestResult | None:
        params = {"timeout": str(timeout), "after": after.isoformat()}
        client_timeout = timeout + _SERVER_POLL_BUFFER
        try:
            response = await self._http.get(
                f"/v1/latest/{tag}", params=params, timeout=client_timeout
            )
        except httpx.TransportError as exc:
            raise MailCaptureNetworkError(self._base_url, exc) from exc

        if response.status_code == 408:
            return None
        if not response.is_success:
            raise_api_error(response)
        return LatestResult.from_dict(response.json())

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, params=params)
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
