# mailcapture

Official Python SDK for [MailCapture](https://mailcapture.app) — a real email capture API for integration testing OTP codes, verification links, and other transactional emails.

`mailcapture` is the Python client for the MailCapture service. Your application sends email to a unique MailCapture address during a test; this library retrieves that email so your test can assert on its contents — subject line, body text, OTP codes, links, and more. Both synchronous and async clients are included.

A MailCapture account is required — free and paid plans are available. [Sign up at mailcapture.app](https://mailcapture.app).

## Installation

```bash
pip install mailcapture
```

Requires Python 3.9+.

## Quick start

```python
from mailcapture import MailCapture

with MailCapture(api_key) as mc:
    mc.ping()  # validates key, caches your username

    # Send an email to {username}-signup@mailcapture.app, then:
    email = mc.wait_for("signup", timeout=15)

    print(email.subject)   # "Welcome to Acme!"
    print(email.otp)       # "123456" — extracted automatically
```

## The pattern for integration tests

1. **Clear** the inbox before each test
2. **Trigger** the action that sends the email (register, reset password, etc.)
3. **Wait** for the email — `wait_for` holds the connection open and returns the instant it arrives
4. **Assert** on subject, OTP, body, links
5. **Clean up** after

```python
# pytest example
import pytest
from mailcapture import MailCapture

@pytest.fixture(scope="session")
def mc():
    with MailCapture(os.environ["MAILCAPTURE_API_KEY"]) as client:
        client.ping()
        yield client

def test_signup_otp(mc):
    inbox = mc.inbox("signup")
    inbox.clear()                             # clean starting state

    register_user(inbox.address)              # "alice-signup@mailcapture.app"

    email = inbox.wait_for(timeout=10)

    assert email.subject == "Verify your email"
    assert re.match(r"^\d{6}$", email.otp)
```

## Async usage

```python
import asyncio
from mailcapture import AsyncMailCapture

async def test_signup():
    async with AsyncMailCapture(api_key) as mc:
        await mc.ping()
        inbox = mc.inbox("signup")
        await inbox.clear()

        await register_user(inbox.address)

        email = await inbox.wait_for(timeout=10)
        assert email.otp is not None
```

## API reference

### `MailCapture(api_key, *, base_url=..., request_timeout=...)`
### `AsyncMailCapture(api_key, *, base_url=..., request_timeout=...)`

Both clients accept the same constructor arguments.

| Argument | Default | Description |
|---|---|---|
| `api_key` | required | Your `mc_...` API key |
| `base_url` | `https://mailcapture.app` | Override for local dev |
| `request_timeout` | `10.0` | Default timeout in seconds |

Both support context manager usage (`with` / `async with`) for clean connection handling.

---

### `ping()` → `PingResult`

Validates your API key and returns your address template. Also caches your `username` so `address()` works synchronously.

```python
result = mc.ping()
print(result.username)          # "alice"
print(result.address_template)  # "alice-{tag}@mailcapture.app"
```

---

### `wait_for(tag, *, timeout=30, poll_timeout=10, after=None)` → `Capture`

Long-polls the API and returns the first email captured for the given tag. The server holds the connection open — no busy-waiting.

```python
email = mc.wait_for("signup", timeout=15)
```

| Argument | Default | Description |
|---|---|---|
| `tag` | required | Which inbox to watch |
| `timeout` | `30` | Total wait in seconds |
| `poll_timeout` | `10` | Per-poll server timeout in seconds (max 30) |
| `after` | 60s ago | Only return captures received after this `datetime` |

Raises `MailCaptureTimeoutError` if no email arrives in time.

---

### `inbox(tag)` → `Inbox` / `AsyncInbox`

Returns a scoped inbox object for a tag. Keeps test code clean.

```python
inbox = mc.inbox("password-reset")

inbox.address          # "alice-password-reset@mailcapture.app" (requires ping() first)
inbox.wait_for(timeout=10)
inbox.list(limit=5)
inbox.clear()
```

---

### `address(tag)` → `str`

Generates the capture email address synchronously. Requires `ping()` first.

```python
mc.ping()
mc.address("signup")  # "alice-signup@mailcapture.app"
```

---

### `list(*, tag=None, after=None, limit=None)` → `CaptureList`

List recent captures (newest first).

```python
result = mc.list(tag="signup", limit=10)
for email in result.items:
    print(email.subject)
```

---

### `get(capture_id)` → `Capture`

Get a single capture by ID. Raises `MailCaptureNotFoundError` if not found.

---

### `delete(tag)` → `None`

Delete all captures for a tag. Use before each test for a clean inbox.

---

## The `Capture` object

```python
@dataclass
class Capture:
    id: str           # UUID
    tag: str          # e.g. "signup"
    subject: str      # email subject line
    otp: str | None   # extracted OTP/code, if detected
    body_text: str | None
    body_html: str | None
    latency_ms: int   # time from send to capture, in ms
    status: str
    received_at: str  # ISO 8601 timestamp
```

The `otp` field is extracted automatically. If your OTP is embedded in a sentence, the service finds it for you. `None` if no code was detected.

---

## Error handling

All errors extend `MailCaptureError` and have a `.code` attribute.

```python
from mailcapture import (
    MailCaptureAuthError,
    MailCaptureTimeoutError,
    MailCaptureNotFoundError,
    MailCaptureNetworkError,
)

try:
    email = mc.wait_for("signup", timeout=10)
except MailCaptureTimeoutError as e:
    print(f"Waited {e.waited_seconds:.0f}s for tag '{e.tag}' — nothing arrived")
    print("Did the email actually send? Check your email service logs.")
except MailCaptureAuthError:
    print("Check your MAILCAPTURE_API_KEY environment variable.")
except MailCaptureNetworkError:
    print("Could not reach MailCapture. Check your network connection.")
```

| Exception | `.code` | When |
|---|---|---|
| `MailCaptureAuthError` | `UNAUTHORIZED` | Invalid or revoked API key |
| `MailCaptureTimeoutError` | `TIMEOUT` | `wait_for` exceeded its timeout |
| `MailCaptureNotFoundError` | `NOT_FOUND` | `get(id)` — capture not found |
| `MailCaptureNetworkError` | `NETWORK_ERROR` | Could not reach the API |
| `MailCaptureApiError` | varies | Unexpected API error |

---

## Parallel tests

Each tag is its own inbox — safe to run concurrently.

```python
import asyncio
from mailcapture import AsyncMailCapture

async def test_parallel():
    async with AsyncMailCapture(api_key) as mc:
        await mc.ping()

        signup = mc.inbox("signup")
        reset  = mc.inbox("password-reset")

        await asyncio.gather(signup.clear(), reset.clear())

        # Trigger both emails...

        signup_email, reset_email = await asyncio.gather(
            signup.wait_for(timeout=15),
            reset.wait_for(timeout=15),
        )
```

---

## Local development

```python
mc = MailCapture(api_key, base_url="http://localhost:3002")
```

---

## Environment variable

The SDK does not read environment variables automatically. Pass your key explicitly:

```python
import os
mc = MailCapture(os.environ["MAILCAPTURE_API_KEY"])
```

Get your API key at [mailcapture.app/admin/api-keys](https://mailcapture.app/admin/api-keys).
