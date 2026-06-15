"""Input sanitization utilities for security-aware plugins."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Match, Optional


def escape_mentions(text: str) -> str:
    """Replace @everyone and @here with spaced variants to prevent mentions."""
    text = text.replace("@everyone", "@ everyone")
    text = text.replace("@here", "@ here")
    return text


def truncate(text: str, max_len: int = 2000) -> str:
    """Truncate text to max_len with ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def safe_regex(pattern: str, subject: str, timeout_ms: int = 100) -> Optional[Match]:
    """Compile and match regex with timeout protection against ReDoS."""
    try:
        regex = re.compile(pattern)
    except re.error:
        return None

    def _match():
        return regex.search(subject)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_match)
            return future.result(timeout=timeout_ms / 1000.0)
    except FuturesTimeoutError:
        return None


def strip_injection_prefixes(text: str) -> str:
    """Remove common prompt-injection openers from the start of text."""
    prefixes = [
        "ignore previous instructions",
        "disregard previous instructions",
        "you are now",
        "pretend you are",
        "act as",
        "respond as if",
        "roleplay as",
        "assume the role of",
        "from now on",
    ]
    lower_text = text.lower()
    for prefix in prefixes:
        if lower_text.startswith(prefix):
            return text[len(prefix) :].lstrip()
    return text
