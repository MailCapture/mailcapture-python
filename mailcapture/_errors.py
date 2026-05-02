from __future__ import annotations


class MailCaptureError(Exception):
    """Base class for all MailCapture errors. Check ``error.code`` for a machine-readable type."""

    code: str

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class MailCaptureAuthError(MailCaptureError):
    """Raised when authentication fails — invalid, expired, or revoked API key.

    Example::

        try:
            mc.ping()
        except MailCaptureAuthError:
            print("Check your MAILCAPTURE_API_KEY environment variable.")
    """

    def __init__(self, detail: str | None = None) -> None:
        parts = [
            "Authentication failed.",
            f'Server said: "{detail}".' if detail else "Your API key was rejected.",
            "Make sure your key is valid and has not been revoked.",
            "Keys look like: mc_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "Find your keys at https://mailcapture.app/admin/api-keys",
        ]
        super().__init__(" ".join(parts), "UNAUTHORIZED")


class MailCaptureNotFoundError(MailCaptureError):
    """Raised when a capture is not found.

    The capture may have expired, been deleted, or the ID may be wrong.
    """

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail or "Capture not found. It may have expired, been deleted, or the ID is incorrect.",
            "NOT_FOUND",
        )


class MailCaptureTimeoutError(MailCaptureError):
    """Raised by ``wait_for()`` when no email arrives before the timeout.

    Attributes:
        tag: The tag that was being waited on.
        waited_seconds: How many seconds elapsed before giving up.

    Example::

        try:
            email = mc.wait_for("signup", timeout=10)
        except MailCaptureTimeoutError as e:
            print(f"Gave up after {e.waited_seconds}s waiting for tag: {e.tag}")
    """

    tag: str
    waited_seconds: float

    def __init__(self, tag: str, waited_seconds: float, hint: str | None = None) -> None:
        hint_text = f" {hint}" if hint else ""
        super().__init__(
            f'No email arrived for tag "{tag}" within {waited_seconds:.0f}s.{hint_text}',
            "TIMEOUT",
        )
        self.tag = tag
        self.waited_seconds = waited_seconds


class MailCaptureNetworkError(MailCaptureError):
    """Raised when the SDK cannot reach the MailCapture API.

    Check your network connection and the ``base_url`` option.
    """

    def __init__(self, base_url: str, cause: BaseException | None = None) -> None:
        super().__init__(
            f"Could not reach the MailCapture API at {base_url}. "
            "Check your network connection and firewall settings.",
            "NETWORK_ERROR",
        )
        if cause is not None:
            self.__cause__ = cause


class MailCaptureApiError(MailCaptureError):
    """Raised when the API returns an unexpected error response.

    Attributes:
        status_code: HTTP status code returned by the server.
        detail: Human-readable detail from the server, if any.
    """

    status_code: int
    detail: str | None

    def __init__(self, status_code: int, code: str, detail: str | None = None) -> None:
        super().__init__(
            f"API error ({status_code}): {detail or code}",
            code,
        )
        self.status_code = status_code
        self.detail = detail
