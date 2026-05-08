from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Capture:
    """A captured email."""

    id: str
    """Unique ID for this capture."""

    tag: str
    """Tag portion of the address (e.g. "signup" from "user-signup@mailcapture.app")."""

    subject: str
    """Email subject line."""

    otp: str | None
    """Extracted OTP / verification code, if one was detected. ``None`` if no code found."""

    body_text: str | None
    """Plain-text body of the email, if present."""

    body_html: str | None
    """HTML body of the email, if present."""

    latency_ms: int
    """Time from email send to capture receipt, in milliseconds."""

    status: str
    """Email status (e.g. "captured")."""

    received_at: str
    """ISO 8601 timestamp of when the email was received."""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Capture:
        return cls(
            id=d["id"],
            tag=d["tag"],
            subject=d["subject"],
            otp=d.get("otp"),
            body_text=d.get("body_text"),
            body_html=d.get("body_html"),
            latency_ms=d["latency_ms"],
            status=d["status"],
            received_at=d["received_at"],
        )


@dataclass
class CaptureList:
    """Response from the list captures endpoint."""

    items: list[Capture]
    count: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CaptureList:
        return cls(
            items=[Capture.from_dict(i) for i in d.get("items", [])],
            count=d["count"],
        )


@dataclass
class PingResult:
    """Response from the ping endpoint."""

    status: str
    username: str
    """Your unique username — used as the prefix in all capture addresses."""
    address_template: str
    """Template string: replace ``{tag}`` with your desired tag."""
    example: str
    """A concrete example address."""


@dataclass
class LatestResult:
    """Response from the long-poll endpoint."""

    items: list[Capture]
    count: int
    next_after: str
    """ISO 8601 cursor — pass as ``after`` in the next poll to avoid re-processing."""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LatestResult:
        return cls(
            items=[Capture.from_dict(i) for i in d.get("items", [])],
            count=d["count"],
            next_after=d["next_after"],
        )


@dataclass
class GenerateResult:
    """Result from :meth:`MailCapture.generate`."""

    tag: str
    """The generated tag, e.g. ``"funky-otter-a3f2b8"``."""

    email: str
    """The full capture email address for this tag."""
