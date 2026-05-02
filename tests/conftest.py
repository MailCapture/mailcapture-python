"""Shared test fixtures and helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def capture_dict(
    *,
    id: str = "abc-123",
    tag: str = "signup",
    subject: str = "Welcome",
    otp: str | None = "123456",
    body_text: str | None = "Your code is 123456",
    body_html: str | None = "<p>Your code is 123456</p>",
    latency_ms: int = 100,
    status: str = "captured",
    received_at: str | None = None,
) -> dict:
    return {
        "id": id,
        "tag": tag,
        "subject": subject,
        "otp": otp,
        "body_text": body_text,
        "body_html": body_html,
        "latency_ms": latency_ms,
        "status": status,
        "received_at": received_at or datetime.now(timezone.utc).isoformat(),
    }


def ping_dict(username: str = "alice") -> dict:
    return {
        "status": "ok",
        "username": username,
        "address_template": f"{username}-{{tag}}@mailcapture.app",
        "example": f"{username}-signup@mailcapture.app",
    }


def timeout_dict() -> dict:
    return {"status": "error", "message": "REQUEST_TIMEOUT", "detail": "Timed out"}


def auth_error_dict() -> dict:
    return {"status": "fail", "message": "UNAUTHORIZED", "detail": "Invalid API key"}


def not_found_dict() -> dict:
    return {"status": "fail", "message": "NOT_FOUND", "detail": "Resource not found"}
