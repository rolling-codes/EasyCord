"""Reusable option validators and parsers for command handlers."""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


class ValidationError(ValueError):
    """User-safe validation failure."""

    def __init__(self, message: str, *, key: str = "errors.validation") -> None:
        super().__init__(message)
        self.message = message
        self.key = key

    def user_message(self, ctx) -> str:
        return ctx.t(self.key, default=self.message)


class Duration:
    """Parse duration strings such as ``10s``, ``5m``, ``2h``, or ``1d``."""

    _pattern = re.compile(r"^\s*(\d+(?:\.\d+)?)([smhd])\s*$", re.IGNORECASE)
    _multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    def __call__(self, value: str | int | float) -> float:
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValidationError("Duration must be positive.")
            return float(value)
        match = self._pattern.match(str(value))
        if match is None:
            raise ValidationError("Duration must look like 10s, 5m, 2h, or 1d.")
        amount = float(match.group(1))
        return amount * self._multipliers[match.group(2).lower()]


class URL:
    """Validate HTTP or HTTPS URLs."""

    def __call__(self, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("Enter a valid http(s) URL.")
        return value


class Snowflake:
    """Validate and coerce a Discord snowflake ID."""

    def __call__(self, value: str | int) -> int:
        text = str(value)
        if not re.fullmatch(r"\d{15,22}", text):
            raise ValidationError("Enter a valid Discord ID.")
        return int(text)


@dataclass(frozen=True)
class Range:
    """Validate numeric min/max bounds."""

    min: float | None = None
    max: float | None = None

    def __post_init__(self) -> None:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"Range min ({self.min}) must be <= max ({self.max})")

    def __call__(self, value: int | float) -> int | float:
        if self.min is not None and value < self.min:
            raise ValidationError(f"Value must be at least {self.min}.")
        if self.max is not None and value > self.max:
            raise ValidationError(f"Value must be at most {self.max}.")
        return value


@dataclass(frozen=True)
class Regex:
    """Validate text with a regex plus optional length bounds."""

    pattern: str
    min_length: int | None = None
    max_length: int | None = None

    def __call__(self, value: str) -> str:
        if self.min_length is not None and len(value) < self.min_length:
            raise ValidationError(f"Must be at least {self.min_length} characters.")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError(f"Must be at most {self.max_length} characters.")
        if re.fullmatch(self.pattern, value) is None:
            raise ValidationError("Value has an invalid format.")
        return value


class ChoiceSet:
    """Validate that a value is one of a fixed set."""

    def __init__(self, *choices):
        if not choices:
            raise ValueError("ChoiceSet requires at least one choice")
        self.choices = set(choices)

    def __call__(self, value):
        if value not in self.choices:
            allowed = ", ".join(str(choice) for choice in sorted(self.choices, key=str))
            raise ValidationError(f"Choose one of: {allowed}.")
        return value


__all__ = [
    "ChoiceSet",
    "Duration",
    "Range",
    "Regex",
    "Snowflake",
    "URL",
    "ValidationError",
]
