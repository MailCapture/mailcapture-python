from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._async_client import AsyncMailCapture
    from ._client import MailCapture
    from ._types import Capture, CaptureList


class Inbox:
    """Scoped handle for a single capture inbox (sync).

    Created via ``mc.inbox("my-tag")``. Keeps test code clean by binding
    the tag once.

    Example::

        inbox = mc.inbox("password-reset")
        inbox.clear()
        trigger_password_reset(inbox.address)
        email = inbox.wait_for(timeout=15)
        assert email.otp is not None
    """

    tag: str
    """The tag this inbox is scoped to."""

    def __init__(self, client: MailCapture, tag: str) -> None:
        self._client = client
        self.tag = tag

    @property
    def address(self) -> str:
        """Full capture email address (e.g. "alice-signup@mailcapture.app").

        Requires ``mc.ping()`` to have been called first.

        :raises RuntimeError: if ``ping()`` hasn't been called yet.
        """
        return self._client.address(self.tag)

    def wait_for(
        self,
        *,
        timeout: float = 30.0,
        poll_timeout: int = 10,
        after: datetime | str | None = None,
    ) -> Capture:
        """Wait for an email to arrive. See :meth:`MailCapture.wait_for`."""
        return self._client.wait_for(
            self.tag, timeout=timeout, poll_timeout=poll_timeout, after=after
        )

    def list(
        self,
        *,
        after: datetime | str | None = None,
        limit: int | None = None,
    ) -> CaptureList:
        """List recent captures. See :meth:`MailCapture.list`."""
        return self._client.list(tag=self.tag, after=after, limit=limit)

    def clear(self) -> None:
        """Delete all captures. Call before each test for a clean inbox."""
        self._client.delete(self.tag)

    def __repr__(self) -> str:
        return f"Inbox(tag={self.tag!r})"


class AsyncInbox:
    """Scoped handle for a single capture inbox (async).

    Created via ``mc.inbox("my-tag")``.

    Example::

        inbox = mc.inbox("signup")
        await inbox.clear()
        await trigger_signup(inbox.address)
        email = await inbox.wait_for(timeout=15)
        assert email.otp is not None
    """

    tag: str
    """The tag this inbox is scoped to."""

    def __init__(self, client: AsyncMailCapture, tag: str) -> None:
        self._client = client
        self.tag = tag

    @property
    def address(self) -> str:
        """Full capture email address. Requires ``await mc.ping()`` first."""
        return self._client.address(self.tag)

    async def wait_for(
        self,
        *,
        timeout: float = 30.0,
        poll_timeout: int = 10,
        after: datetime | str | None = None,
    ) -> Capture:
        """Wait for an email to arrive. See :meth:`AsyncMailCapture.wait_for`."""
        return await self._client.wait_for(
            self.tag, timeout=timeout, poll_timeout=poll_timeout, after=after
        )

    async def list(
        self,
        *,
        after: datetime | str | None = None,
        limit: int | None = None,
    ) -> CaptureList:
        """List recent captures. See :meth:`AsyncMailCapture.list`."""
        return await self._client.list(tag=self.tag, after=after, limit=limit)

    async def clear(self) -> None:
        """Delete all captures. Call before each test for a clean inbox."""
        await self._client.delete(self.tag)

    def __repr__(self) -> str:
        return f"AsyncInbox(tag={self.tag!r})"
