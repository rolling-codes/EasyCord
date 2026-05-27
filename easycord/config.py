"""Structured environment and config loading for EasyCord bots.

Eliminates the boilerplate of reading tokens, prefixes, and database paths
from environment variables or config files.  All values are validated on
construction so mis-configuration surfaces at startup, not mid-execution.

Example::

    from easycord import Bot, BotConfig

    cfg = BotConfig.from_env()
    bot = cfg.build_bot()
    bot.run(cfg.token)

Or from a JSON file::

    cfg = BotConfig.from_file("config.json")
    bot = cfg.build_bot()
    bot.run(cfg.token)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import Bot


_CONFIG_FIELDS = {
    "token",
    "guild_id",
    "db_backend",
    "db_path",
    "auto_sync",
    "log_level",
    "enable_health_command",
    "extra",
}
_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


@dataclass
class BotConfig:
    """Validated bot configuration.

    All parameters are keyword-only.  Use the class-method constructors
    ``from_env()`` or ``from_file()`` rather than constructing directly.

    Parameters
    ----------
    token:
        Discord bot token.  **Required** — raises ``ValueError`` if absent.
    guild_id:
        Development guild ID.  When set, slash commands are synced to this
        guild only (instant) instead of globally (up to 1 hour).
    db_backend:
        ``"memory"`` (default) or ``"sqlite"``.
    db_path:
        Path to the SQLite file, used only when ``db_backend="sqlite"``.
        Defaults to ``"data/bot.db"``.
    auto_sync:
        Auto-sync slash commands with Discord on startup.  Defaults to
        ``True``.
    log_level:
        Python logging level string (``"DEBUG"``, ``"INFO"``, etc.).
        Defaults to ``"INFO"``.
    enable_health_command:
        Automatically register a global ``/health`` command showing bot status.
        Defaults to ``False``.
    extra:
        Arbitrary key-value pairs for application-specific settings.
        Access via ``cfg.extra["my_key"]`` or ``cfg.get("my_key", default)``.
    """

    token: str
    guild_id: int | None = None
    db_backend: str = "memory"
    db_path: str = "data/bot.db"
    auto_sync: bool = True
    log_level: str = "INFO"
    enable_health_command: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError(
                "BotConfig: token is required. "
                "Set DISCORD_TOKEN or pass token= explicitly."
            )
        if self.db_backend not in ("memory", "sqlite"):
            raise ValueError(
                f"BotConfig: db_backend must be 'memory' or 'sqlite', got {self.db_backend!r}."
            )
        if self.log_level.upper() not in _VALID_LOG_LEVELS:
            raise ValueError(
                "BotConfig: log_level must be one of "
                f"{', '.join(sorted(_VALID_LOG_LEVELS))}, got {self.log_level!r}."
            )

    # ── Constructors ──────────────────────────────────────────

    @classmethod
    def from_env(cls, **overrides: Any) -> "BotConfig":
        """Build a BotConfig from environment variables.

        Reads the following env vars (all optional except ``DISCORD_TOKEN``):

        ========================  =============================================
        Variable                  Mapped to
        ========================  =============================================
        ``DISCORD_TOKEN``         ``token``
        ``DISCORD_GUILD_ID``      ``guild_id``
        ``EASYCORD_DB_BACKEND``   ``db_backend``
        ``EASYCORD_DB_PATH``      ``db_path``
        ``EASYCORD_AUTO_SYNC``    ``auto_sync``
        ``EASYCORD_LOG_LEVEL``    ``log_level``
        ``EASYCORD_HEALTH_COMMAND`` ``enable_health_command``
        ========================  =============================================

        Keyword arguments in *overrides* take precedence over env vars.

        Example::

            cfg = BotConfig.from_env(log_level="DEBUG")
        """
        override_extra = overrides.pop("extra", {})
        token = overrides.pop("token", None)
        if token is None:
            token = os.environ.get("DISCORD_TOKEN", "")
        raw_guild = overrides.pop("guild_id", None)
        if raw_guild is None:
            raw_guild = os.environ.get("DISCORD_GUILD_ID")
        try:
            guild_id = int(raw_guild) if raw_guild not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError(
                "BotConfig: DISCORD_GUILD_ID/guild_id must be an integer, "
                f"got {raw_guild!r}."
            ) from None
        db_backend = overrides.pop("db_backend", None)
        if db_backend is None:
            db_backend = os.environ.get("EASYCORD_DB_BACKEND", "memory")
        db_path = overrides.pop("db_path", None)
        if db_path is None:
            db_path = os.environ.get("EASYCORD_DB_PATH", "data/bot.db")
        raw_sync = overrides.pop("auto_sync", None)
        if raw_sync is None:
            raw_sync = os.environ.get("EASYCORD_AUTO_SYNC", "true")
            auto_sync = raw_sync.lower() not in ("0", "false", "no")
        else:
            if isinstance(raw_sync, str):
                auto_sync = raw_sync.lower() not in ("0", "false", "no")
            else:
                auto_sync = bool(raw_sync)
        log_level = overrides.pop("log_level", None)
        if log_level is None:
            log_level = os.environ.get("EASYCORD_LOG_LEVEL", "INFO")
        raw_health = overrides.pop("enable_health_command", None)
        if raw_health is None:
            raw_health = os.environ.get("EASYCORD_HEALTH_COMMAND", "false")
            enable_health_command = raw_health.lower() not in ("0", "false", "no")
        else:
            if isinstance(raw_health, str):
                enable_health_command = raw_health.lower() not in ("0", "false", "no")
            else:
                enable_health_command = bool(raw_health)
        return cls(
            token=token,
            guild_id=guild_id,
            db_backend=db_backend,
            db_path=db_path,
            auto_sync=auto_sync,
            log_level=log_level,
            enable_health_command=enable_health_command,
            extra={**overrides, **dict(override_extra or {})},
        )

    @classmethod
    def from_file(cls, path: str, **overrides: Any) -> "BotConfig":
        """Build a BotConfig from a JSON config file.

        The file must be a flat JSON object.  Keys match the dataclass field
        names.  An ``extra`` object in the file becomes ``BotConfig.extra``.
        Environment variables are read *first* as defaults; the file values
        override them; *overrides* kwargs override the file.

        Example ``config.json``::

            {
                "token": "YOUR_TOKEN",
                "guild_id": 123456789,
                "db_backend": "sqlite",
                "db_path": "data/prod.db",
                "log_level": "WARNING",
                "extra": {"webhook_url": "https://..."}
            }
        """
        with open(path, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"BotConfig.from_file: {path!r} must be a JSON object.")
        file_extra = data.pop("extra", {})
        override_extra = overrides.pop("extra", {})
        file_known = {k: data.pop(k) for k in list(data) if k in _CONFIG_FIELDS}
        override_known = {
            k: overrides.pop(k) for k in list(overrides) if k in _CONFIG_FIELDS
        }
        # Let env be the base, file overrides env, kwargs override file.
        inst = cls.from_env(**{**file_known, **override_known})
        # Merge extra in increasing precedence: loose file keys, file extra,
        # loose overrides, explicit override extra.
        inst.extra.update(data)
        inst.extra.update(dict(file_extra or {}))
        inst.extra.update(overrides)
        inst.extra.update(dict(override_extra or {}))
        return inst

    # ── Helpers ───────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return a value from ``extra``, or *default* if missing."""
        return self.extra.get(key, default)

    def build_bot(self, **kwargs: Any) -> "Bot":
        """Construct and return a :class:`Bot` wired to this config.

        Any keyword arguments are forwarded to ``Bot.__init__``, letting you
        inject intents, plugins, or other options without repeating config
        values.

        Example::

            cfg = BotConfig.from_env()
            bot = cfg.build_bot(load_builtin_plugins=True)
            bot.run(cfg.token)
        """
        import logging
        logging.basicConfig(level=getattr(logging, self.log_level.upper(), logging.INFO))

        from .bot import Bot

        kwargs.setdefault("auto_sync", self.auto_sync)
        kwargs.setdefault("sync_guild_id", self.guild_id)
        kwargs.setdefault("db_backend", self.db_backend)
        if self.db_backend == "sqlite":
            kwargs.setdefault("db_path", self.db_path)
        kwargs.setdefault("enable_health_command", self.enable_health_command)
        return Bot(**kwargs)
