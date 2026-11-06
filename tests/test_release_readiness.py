"""Release-readiness checks for docs, metadata, and packaging."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

import easycord
from easycord.builtin_plugins import builtin_plugin_classes

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check_release_metadata.py"
SPEC = importlib.util.spec_from_file_location("check_release_metadata", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
collect_errors = CHECKER.collect_errors


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_version_metadata_and_docs_are_consistent() -> None:
    assert collect_errors(ROOT) == []

    pyproject = tomllib.loads(_read("pyproject.toml"))
    version = pyproject["project"]["version"]

    assert easycord.__version__ == version
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?", version)
    wheel_asset = f"releases/download/v{version}/easycord-{version}-py3-none-any.whl"
    sdist_asset = f"releases/download/v{version}/easycord-{version}.tar.gz"
    assert wheel_asset in _read("README.md")
    assert wheel_asset in _read("docs/getting-started.md")
    assert f"## EasyCord v{version}" in _read("CHANGELOG.md")
    assert f"releases/tag/v{version}" in pyproject["project"]["urls"]["Release"]
    assert wheel_asset in pyproject["project"]["urls"]["Download"]
    assert sdist_asset in _read("CHANGELOG.md")
    assert pyproject["project"]["scripts"]["easycord"] == "easycord.cli:main"
    assert "discord.py>=2.7.1,<3" in pyproject["project"]["dependencies"]
    assert "discord.py>=2.7.1,<3" in _read("docs/getting-started.md")


def test_manifest_includes_documentation_assets() -> None:
    manifest = _read("MANIFEST.in")

    required_lines = {
        "recursive-include docs *.md",
        "recursive-include examples *.py",
        "recursive-include context *.md",
    }
    for line in required_lines:
        assert line in manifest

    excluded_lines = {
        "exclude AGENTS.md",
        "exclude CLAUDE.md",
        "prune tests",
        "prune scripts",
        "prune release_v*",
        "prune .github",
    }
    for line in excluded_lines:
        assert line in manifest


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
    # Each API must remain discoverable in its current task guide. Historical
    # changelogs and plans cannot satisfy documentation coverage by themselves.
    guides = {
        "docs/developer-toolkit.md": (
            "BotConfig", "easycord new", "--template minimal", "--template plugin",
            "--template community", "--template ai", "--template database",
            "new --list-templates", "easycord doctor", "easycord audit-tools",
            "audit-tools bot:bot --fail-on-warnings", "doctor bot:bot --json",
            "audit-tools bot:bot --json", "inspect bot:bot --json", "sync-plan bot:bot",
            "ai.tools_audit", "severity", "fix", "audit_tool_registry",
            "format_doctor_report", "format_tool_audit",
        ),
        "docs/testing.md": (
            "FakeContext", "invoke()", "FakeContextBuilder", "with_roles",
            "invoke_user_command", "invoke_message_command", "invoke_component",
            "invoke_modal",
        ),
        "docs/building-commands.md": (
            "@cooldown", "@require_permissions", "@install_type", "@premium_required",
        ),
        "docs/error-handling.md": ("Plugin.on_error",),
        "docs/context-reference.md": (
            "ctx.send", "ctx.app_context", "ctx.entitlements", "ctx.forward",
            "silent", "suppress_embeds",
        ),
        "docs/database-guide.md": ("MemoryDatabase", "EASYCORD_DB_BACKEND=memory"),
        "docs/plugin-authoring.md": (
            "PluginManifest", "PluginScaffoldOptions", "PluginScaffoldResult",
            "PluginCheck", "PluginCheckReport", "create_in_project_plugin",
            "create_package_plugin", "create_plugin_scaffold", "load_plugin_manifest",
            "validate_plugin_manifest", "check_plugin_project", "discover_plugins",
            "load_entrypoint_plugins", "easycord plugin create", "easycord plugin check",
            "easycord plugin discover", "easycord.plugins",
        ),
    }
    for guide, terms in guides.items():
        for term in terms:
            assert term in _read(guide), f"{term} is missing from {guide}"


@pytest.mark.parametrize("page", ["README.md", "docs/getting-started.md", "docs/README.md"])
def test_beginner_guide_local_links_resolve(page: str) -> None:
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", _read(page)):
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        relative_path = target.split("#", 1)[0]
        assert (ROOT / page).parent.joinpath(relative_path).is_file(), (page, target)


def test_all_public_all_entries_resolve() -> None:
    missing = [name for name in easycord.__all__ if not hasattr(easycord, name)]
    assert missing == []
