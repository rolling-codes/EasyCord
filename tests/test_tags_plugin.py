"""Tests for easycord.plugins.tags — TagsStore and TagsPlugin."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import discord

from easycord.plugins.tags import TagsStore, TagsPlugin


# ── TagsStore ─────────────────────────────────────────────────────────────────

def test_store_get_missing_returns_none(tmp_path):
    store = TagsStore(str(tmp_path))
    assert store.get(1, "missing") is None


def test_store_set_and_get(tmp_path):
    store = TagsStore(str(tmp_path))
    store.set(1, "hello", "Hello, world!", author_id=42)
    entry = store.get(1, "hello")
    assert entry["text"] == "Hello, world!"
    assert entry["author_id"] == 42


def test_store_set_overwrites(tmp_path):
    store = TagsStore(str(tmp_path))
    store.set(1, "greet", "Hi", author_id=1)
    store.set(1, "greet", "Hello", author_id=2)
    assert store.get(1, "greet")["text"] == "Hello"


def test_store_delete_existing(tmp_path):
    store = TagsStore(str(tmp_path))
    store.set(1, "bye", "Goodbye", author_id=99)
    store.delete(1, "bye")
    assert store.get(1, "bye") is None


def test_store_delete_missing_is_noop(tmp_path):
    store = TagsStore(str(tmp_path))
    store.delete(1, "nonexistent")  # should not raise


def test_store_list_names_empty(tmp_path):
    store = TagsStore(str(tmp_path))
    assert store.list_names(1) == []


def test_store_list_names_sorted(tmp_path):
    store = TagsStore(str(tmp_path))
    store.set(1, "zebra", "z", author_id=1)
    store.set(1, "apple", "a", author_id=1)
    assert store.list_names(1) == ["apple", "zebra"]


def test_store_persists_across_instances(tmp_path):
    TagsStore(str(tmp_path)).set(1, "persistent", "yes", author_id=5)
    assert TagsStore(str(tmp_path)).get(1, "persistent")["text"] == "yes"


def test_store_guild_isolation(tmp_path):
    store = TagsStore(str(tmp_path))
    store.set(1, "shared", "guild1", author_id=1)
    assert store.get(2, "shared") is None


# ── TagsPlugin ────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return TagsStore(str(tmp_path))


@pytest.fixture
def plugin(tmp_path):
    return TagsPlugin(data_dir=str(tmp_path))


def _make_ctx(guild_id=1, user_id=10, is_admin=False):
    ctx = MagicMock()
    ctx.guild_id = guild_id
    ctx.respond = AsyncMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    member = MagicMock(spec=discord.Member)
    member.guild_permissions = MagicMock()
    member.guild_permissions.administrator = is_admin
    ctx.guild.get_member = MagicMock(return_value=member)
    ctx.user = MagicMock()
    ctx.user.id = user_id
    return ctx


async def test_tag_get_missing(plugin):
    ctx = _make_ctx()
    await plugin.get(ctx, name="nope")
    ctx.respond.assert_called_once_with("Tag `nope` not found.", ephemeral=True)


async def test_tag_get_found(plugin):
    plugin._store.set(1, "hello", "Hello, world!", author_id=10)
    ctx = _make_ctx()
    await plugin.get(ctx, name="hello")
    ctx.respond.assert_called_once_with("Hello, world!")


async def test_tag_set_creates(plugin):
    ctx = _make_ctx()
    await plugin.set(ctx, name="greet", text="Hi there")
    ctx.respond.assert_called_once_with("Tag `greet` saved.", ephemeral=True)
    assert plugin._store.get(1, "greet")["text"] == "Hi there"


async def test_tag_set_overwrites(plugin):
    plugin._store.set(1, "greet", "Old", author_id=10)
    ctx = _make_ctx()
    await plugin.set(ctx, name="greet", text="New")
    assert plugin._store.get(1, "greet")["text"] == "New"


async def test_tag_delete_by_creator(plugin):
    plugin._store.set(1, "bye", "Goodbye", author_id=10)
    ctx = _make_ctx(user_id=10)
    await plugin.delete(ctx, name="bye")
    ctx.respond.assert_called_once_with("Tag `bye` deleted.", ephemeral=True)
    assert plugin._store.get(1, "bye") is None


async def test_tag_delete_by_admin(plugin):
    plugin._store.set(1, "bye", "Goodbye", author_id=99)
    ctx = _make_ctx(user_id=1, is_admin=True)
    await plugin.delete(ctx, name="bye")
    assert plugin._store.get(1, "bye") is None


async def test_tag_delete_denied(plugin):
    plugin._store.set(1, "bye", "Goodbye", author_id=99)
    ctx = _make_ctx(user_id=10, is_admin=False)
    await plugin.delete(ctx, name="bye")
    ctx.respond.assert_called_once_with(
        "You can only delete your own tags (or be an admin).", ephemeral=True
    )
    assert plugin._store.get(1, "bye") is not None


async def test_tag_delete_missing(plugin):
    ctx = _make_ctx()
    await plugin.delete(ctx, name="ghost")
    ctx.respond.assert_called_once_with("Tag `ghost` not found.", ephemeral=True)


async def test_tag_list_empty(plugin):
    ctx = _make_ctx()
    await plugin.list(ctx)
    ctx.respond.assert_called_once_with("No tags yet.", ephemeral=True)


async def test_tag_list_shows_names(plugin):
    plugin._store.set(1, "b", "B", author_id=1)
    plugin._store.set(1, "a", "A", author_id=1)
    ctx = _make_ctx()
    await plugin.list(ctx)
    ctx.respond.assert_called_once_with("**Tags:**\na\nb", ephemeral=True)
