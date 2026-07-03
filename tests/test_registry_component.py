"""Component registry: regex pre-compilation and TTL boundary regressions.

Guards two audit findings:
- #11 (perf): component route regex must be compiled at *registration*, not
  lazily on the first ``resolve_component`` call (which caused first-press jitter
  with many handlers). Already eager in v5.50.2 — this pins it so it stays eager.
- #9 (TTL boundary): expiry uses a strict ``>`` against ``time.time()``; mocking
  the clock catches coarse-tick / skew regressions.
"""
from __future__ import annotations

import re

from easycord.registry import InteractionRegistry


async def _noop(ctx) -> None:  # pragma: no cover - placeholder callback
    pass


class TestComponentRegexPrecompiled:
    def test_dynamic_pattern_compiled_at_registration(self) -> None:
        """A dynamic custom_id is compiled to a re.Pattern when registered,
        before resolve_component is ever called."""
        registry = InteractionRegistry()
        entry = registry.register_component("vote:{choice:int}", _noop)

        # Compiled eagerly — not None, and a real compiled pattern object.
        assert isinstance(entry.regex, re.Pattern)
        assert entry.variables == [("choice", "int")]

    def test_static_custom_id_has_no_regex(self) -> None:
        """A static (brace-free) custom_id needs no regex and stays None."""
        registry = InteractionRegistry()
        entry = registry.register_component("static_button", _noop)
        assert entry.regex is None

    def test_resolve_does_not_recompile(self) -> None:
        """resolve_component reuses the registration-time pattern object."""
        registry = InteractionRegistry()
        entry = registry.register_component("page:{n:int}", _noop)
        compiled = entry.regex

        resolved, params = registry.resolve_component("page:42")
        assert resolved is entry
        assert params == {"n": 42}
        # Same compiled object — resolution did not rebuild it.
        assert entry.regex is compiled


class TestComponentTTLBoundary:
    def test_entry_expires_strictly_after_expiry(self, monkeypatch) -> None:
        """At exactly expires_at the entry is expired (strict > boundary)."""
        monkeypatch.setattr("time.time", lambda: 1000.0)

        registry = InteractionRegistry()
        registry.register_component("ephemeral_btn", _noop, ttl=10.0)  # expires at 1010

        # Before expiry: active.
        monkeypatch.setattr("time.time", lambda: 1009.999)
        resolved, _ = registry.resolve_component("ephemeral_btn")
        assert resolved is not None

        # Exactly at expiry: expired (expires_at > now is False).
        monkeypatch.setattr("time.time", lambda: 1010.0)
        resolved, _ = registry.resolve_component("ephemeral_btn")
        assert resolved is None
