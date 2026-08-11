"""Tests for ``easycord try`` — the offline slash-command runner (cli.cmd_try)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from easycord.cli import _coerce_arg, _parse_set_args, main


_SAMPLE_BOT = '''\
from easycord import Bot
import discord

bot = Bot(auto_sync=False, db_backend="memory")


@bot.slash(description="Ping")
async def ping(ctx):
    await ctx.respond("Pong!")


@bot.slash(description="Echo with a count")
async def echo(ctx, name: str, times: int):
    # `times + 1` raises TypeError unless `times` was coerced from str to int,
    # so a passing assertion on the output proves --set coercion happened.
    await ctx.respond(f"{name}:{times + 1}", ephemeral=True)


@bot.slash(description="Report the invocation context")
async def whereami(ctx):
    await ctx.respond(f"guild={ctx.guild_id} admin={ctx.is_admin}")


@bot.slash(description="Respond with an embed")
async def card(ctx):
    await ctx.respond(embed=discord.Embed(title="Title", description="Desc"))


@bot.slash(description="Always fails")
async def boom(ctx):
    raise ValueError("kaboom")
'''


@pytest.fixture
def sample_bot(tmp_path: Path, monkeypatch):
    """Write an importable bot module under a unique name and clean it up.

    A unique module name per test avoids ``sys.modules`` caching leaking one
    test's ``bot`` object into another (``_load_bot`` imports by name).
    """
    name = f"trybot_{uuid4().hex}"
    (tmp_path / f"{name}.py").write_text(_SAMPLE_BOT, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield f"{name}:bot"
    sys.modules.pop(name, None)


def test_try_runs_command_and_prints_response(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "ping"]) == 0
    out = capsys.readouterr().out
    assert "EasyCord try: ping" in out
    assert "Pong!" in out


def test_try_coerces_set_args(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "echo", "--set", "name=World", "--set", "times=3"]) == 0
    out = capsys.readouterr().out
    assert "World:4" in out  # times coerced to int(3); 3 + 1 == 4
    assert "(ephemeral)" in out


def test_try_defaults_to_guild_and_admin(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "whereami"]) == 0
    out = capsys.readouterr().out
    assert "guild=100 admin=True" in out


def test_try_dm_and_no_admin_reach_invoke(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "whereami", "--dm", "--no-admin"]) == 0
    out = capsys.readouterr().out
    assert "guild=None admin=False" in out


def test_try_renders_embed(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "card"]) == 0
    out = capsys.readouterr().out
    assert "embed.title: Title" in out
    assert "embed.description: Desc" in out


def test_try_unknown_command_returns_1_and_lists_available(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "nope"]) == 1
    err = capsys.readouterr().err
    assert "not registered" in err.lower()
    assert "ping" in err  # invoke() lists available commands


def test_try_surfaces_command_error(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "boom"]) == 1
    err = capsys.readouterr().err
    assert "ValueError" in err
    assert "kaboom" in err


def test_try_json_output(sample_bot, capsys) -> None:
    assert main(["try", sample_bot, "ping", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "ping"
    assert payload["response_count"] == 1
    assert payload["responses"][0]["content"] == "Pong!"
    assert payload["responses"][0]["embed"] is None


def test_coerce_arg_infers_types() -> None:
    assert _coerce_arg("42") == 42 and isinstance(_coerce_arg("42"), int)
    assert _coerce_arg("3.14") == pytest.approx(3.14)
    assert _coerce_arg("true") is True
    assert _coerce_arg("False") is False
    assert _coerce_arg("hello") == "hello"


def test_parse_set_args_rejects_missing_equals() -> None:
    with pytest.raises(SystemExit):
        _parse_set_args(["novalue"])
