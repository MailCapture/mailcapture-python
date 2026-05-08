"""
MailCapture Python SDK
======================

Official Python SDK for the MailCapture email testing API.

Quick start::

    from mailcapture import MailCapture

    with MailCapture(api_key) as mc:
        mc.ping()
        email = mc.wait_for("signup", timeout=15)
        print(email.otp)

Async::

    from mailcapture import AsyncMailCapture

    async with AsyncMailCapture(api_key) as mc:
        await mc.ping()
        email = await mc.wait_for("signup", timeout=15)
"""
from ._async_client import AsyncMailCapture
from ._client import MailCapture
from ._generate import generate_tag
from ._errors import (
    MailCaptureApiError,
    MailCaptureAuthError,
    MailCaptureError,
    MailCaptureNetworkError,
    MailCaptureNotFoundError,
    MailCaptureTimeoutError,
)
from ._inbox import AsyncInbox, Inbox
from ._types import Capture, CaptureList, GenerateResult, LatestResult, PingResult

__all__ = [
    # Clients
    "MailCapture",
    "AsyncMailCapture",
    # Inbox helpers
    "Inbox",
    "AsyncInbox",
    # Tag generation
    "generate_tag",
    # Types
    "Capture",
    "CaptureList",
    "GenerateResult",
    "LatestResult",
    "PingResult",
    # Errors
    "MailCaptureError",
    "MailCaptureAuthError",
    "MailCaptureNotFoundError",
    "MailCaptureTimeoutError",
    "MailCaptureNetworkError",
    "MailCaptureApiError",
]

__version__ = "0.1.0"
