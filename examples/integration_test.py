"""
Example: OTP / 2FA email integration test patterns.

Requires:
    MAILCAPTURE_API_KEY=mc_... python examples/integration_test.py
"""
import asyncio
import os
import re

from mailcapture import AsyncMailCapture, MailCapture, MailCaptureTimeoutError

API_KEY = os.environ["MAILCAPTURE_API_KEY"]


# ---------------------------------------------------------------------------
# Sync examples
# ---------------------------------------------------------------------------


def example_basic_sync():
    """Most common pattern: clear, trigger, wait, assert, clean up."""
    with MailCapture(API_KEY) as mc:
        mc.ping()
        capture_email = mc.address("signup")

        # Clear any stale emails from previous runs
        mc.delete("signup")

        # ➜ Replace with your actual sign-up call
        print(f"Sign up your test user with: {capture_email}")
        # your_app.register(email=capture_email)

        email = mc.wait_for("signup", timeout=15)

        print(f"Subject:  {email.subject}")
        print(f"OTP:      {email.otp}")
        print(f"Latency:  {email.latency_ms}ms")

        mc.delete("signup")


def example_inbox_pattern():
    """Using Inbox for cleaner, tag-scoped code."""
    with MailCapture(API_KEY) as mc:
        mc.ping()
        inbox = mc.inbox("password-reset")

        inbox.clear()

        # ➜ Replace with your actual reset call
        print(f"Trigger a password reset to: {inbox.address}")
        # your_app.request_password_reset(inbox.address)

        email = inbox.wait_for(timeout=15)

        # Extract the reset link from the plain-text body
        link = re.search(r"https://\S+", email.body_text or "")
        print(f"Reset link: {link.group(0) if link else '(not found)'}")

        inbox.clear()


def example_timeout_handling():
    """Gracefully handle a timeout."""
    with MailCapture(API_KEY) as mc:
        try:
            email = mc.wait_for("signup", timeout=5)
            print(f"Got email: {email.subject}")
        except MailCaptureTimeoutError as e:
            print(f"No email after {e.waited_seconds:.0f}s for tag '{e.tag}'")
            print("Check that your email service is configured correctly.")


def example_list_and_inspect():
    """List recent captures and inspect them."""
    with MailCapture(API_KEY) as mc:
        result = mc.list(tag="signup", limit=5)
        print(f"Found {result.count} capture(s):")
        for email in result.items:
            print(f"  [{email.received_at}] {email.subject} — OTP: {email.otp}")


def example_local_server():
    """Point at a local development server."""
    with MailCapture(API_KEY, base_url="http://localhost:3002") as mc:
        result = mc.ping()
        print(f"Connected to local server, username: {result.username}")


# ---------------------------------------------------------------------------
# Async examples
# ---------------------------------------------------------------------------


async def example_async_basic():
    """Async version of the basic pattern."""
    async with AsyncMailCapture(API_KEY) as mc:
        await mc.ping()
        inbox = mc.inbox("signup")

        await inbox.clear()

        print(f"Sign up your test user with: {inbox.address}")
        # await your_app.register(email=inbox.address)

        email = await inbox.wait_for(timeout=15)
        print(f"OTP: {email.otp}")

        await inbox.clear()


async def example_parallel_inboxes():
    """Wait for multiple emails concurrently."""
    async with AsyncMailCapture(API_KEY) as mc:
        await mc.ping()

        signup_inbox = mc.inbox("signup")
        reset_inbox = mc.inbox("password-reset")

        await asyncio.gather(signup_inbox.clear(), reset_inbox.clear())

        # ➜ Trigger both emails
        print(f"Signup inbox:  {signup_inbox.address}")
        print(f"Reset inbox:   {reset_inbox.address}")

        signup_email, reset_email = await asyncio.gather(
            signup_inbox.wait_for(timeout=15),
            reset_inbox.wait_for(timeout=15),
        )

        print(f"Signup OTP:   {signup_email.otp}")
        print(f"Reset subject: {reset_email.subject}")


if __name__ == "__main__":
    print("=== Sync examples ===")
    example_basic_sync()
    example_inbox_pattern()
    example_list_and_inspect()

    print("\n=== Async examples ===")
    asyncio.run(example_async_basic())
    asyncio.run(example_parallel_inboxes())
