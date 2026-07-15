"""Command line tools for EasyCord developers."""
from __future__ import annotations

import argparse
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import platform
import warnings
from typing import Literal, Sequence

from .bot import Bot
from .formatters import (
    format_doctor_report,
    format_interaction_inventory,
    format_sync_plan,
    format_tool_audit,
)
from .plugin_creator import (
    PluginScaffoldOptions,
    check_plugin_project,
    create_plugin_scaffold,
    discover_plugins,
)
from .tools import audit_tool_registry

ProjectTemplate = Literal["minimal", "plugin", "ai", "database"]
_PROJECT_TEMPLATES: tuple[ProjectTemplate, ...] = (
    "minimal",
    "plugin",
    "ai",
    "database",
)
_PROJECT_TEMPLATE_DESCRIPTIONS = {
    "minimal": "Single-file bot with a slash command and non-SQL tests.",
    "plugin": "Plugin-oriented scaffold with a memory database; this is the default.",
    "ai": "Plugin scaffold with an AI-provider placeholder command and memory database.",
    "database": "Plugin scaffold with SQLite app setup and in-memory tests.",
}


def _class_name(name: str) -> str:
    parts = re.split(r"[^0-9A-Za-z]+", name)
    cleaned = "".join(part[:1].upper() + part[1:] for part in parts if part)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"Plugin{cleaned}"
    return cleaned


def _module_name(name: str) -> str:
    lowered = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    if not lowered:
        return "plugin"
    if lowered[0].isdigit():
        lowered = f"plugin_{lowered}"
    renamed = lowered
    if renamed.startswith("test_"):
        renamed = f"bot_{renamed}"
    if renamed.endswith("_test"):
        renamed = f"{renamed}_plugin"
    if renamed != lowered:
        warnings.warn(
            f"Project name {name!r} maps to module {lowered!r}, which pytest "
            f"would collect as a test file; renamed to {renamed!r}.",
            UserWarning,
            stacklevel=2,
        )
    return renamed


def _load_bot(spec: str) -> Bot:
    if ":" not in spec:
        raise SystemExit("Bot target must use 'module:object', for example 'bot:bot'.")
    module_name, object_name = spec.split(":", 1)
    if not module_name or not object_name:
        raise SystemExit("Bot target must include both module and object names.")
    if "" not in sys.path:
        sys.path.insert(0, "")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Could not import module {module_name!r}: {exc}") from exc
    try:
        candidate = getattr(module, object_name)
    except AttributeError as exc:
        raise SystemExit(
            f"Module {module_name!r} has no object named {object_name!r}."
        ) from exc
    if not isinstance(candidate, Bot):
        raise SystemExit(
            f"{spec!r} resolved to {type(candidate).__name__}, not an easycord.Bot."
        )
    return candidate


def _base_project_files(name: str) -> dict[str, str]:
    return {
        ".env.example": "DISCORD_TOKEN=replace-me\n",
        "pyproject.toml": f'''\
            [project]
            name = "{_module_name(name).replace("_", "-")}-bot"
            version = "0.1.0"
            requires-python = ">=3.10"
            dependencies = ["easycord"]

            [project.optional-dependencies]
            dev = ["pytest>=7", "pytest-asyncio>=0.21"]

            [tool.pytest.ini_options]
            asyncio_mode = "auto"
            testpaths = ["tests"]
            ''',
    }


def _minimal_project_files(name: str) -> dict[str, str]:
    return {
        **_base_project_files(name),
        "bot.py": '''\
            import os

            from easycord import Bot


            bot = Bot(auto_sync=False)


            @bot.slash(description="Ping the bot")
            async def ping(ctx):
                await ctx.respond("Pong!")


            if __name__ == "__main__":
                bot.run(os.environ["DISCORD_TOKEN"])
            ''',
        "tests/test_bot.py": '''\
            from bot import bot
            from easycord.testing import invoke


            async def test_ping_command():
                ctx = await invoke(bot, "ping")
                ctx.assert_content("Pong!")
            ''',
    }


def _plugin_project_files(name: str) -> dict[str, str]:
    plugin_module = _module_name(name)
    plugin_class = f"{_class_name(name)}Plugin"
    return {
        **_base_project_files(name),
        "bot.py": f'''\
            import os

            from easycord import Bot

            from plugins.{plugin_module} import {plugin_class}


            bot = Bot(auto_sync=False)
            bot.add_plugin({plugin_class}())


            if __name__ == "__main__":
                bot.run(os.environ["DISCORD_TOKEN"])
            ''',
        "plugins/__init__.py": "",
        f"plugins/{plugin_module}.py": f'''\
            from easycord import Plugin, slash


            class {plugin_class}(Plugin):
                @slash(description="Say hello")
                async def hello(self, ctx):
                    await ctx.respond(f"Hello, {{ctx.user.display_name}}!")
            ''',
        "tests/test_bot.py": '''\
            from bot import bot
            from easycord.testing import invoke


            async def test_hello_command():
                ctx = await invoke(bot, "hello")
                ctx.assert_contains("Hello")
            ''',
    }


def _ai_project_files(name: str) -> dict[str, str]:
    plugin_module = _module_name(name)
    plugin_class = f"{_class_name(name)}AssistantPlugin"
    return {
        **_base_project_files(name),
        "bot.py": f'''\
            import os

            from easycord import Bot

            from plugins.{plugin_module} import {plugin_class}


            bot = Bot(auto_sync=False)
            bot.add_plugin({plugin_class}())


            if __name__ == "__main__":
                bot.run(os.environ["DISCORD_TOKEN"])
            ''',
        "plugins/__init__.py": "",
        f"plugins/{plugin_module}.py": f'''\
            from easycord import Plugin, slash


            class {plugin_class}(Plugin):
                @slash(description="Ask the configured AI provider")
                async def ask(self, ctx, prompt: str):
                    try:
                        answer = await ctx.ai(prompt)
                    except RuntimeError:
                        await ctx.respond(
                            "No AI provider is configured yet.",
                            ephemeral=True,
                        )
                        return
                    await ctx.respond(answer[:2000])
            ''',
        "tests/test_bot.py": '''\
            from bot import bot
            from easycord.testing import invoke


            async def test_ask_command_without_provider_is_friendly():
                ctx = await invoke(bot, "ask", prompt="hello")
                ctx.assert_contains("No AI provider")
                assert ctx.was_ephemeral is True
            ''',
    }


def _database_project_files(name: str) -> dict[str, str]:
    plugin_module = _module_name(name)
    plugin_class = f"{_class_name(name)}DatabasePlugin"
    return {
        **_base_project_files(name),
        "bot.py": f'''\
            import os

            from easycord import Bot, SQLiteDatabase

            from plugins.{plugin_module} import {plugin_class}


            bot = Bot(
                auto_sync=False,
                database=SQLiteDatabase(path="data/bot.db"),
            )
            bot.add_plugin({plugin_class}())


            if __name__ == "__main__":
                bot.run(os.environ["DISCORD_TOKEN"])
            ''',
        "plugins/__init__.py": "",
        f"plugins/{plugin_module}.py": f'''\
            from easycord import Plugin, slash


            class {plugin_class}(Plugin):
                @slash(description="Store a guild note")
                async def set_note(self, ctx, note: str):
                    await ctx.interaction.client.db.set(ctx.guild_id or 0, "note", note)
                    await ctx.respond("Note saved.", ephemeral=True)

                @slash(description="Show the stored guild note")
                async def get_note(self, ctx):
                    note = await ctx.interaction.client.db.get(
                        ctx.guild_id or 0,
                        "note",
                        "No note saved.",
                    )
                    await ctx.respond(note)
            ''',
        "tests/test_bot.py": f'''\
            from easycord import Bot
            from easycord.testing import invoke

            from plugins.{plugin_module} import {plugin_class}


            async def test_note_round_trip():
                bot = Bot(auto_sync=False, db_backend="memory")
                try:
                    bot.add_plugin({plugin_class}())
                    saved = await invoke(bot, "set_note", note="Ship it")
                    shown = await invoke(bot, "get_note")
                    saved.assert_contains("Note saved")
                    shown.assert_content("Ship it")
                finally:
                    await bot.close()
            ''',
    }


def _project_files(name: str, template: ProjectTemplate) -> dict[str, str]:
    if template == "minimal":
        return _minimal_project_files(name)
    if template == "plugin":
        return _plugin_project_files(name)
    if template == "ai":
        return _ai_project_files(name)
    if template == "database":
        return _database_project_files(name)
    raise SystemExit(f"Unknown project template: {template}")


def _write_new_project(
    target: Path,
    name: str,
    *,
    template: ProjectTemplate = "plugin",
) -> list[Path]:
    files = _project_files(name, template)
    written: list[Path] = []
    for relative, content in files.items():
        path = target / relative
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        written.append(path)
    return written


def _test_template(plugin_name: str) -> str:
    plugin_class = f"{_class_name(plugin_name)}Plugin"
    module_name = _module_name(plugin_name)
    return textwrap.dedent(
        f'''\
        from easycord import Bot
        from easycord.testing import invoke

        from plugins.{module_name} import {plugin_class}


        async def test_{module_name}_command():
            bot = Bot(auto_sync=False, db_backend="memory")
            try:
                bot.add_plugin({plugin_class}())
                ctx = await invoke(bot, "hello")
                assert ctx.response_count == 1
            finally:
                await bot.close()
        '''
    )


def cmd_new(args: argparse.Namespace) -> int:
    if args.list_templates:
        print("EasyCord project templates")
        for template in _PROJECT_TEMPLATES:
            default = " (default)" if template == "plugin" else ""
            print(f"  {template}{default}: {_PROJECT_TEMPLATE_DESCRIPTIONS[template]}")
        return 0
    if not args.name:
        raise SystemExit("Project name is required unless --list-templates is used.")
    target = Path(args.name)
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Directory {target} already exists and is not empty.")
    written = _write_new_project(target, target.name, template=args.template)
    print(f"Created EasyCord project at {target} (template: {args.template})")
    for path in written:
        print(f"  {path.relative_to(target)}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    bot = _load_bot(args.target)
    inventory = bot.inspect_interactions()
    if args.json:
        print(json.dumps(inventory, indent=2, default=str))
    else:
        print(format_interaction_inventory(inventory))
    return 0


def cmd_sync_plan(args: argparse.Namespace) -> int:
    bot = _load_bot(args.target)
    plan = bot.plan_command_sync(remote_commands=args.remote or None)
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(format_sync_plan(plan))
    return 0


def _apply_schema_fixes(schema_plugins: list) -> int:
    """Sync-heal all guild configs for plugins that expose SCHEMA. Returns count fixed."""
    fixed = 0
    for plugin, schema in schema_plugins:
        store_base = getattr(getattr(getattr(plugin, "config", None), "store", None), "_base", None)
        if store_base is None:
            continue
        for guild_json in Path(store_base).glob("*.json"):
            try:
                data = json.loads(guild_json.read_text(encoding="utf-8"))
                other: dict = data.get("other") or {}
                section = other.get(schema.key)
                healed, changes = schema.apply(section)
                if not changes:
                    continue
                other[schema.key] = healed
                data["other"] = other
                tmp = guild_json.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
                tmp.replace(guild_json)
                fixed += 1
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                warnings.warn(
                    f"Skipping schema fix for {guild_json}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
    return fixed


def _doctor_report(target: str | None = None, *, fix_configs: bool = False) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def add(
        code: str,
        name: str,
        ok: bool,
        detail: str = "",
        *,
        severity: str = "error",
        fix: str = "",
    ) -> None:
        checks.append(
            {
                "code": code,
                "name": name,
                "ok": ok,
                "detail": detail,
                "severity": "ok" if ok else severity,
                "fix": "" if ok else fix,
            }
        )

    python_version = platform.python_version()
    add(
        "python.version",
        "Python >= 3.10",
        sys.version_info >= (3, 10),
        python_version,
        fix="Install Python 3.10 or newer, then recreate your virtual environment.",
    )

    try:
        discord_version = metadata.version("discord.py")
    except metadata.PackageNotFoundError:
        add(
            "dependency.discord_py",
            "discord.py installed",
            False,
            "package not found",
            fix='Install EasyCord dependencies with: pip install -e ".[dev]"',
        )
    else:
        add("dependency.discord_py", "discord.py installed", True, f"v{discord_version}")

    add(
        "env.discord_token",
        "DISCORD_TOKEN configured",
        bool(os.getenv("DISCORD_TOKEN")),
        "set" if os.getenv("DISCORD_TOKEN") else "missing",
        fix="Set DISCORD_TOKEN in your shell or .env file before running the bot.",
    )

    if target:
        try:
            bot = _load_bot(target)
        except SystemExit as exc:
            add(
                "bot.import",
                "bot target imports",
                False,
                str(exc),
                fix="Check the module:object path and import the bot from the project root.",
            )
        else:
            inventory = bot.inspect_interactions()
            total = sum(len(entries) for entries in inventory.values())
            add("bot.import", "bot target imports", True, f"{target} ({total} interactions)")
            add(
                "bot.auto_sync",
                "auto_sync disabled for local imports",
                not bot._auto_sync,
                "disabled" if not bot._auto_sync else "enabled",
                severity="warning",
                fix="Use Bot(auto_sync=False) while importing bots in local tests and diagnostics.",
            )
            tool_registry = getattr(bot, "tool_registry", None)
            if tool_registry is not None and getattr(tool_registry, "_tools", None):
                audit = audit_tool_registry(tool_registry)
                add(
                    "ai.tools_audit",
                    "AI tools safety audit",
                    True,
                    audit["summary"],
                    severity="warning",
                    fix=f"Run: easycord audit-tools {target}",
                )

            # --- plugin config schema drift ------------------------------------
            schema_plugins = []
            for _plugin in getattr(bot, "_plugins", []):
                _mod = sys.modules.get(type(_plugin).__module__)
                if _mod is not None and hasattr(_mod, "SCHEMA"):
                    schema_plugins.append((_plugin, _mod.SCHEMA))

            schema_issues: list[str] = []
            for _plugin, _schema in schema_plugins:
                _store_base = getattr(
                    getattr(getattr(_plugin, "config", None), "store", None),
                    "_base",
                    None,
                )
                if _store_base is None:
                    continue
                for _guild_json in Path(_store_base).glob("*.json"):
                    try:
                        _data = json.loads(_guild_json.read_text(encoding="utf-8"))
                        _other: dict = _data.get("other") or {}
                        _, _changes = _schema.apply(_other.get(_schema.key))
                        if _changes:
                            schema_issues.append(
                                f"{type(_plugin).__name__} guild "
                                f"{_guild_json.stem}: {', '.join(_changes)}"
                            )
                    except (json.JSONDecodeError, OSError, ValueError) as exc:
                        schema_issues.append(
                            f"{type(_plugin).__name__} guild "
                            f"{_guild_json.stem}: unreadable config ({exc})"
                        )

            if schema_issues:
                _fixed = _apply_schema_fixes(schema_plugins) if fix_configs else 0
                add(
                    "config.schema_health",
                    "Plugin config schema drift",
                    fix_configs and _fixed >= 0,
                    f"{len(schema_issues)} guild config(s) need healing"
                    if not fix_configs
                    else f"{_fixed} guild config(s) healed",
                    severity="warning",
                    fix="" if fix_configs else f"Run: easycord doctor --fix-configs {target}",
                )
            elif schema_plugins:
                add(
                    "config.schema_health",
                    "Plugin config schemas healthy",
                    True,
                    f"{len(schema_plugins)} schema(s) checked",
                )

    # --- generic config file health -------------------------------------------
    _ec_root = Path(".easycord")
    if _ec_root.exists():
        _tmp_files = list(_ec_root.rglob("*.tmp"))
        for _tmp_f in _tmp_files:
            add(
                "config.leftover_tmp",
                f"Leftover .tmp: {_tmp_f}",
                False,
                str(_tmp_f),
                severity="warning",
                fix=f"Delete {_tmp_f} — residue from an interrupted atomic config write.",
            )
        _corrupt: list[str] = []
        for _jf in _ec_root.rglob("*.json"):
            try:
                json.loads(_jf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _corrupt.append(str(_jf))
        for _corrupt_path in _corrupt:
            add(
                "config.corrupt_json",
                f"Corrupt config JSON: {_corrupt_path}",
                False,
                _corrupt_path,
                severity="error",
                fix=f"Inspect or delete {_corrupt_path}.",
            )
        if not _tmp_files and not _corrupt:
            add("config.health", "Config files healthy", True, str(_ec_root))

    failed = sum(1 for check in checks if not check["ok"])
    return {
        "checks": checks,
        "failed": failed,
        "ok": failed == 0,
        "summary": "All checks passed." if failed == 0 else f"{failed} check(s) need attention.",
    }


def cmd_doctor(args: argparse.Namespace) -> int:
    report = _doctor_report(args.target, fix_configs=args.fix_configs)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_doctor_report(report))
    return 0 if report["failed"] == 0 else 1


def cmd_audit_tools(args: argparse.Namespace) -> int:
    bot = _load_bot(args.target)
    report = audit_tool_registry(bot.tool_registry)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_tool_audit(report))
    return 1 if args.fail_on_warnings and report["warnings"] else 0


def cmd_test_template(args: argparse.Namespace) -> int:
    content = _test_template(args.plugin_name)
    if args.output:
        path = Path(args.output)
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    else:
        print(content, end="")
    return 0


def cmd_plugin_create(args: argparse.Namespace) -> int:
    result = create_plugin_scaffold(
        PluginScaffoldOptions(
            name=args.name,
            target=Path(args.target),
            mode=args.mode,
            author=args.author,
            description=args.description,
            overwrite=args.force,
        )
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    print(f"Created EasyCord plugin {result.manifest.name} at {result.target}")
    print(f"  mode: {result.mode}")
    print(f"  entry point: {result.manifest.class_target}")
    for path in result.written:
        try:
            shown = path.relative_to(result.target)
        except ValueError:
            shown = path
        print(f"  {shown}")
    return 0


def cmd_plugin_check(args: argparse.Namespace) -> int:
    report = check_plugin_project(args.path)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("EasyCord plugin check")
        for check in report.checks:
            state = "ok" if check.ok else check.severity
            print(f"{state}: {check.code} - {check.message}")
        print("All checks passed." if report.ok else f"{report.failed} check(s) failed.")
    return 0 if report.ok else 1


def cmd_plugin_discover(args: argparse.Namespace) -> int:
    plugins = discover_plugins()
    if args.json:
        print(json.dumps(plugins, indent=2))
    else:
        print("EasyCord plugin entry points")
        if not plugins:
            print("  none found")
        for item in plugins:
            dist = f" ({item['distribution']})" if item.get("distribution") else ""
            print(f"  {item['name']}: {item['value']}{dist}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="easycord", description="EasyCord")
    subcommands = parser.add_subparsers(dest="command", required=True)

    new = subcommands.add_parser("new", help="Create a starter EasyCord bot project")
    new.add_argument("name", nargs="?")
    new.add_argument(
        "--template",
        choices=_PROJECT_TEMPLATES,
        default="plugin",
        help="Project template to generate (default: plugin)",
    )
    new.add_argument(
        "--list-templates",
        action="store_true",
        help="Show available project templates and exit",
    )
    new.set_defaults(func=cmd_new)

    inspect = subcommands.add_parser("inspect", help="Show a bot's registered interactions")
    inspect.add_argument("target", help="Bot object as module:object, for example bot:bot")
    inspect.add_argument("--json", action="store_true", help="Print raw JSON")
    inspect.set_defaults(func=cmd_inspect)

    sync_plan = subcommands.add_parser("sync-plan", help="Preview command sync changes")
    sync_plan.add_argument("target", help="Bot object as module:object, for example bot:bot")
    sync_plan.add_argument("--remote", action="append", default=[], help="Remote command name to compare")
    sync_plan.add_argument("--json", action="store_true", help="Print raw JSON")
    sync_plan.set_defaults(func=cmd_sync_plan)

    doctor = subcommands.add_parser("doctor", help="Check local EasyCord development setup")
    doctor.add_argument("target", nargs="?", help="Optional bot object as module:object")
    doctor.add_argument("--json", action="store_true", help="Print raw JSON")
    doctor.add_argument(
        "--fix-configs",
        action="store_true",
        help="Heal schema drift in guild config files (requires a bot target)",
    )
    doctor.set_defaults(func=cmd_doctor)

    audit_tools = subcommands.add_parser(
        "audit-tools",
        help="Audit registered AI tools without contacting Discord",
    )
    audit_tools.add_argument("target", help="Bot object as module:object, for example bot:bot")
    audit_tools.add_argument("--json", action="store_true", help="Print raw JSON")
    audit_tools.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with status 1 when audit warnings are present",
    )
    audit_tools.set_defaults(func=cmd_audit_tools)

    template = subcommands.add_parser("test-template", help="Generate a starter plugin test")
    template.add_argument("plugin_name")
    template.add_argument("-o", "--output", help="Write the template to a file")
    template.set_defaults(func=cmd_test_template)

    plugin = subcommands.add_parser("plugin", help="Create and inspect EasyCord plugins")
    plugin_commands = plugin.add_subparsers(dest="plugin_command", required=True)

    plugin_create = plugin_commands.add_parser("create", help="Create a plugin scaffold")
    plugin_create.add_argument("name")
    plugin_create.add_argument(
        "--mode",
        choices=("in-project", "package"),
        default="in-project",
        help="Scaffold mode (default: in-project)",
    )
    plugin_create.add_argument(
        "--target",
        default=".",
        help="Directory to write into (default: current directory)",
    )
    plugin_create.add_argument("--author", default="Unknown")
    plugin_create.add_argument("--description")
    plugin_create.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scaffold files",
    )
    plugin_create.add_argument("--json", action="store_true", help="Print raw JSON")
    plugin_create.set_defaults(func=cmd_plugin_create)

    plugin_check = plugin_commands.add_parser("check", help="Validate a plugin project")
    plugin_check.add_argument("path")
    plugin_check.add_argument("--json", action="store_true", help="Print raw JSON")
    plugin_check.set_defaults(func=cmd_plugin_check)

    plugin_discover = plugin_commands.add_parser(
        "discover",
        help="List installed easycord.plugins entry points",
    )
    plugin_discover.add_argument("--json", action="store_true", help="Print raw JSON")
    plugin_discover.set_defaults(func=cmd_plugin_discover)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
