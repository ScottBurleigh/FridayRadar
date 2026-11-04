"""Shared 403 / captcha / Cloudflare detection. Do not work around a block."""
from __future__ import annotations

BLOCKED_MARKERS = (
    "cf-browser-verification",
    "cdn-cgi/challenge",
    "just a moment",
    "attention required! | cloudflare",
    "g-recaptcha",
    "hcaptcha",
    "cf-challenge",
    "enable javascript and cookies to continue",
)


class SiteBlocked(RuntimeError):
    """Public listing site refused the scrape. Keep the on-disk file."""


def looks_blocked(status: int | None, body: str) -> bool:
    if status in (401, 403, 429):
        return True
    low = (body or "")[:8000].lower()
    return any(m in low for m in BLOCKED_MARKERS)
