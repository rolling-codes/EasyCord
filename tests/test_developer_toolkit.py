"""Tests for the EasyCord developer toolkit."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from easycord import (
    Bot,
    ToolRegistry,
    ToolSafety,
    audit_tool_registry,
    format_doctor_report,
    format_interaction_inventory,
    format_sync_plan,
    format_tool_audit,
)
from easycord.cli import main
from easycord.testing import invoke_component, invoke_modal


def test_format_interaction_inventory_and_sync_plan() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Ping")
        async def ping(ctx):
            await ctx.respond("pong")

        inventory = format_interaction_inventory(bot.inspect_interactions())
        plan = format_sync_plan(bot.plan_command_sync(remote_commands=["old"]))

        assert "EasyCord interaction inventory" in inventory
        assert "slash: 1" in inventory
        assert "ping (Bot, global, enabled)" in inventory
        assert "added: ping" in plan
        assert "removed: old" in plan
    finally:
        asyncio.run(bot.close())


def test_format_doctor_report() -> None:
    rendered = format_doctor_report(
        {
            "checks": [
                {"name": "Python >= 3.10", "ok": True, "detail": "3.14.0"},
                {
                    "name": "DISCORD_TOKEN configured",
                    "ok": False,
                    "detail": "missing",
                    "code": "env.discord_token",
                    "severity": "error",
                    "fix": "Set DISCORD_TOKEN.",
                },
            ],
            "summary": "1 check(s) need attention.",
        }
    )

    assert "EasyCord doctor" in rendered
    assert "ok: Python >= 3.10 - 3.14.0" in rendered
    assert "error: DISCORD_TOKEN configured - missing" in rendered
    assert "fix: Set DISCORD_TOKEN." in rendered


def test_tool_audit_reports_safe_and_risky_tools() -> None:
    registry = ToolRegistry()
    registry.register(
        "safe_lookup",
        lambda ctx: "ok",
        "Read current state",
        ToolSafety.SAFE,
        require_guild=False,
        parameters={"type": "object", "properties": {}},
    )
    registry.register(
        "risky",
        lambda ctx, user_id: user_id,
        "No description provided.",
        ToolSafety.CONTROLLED,
        require_guild=False,
        timeout_ms=60000,
    )

    report = audit_tool_registry(registry)
    rendered = format_tool_audit(report)

    assert report["ok"] is False
    assert report["counts"]["total"] == 2
    assert report["counts"]["safe"] == 1
    assert report["counts"]["controlled"] == 1
    risky = next(tool for tool in report["tools"] if tool["name"] == "risky")
    assert {"name", "safety", "enabled", "description", "requires_guild"} <= set(risky)
    assert {"requires_admin", "permissions", "allowed_roles", "allowed_users"} <= set(risky)
    assert {"timeout_ms", "rate_limited", "warnings"} <= set(risky)
    assert any("admin, permission, role, or user gate" in item for item in risky["warnings"])
    assert any("JSON parameter schema" in item for item in risky["warnings"])
    assert "EasyCord AI tool audit" in rendered
    assert "risky" in rendered


def test_tool_audit_warns_when_restricted_tool_is_enabled() -> None:
    registry = ToolRegistry()
    registry.register(
        "danger",
        lambda ctx: "danger",
        "Dangerous action",
        ToolSafety.RESTRICTED,
        require_guild=False,
        require_admin=True,
        parameters={"type": "object", "properties": {}},
    )
    registry.enable("danger")

    report = audit_tool_registry(registry)

    tool = report["tools"][0]
    assert tool["enabled"] is True
    assert any("Restricted tools should remain disabled" in item for item in tool["warnings"])


async def test_invoke_component_static_and_dynamic_routes() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    seen: list[object] = []
    try:
        @bot.component("static:button")
        async def static_button(ctx):
            seen.append("static")
            await ctx.respond("static ok")

        @bot.component("ticket:close:{ticket_id:int}")
        async def close_ticket(ctx, ticket_id: int):
            seen.append(ticket_id)
            await ctx.respond(str(ticket_id))

        static_ctx = await invoke_component(bot, "static:button")
        dynamic_ctx = await invoke_component(bot, "ticket:close:42")

        assert seen == ["static", 42]
        assert static_ctx.last_response == "static ok"
        assert dynamic_ctx.last_response == "42"
    finally:
        await bot.close()


async def test_invoke_component_missing_raises_lookup_error() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        with pytest.raises(LookupError, match="Component"):
            await invoke_component(bot, "missing")
    finally:
        await bot.close()


async def test_invoke_modal_passes_field_values() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    seen = {}
    try:
        @bot.modal("profile:edit")
        async def edit_profile(ctx, data):
            seen.update(data)
            await ctx.respond(data["name"])

        ctx = await invoke_modal(bot, "profile:edit", name="Ada", title="Engineer")

        assert seen == {"name": "Ada", "title": "Engineer"}
        assert ctx.last_response == "Ada"
    finally:
        await bot.close()


def test_cli_new_creates_project(tmp_path: Path, capsys) -> None:
    project = tmp_path / "demo_bot"

    assert main(["new", str(project)]) == 0
    output = capsys.readouterr().out

    assert "Created EasyCord project" in output
    assert (project / "bot.py").exists()
    assert (project / "plugins" / "demo_bot.py").exists()
    assert (project / "tests" / "test_bot.py").exists()
    bot_source = (project / "bot.py").read_text(encoding="utf-8")
    assert "Bot(auto_sync=False)" in bot_source
    assert "db_backend=\"memory\"" not in bot_source


@pytest.mark.parametrize(
    ("template", "has_plugin"),
    [
        ("minimal", False),
        ("plugin", True),
        ("ai", True),
        ("database", True),
    ],
)
def test_cli_new_template_options(
    tmp_path: Path,
    capsys,
    template: str,
    has_plugin: bool,
) -> None:
    project = tmp_path / f"{template}_bot"

    assert main(["new", str(project), "--template", template]) == 0
    output = capsys.readouterr().out

    assert "Created EasyCord project" in output
    assert f"(template: {template})" in output
    assert (project / "bot.py").exists()
    assert (project / "tests" / "test_bot.py").exists()
    assert (project / "plugins" / f"{template}_bot.py").exists() is has_plugin
    assert "auto_sync=False" in (project / "bot.py").read_text(encoding="utf-8")


def test_cli_new_defaults_to_plugin_template(tmp_path: Path, capsys) -> None:
    project = tmp_path / "default_bot"

    assert main(["new", str(project)]) == 0
    capsys.readouterr()

    assert (project / "plugins" / "default_bot.py").exists()


def test_cli_new_lists_templates(capsys) -> None:
    assert main(["new", "--list-templates"]) == 0
    output = capsys.readouterr().out

    assert "EasyCord project templates" in output
    assert "minimal:" in output
    assert "plugin (default):" in output
    assert "ai:" in output
    assert "database:" in output


def test_cli_test_template_prints_and_writes(tmp_path: Path, capsys) -> None:
    assert main(["test-template", "greetings"]) == 0
    printed = capsys.readouterr().out
    assert "from plugins.greetings import GreetingsPlugin" in printed

    output = tmp_path / "tests" / "test_greetings.py"
    assert main(["test-template", "greetings", "--output", str(output)]) == 0
    assert "async def test_greetings_command" in output.read_text(encoding="utf-8")


def test_cli_plugin_create_check_and_discover(
    tmp_path: Path,
    monkeypatch,
    capsys,
    fake_entry_points,
) -> None:
    project = tmp_path / "app"

    assert main(["plugin", "create", "greetings", "--target", str(project)]) == 0
    output = capsys.readouterr().out
    assert "Created EasyCord plugin greetings" in output
    assert (project / "plugins" / "greetings.py").exists()
    assert (project / "plugins" / "greetings.easycord-plugin.json").exists()
    test_source = (project / "tests" / "test_greetings.py").read_text(encoding="utf-8")
    assert 'Bot(auto_sync=False, db_backend="memory")' in test_source

    json_project = tmp_path / "json_app"
    assert main(["plugin", "create", "json-greetings", "--target", str(json_project), "--json"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["manifest"]["name"] == "json_greetings"
    assert created["plugin_path"].endswith("json_greetings.py")

    assert main(["plugin", "check", str(project)]) == 0
    assert "EasyCord plugin check" in capsys.readouterr().out

    from importlib.metadata import EntryPoint

    entry_point = EntryPoint(
        name="greetings",
        value="plugins.greetings:GreetingsPlugin",
        group="easycord.plugins",
    )
    monkeypatch.setattr(
        "easycord.plugin_creator.metadata.entry_points",
        fake_entry_points(entry_point),
    )

    assert main(["plugin", "discover", "--json"]) == 0
    discovered = json.loads(capsys.readouterr().out)
    assert discovered[0]["name"] == "greetings"


def test_cli_inspect_and_sync_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    module = tmp_path / "sample_bot.py"
    module.write_text(
        "from easycord import Bot\n"
        "bot = Bot(auto_sync=False, db_backend='memory')\n"
        "@bot.slash(description='Ping')\n"
        "async def ping(ctx):\n"
        "    await ctx.respond('pong')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    assert main(["inspect", "sample_bot:bot"]) == 0
    assert "slash: 1" in capsys.readouterr().out

    assert main(["inspect", "sample_bot:bot", "--json"]) == 0
    inventory = json.loads(capsys.readouterr().out)
    assert set(inventory) == {
        "slash",
        "context_menu",
        "component",
        "modal",
        "autocomplete",
    }
    slash = inventory["slash"][0]
    for key in (
        "interaction_type",
        "name",
        "callback",
        "source",
        "guild_id",
        "metadata",
        "enabled",
        "sync_state",
        "registered_at",
        "expires_at",
    ):
        assert key in slash
    assert slash["name"] == "ping"
    assert slash["interaction_type"] == "slash"

    assert main(["sync-plan", "sample_bot:bot", "--remote", "old", "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert set(plan) == {"added", "changed", "removed", "unchanged", "warnings"}
    assert plan["added"] == ["ping"]
    assert plan["removed"] == ["old"]


def test_cli_doctor_reports_environment_and_bot(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = tmp_path / "sample_bot.py"
    module.write_text(
        "from easycord import Bot\n"
        "bot = Bot(auto_sync=False, db_backend='memory')\n"
        "@bot.slash(description='Ping')\n"
        "async def ping(ctx):\n"
        "    await ctx.respond('pong')\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    assert main(["doctor", "sample_bot:bot"]) == 0
    output = capsys.readouterr().out

    assert "EasyCord doctor" in output
    assert "ok: DISCORD_TOKEN configured - set" in output
    assert "ok: bot target imports - sample_bot:bot (1 interactions)" in output

    assert main(["doctor", "sample_bot:bot", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["failed"] == 0
    assert report["ok"] is True
    assert report["checks"]
    for check in report["checks"]:
        assert {"code", "name", "ok", "detail", "severity", "fix"} <= set(check)
    assert "ai.tools_audit" in {check["code"] for check in report["checks"]}


def test_cli_doctor_json_includes_actionable_fix(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = tmp_path / "bad_bot.py"
    module.write_text("bot = object()\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)

    assert main(["doctor", "bad_bot:bot", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)

    checks = {check["code"]: check for check in report["checks"]}
    assert report["ok"] is False
    assert checks["env.discord_token"]["fix"]
    assert checks["bot.import"]["fix"]
    assert checks["bot.import"]["severity"] == "error"


def test_cli_audit_tools_outputs_text_and_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = tmp_path / "tool_bot.py"
    module.write_text(
        "from easycord import Bot, ToolSafety, ai_tool, Plugin\n"
        "bot = Bot(auto_sync=False, db_backend='memory')\n"
        "class Tools(Plugin):\n"
        "    @ai_tool(description='Read data', require_guild=False)\n"
        "    async def read_data(self, ctx):\n"
        "        return 'ok'\n"
        "    @ai_tool(description='No description provided.', safety=ToolSafety.CONTROLLED, require_guild=False)\n"
        "    async def risky(self, ctx, value: str):\n"
        "        return value\n"
        "bot.add_plugin(Tools())\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    assert main(["audit-tools", "tool_bot:bot"]) == 0
    output = capsys.readouterr().out
    assert "EasyCord AI tool audit" in output
    assert "risky" in output

    assert main(["audit-tools", "tool_bot:bot", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"ok", "summary", "counts", "tools", "warnings"}
    assert report["tools"]
    for tool in report["tools"]:
        assert {
            "name",
            "safety",
            "enabled",
            "description",
            "requires_guild",
            "requires_admin",
            "permissions",
            "allowed_roles",
            "allowed_users",
            "timeout_ms",
            "rate_limited",
            "warnings",
        } <= set(tool)

    assert main(["audit-tools", "tool_bot:bot", "--fail-on-warnings"]) == 1
    assert "EasyCord AI tool audit" in capsys.readouterr().out


def test_cli_import_errors_are_clear(tmp_path: Path, monkeypatch) -> None:
    module = tmp_path / "not_a_bot.py"
    module.write_text("bot = object()\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(SystemExit, match="not an easycord.Bot"):
        main(["inspect", "not_a_bot:bot"])
