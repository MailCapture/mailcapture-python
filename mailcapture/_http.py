"""Shared HTTP utilities used by both sync and async clients."""
from __future__ import annotations

from typing import Any, NoReturn

import httpx

from ._errors import (
    MailCaptureApiError,
    MailCaptureAuthError,
    MailCaptureNotFoundError,
)


def raise_api_error(response: httpx.Response) -> NoReturn:
    """Parse an error response and raise the appropriate exception."""
    try:
        body: dict[str, Any] = response.json()
    except Exception:
        body = {}

    code: str = body.get("message") or "UNKNOWN_ERROR"
    detail: str | None = body.get("detail")

    if response.status_code == 401:
        raise MailCaptureAuthError(detail)
    if response.status_code == 404:
        raise MailCaptureNotFoundError(detail)
    raise MailCaptureApiError(response.status_code, code, detail)


def parse_datetime_param(value: Any) -> str:
    """Convert a datetime or ISO string to an ISO 8601 string for API params."""
    from datetime import datetime

    if isinstance(value, datetime):
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)
