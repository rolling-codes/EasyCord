"""Release-readiness checks for docs, metadata, and packaging."""
from __future__ import annotations

import re
from pathlib import Path

import easycord
from easycord.builtin_plugins import builtin_plugin_classes

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_version_metadata_and_docs_are_consistent() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    version = pyproject["project"]["version"]

    assert easycord.__version__ == version
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?", version)
    assert f"releases/download/v{version}/EasyCord-v{version}.zip" in _read("README.md")
    assert f"releases/download/v{version}/EasyCord-v{version}.zip" in _read("docs/getting-started.md")
    assert f"## EasyCord v{version}" in _read("CHANGELOG.md")
    assert f"releases/tag/v{version}" in pyproject["project"]["urls"]["Release"]
    assert f"releases/download/v{version}/EasyCord-v{version}.zip" in pyproject["project"]["urls"]["Download"]
    assert pyproject["project"]["scripts"]["easycord"] == "easycord.cli:main"
    assert "discord.py>=2.7.1,<3" in pyproject["project"]["dependencies"]
    assert "discord.py>=2.7.1,<3" in _read("docs/getting-started.md")


def test_manifest_includes_documentation_assets() -> None:
    manifest = _read("MANIFEST.in")

    required_lines = {
        "include AGENTS.md",
        "include CLAUDE.md",
        "recursive-include docs *.md",
        "recursive-include examples *.py",
        "recursive-include context *.md",
    }
    for line in required_lines:
        assert line in manifest

    assert "exclude AGENTS.md" not in manifest
    assert "exclude CLAUDE.md" not in manifest


def test_docs_match_builtin_plugin_loader() -> None:
    plugin_names = {cls.__name__ for cls in builtin_plugin_classes()}
    # Verify required starter plugins without blocking future additions.
    assert plugin_names >= {
        "WelcomePlugin",
        "TagsPlugin",
        "PollsPlugin",
        "LevelsPlugin",
    }

    docs = "\n".join(
        [
            _read("README.md"),
            _read("docs/getting-started.md"),
            _read("context/architecture.md"),
            _read("AGENTS.md"),
        ]
    )
    for friendly_name in ("welcome", "tags", "polls", "levels"):
        assert friendly_name in docs.lower()
    assert "load_builtin_plugins=True` loads the starter set" in docs
    assert "10+ bundled plugins" not in docs
    assert "bot.load_plugin(" not in docs
    assert "ModerationPlugin()" not in _read("docs/getting-started.md")


def test_release_docs_cover_new_public_features() -> None:
    docs = "\n".join(
        [
            _read("README.md"),
            _read("docs/getting-started.md"),
            _read("docs/developer-toolkit.md"),
            _read("CHANGELOG.md"),
        ]
    )
    for term in (
        "BotConfig",
        "FakeContext",
        "invoke()",
        "@cooldown",
        "@require_permissions",
        "@install_type",
        "@premium_required",
        "Plugin.on_error",
        "ctx.send",
        "ctx.app_context",
        "ctx.entitlements",
        "ctx.forward",
        "silent",
        "suppress_embeds",
        "easycord new",
        "--template minimal",
        "--template plugin",
        "--template ai",
        "--template database",
        "new --list-templates",
        "easycord doctor",
        "easycord audit-tools",
        "audit-tools --fail-on-warnings",
        "doctor bot:bot --json",
        "audit-tools bot:bot --json",
        "inspect bot:bot --json",
        "sync-plan bot:bot",
        "ai.tools_audit",
        "severity",
        "fix",
        "audit_tool_registry",
        "format_doctor_report",
        "format_tool_audit",
        "FakeContextBuilder",
        "MemoryDatabase",
        "EASYCORD_DB_BACKEND=memory",
        "with_roles",
        "invoke_user_command",
        "invoke_message_command",
        "invoke_component",
        "invoke_modal",
    ):
        assert term in docs


def test_all_public_all_entries_resolve() -> None:
    missing = [name for name in easycord.__all__ if not hasattr(easycord, name)]
    assert missing == []
