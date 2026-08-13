"""Tests for TagsPlugin: store CRUD, per-guild isolation, and command/admin gating."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.plugins.tags import TagsPlugin, TagsStore


def _make_plugin(tmp_path) -> TagsPlugin:
    return TagsPlugin(data_dir=str(tmp_path / "tags"))


def _make_context(
    *, guild_id: int = 1, user_id: int = 2, is_admin: bool = False
) -> MagicMock:
    ctx = MagicMock()
    ctx.guild_id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.is_admin = is_admin  # property on the real Context; a bool here is fine
    ctx.respond = AsyncMock()
    ctx.paginate = AsyncMock()
    # ctx.t(key, default=..., **fmt) -> formatted default string
    ctx.t = MagicMock(side_effect=lambda key, default="", **fmt: default.format(**fmt) if fmt else default)
    return ctx


# ── TagsStore unit tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_store_set_then_get_returns_entry(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "hello", "world", author_id=7)
    assert store.get(1, "hello") == {"text": "world", "author_id": 7}


def test_store_get_missing_returns_none(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    assert store.get(1, "nope") is None


@pytest.mark.asyncio
async def test_store_delete_removes_entry(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "x", "v", author_id=7)
    await store.delete(1, "x")
    assert store.get(1, "x") is None


@pytest.mark.asyncio
async def test_store_delete_missing_is_noop(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    # Must not raise when the key is absent.
    await store.delete(1, "ghost")
    assert store.list_names(1) == []


@pytest.mark.asyncio
async def test_store_list_names_sorted(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "banana", "b", author_id=7)
    await store.set(1, "apple", "a", author_id=7)
    assert store.list_names(1) == ["apple", "banana"]


@pytest.mark.asyncio
async def test_store_is_isolated_per_guild(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "shared", "guild-one", author_id=7)
    assert store.get(2, "shared") is None
    await store.set(2, "shared", "guild-two", author_id=9)
    one = store.get(1, "shared")
    two = store.get(2, "shared")
    assert one is not None and one["text"] == "guild-one"
    assert two is not None and two["text"] == "guild-two"


# ── Command flow tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_missing_tag_responds_not_found(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context()
    await plugin.get(ctx, "missing")
    assert "not found" in ctx.respond.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_get_existing_tag_responds_text(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._store.set(1, "greet", "hi there", author_id=2)
    ctx = _make_context()
    await plugin.get(ctx, "greet")
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    assert args == ("hi there",)
    assert kwargs["allowed_mentions"].everyone is False
    assert kwargs["allowed_mentions"].users is False
    assert kwargs["allowed_mentions"].roles is False


@pytest.mark.asyncio
async def test_set_saves_tag(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context(user_id=42)
    await plugin.set(ctx, "note", "remember me")
    assert plugin._store.get(1, "note") == {"text": "remember me", "author_id": 42}


@pytest.mark.asyncio
async def test_delete_denied_for_non_author_non_admin(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._store.set(1, "owned", "v", author_id=99)
    ctx = _make_context(user_id=2, is_admin=False)
    await plugin.delete(ctx, "owned")
    assert "only delete your own" in ctx.respond.call_args.args[0].lower()
    # Tag must survive a denied delete.
    assert plugin._store.get(1, "owned") is not None


@pytest.mark.asyncio
async def test_delete_allowed_for_author(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._store.set(1, "mine", "v", author_id=2)
    ctx = _make_context(user_id=2, is_admin=False)
    await plugin.delete(ctx, "mine")
    assert plugin._store.get(1, "mine") is None


@pytest.mark.asyncio
async def test_delete_allowed_for_admin_on_others_tag(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._store.set(1, "theirs", "v", author_id=99)
    ctx = _make_context(user_id=2, is_admin=True)
    await plugin.delete(ctx, "theirs")
    assert plugin._store.get(1, "theirs") is None


@pytest.mark.asyncio
async def test_delete_missing_tag_responds_not_found(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context()
    await plugin.delete(ctx, "ghost")
    assert "not found" in ctx.respond.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_list_empty_responds(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context()
    await plugin.list(ctx)
    ctx.respond.assert_called_once()
    ctx.paginate.assert_not_called()


@pytest.mark.asyncio
async def test_list_populated_paginates(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._store.set(1, "a", "1", author_id=2)
    await plugin._store.set(1, "b", "2", author_id=2)
    ctx = _make_context()
    await plugin.list(ctx)
    ctx.paginate.assert_called_once()


@pytest.mark.asyncio
async def test_store_set_overwrites_existing_entry(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "note", "first", author_id=7)
    await store.set(1, "note", "second", author_id=9)
    assert store.get(1, "note") == {"text": "second", "author_id": 9}
    # Overwriting must not duplicate the name.
    assert store.list_names(1) == ["note"]


@pytest.mark.asyncio
async def test_store_persists_across_reopen(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    await store.set(1, "keep", "me", author_id=7)
    reopened = TagsStore(str(tmp_path / "tags"))
    assert reopened.get(1, "keep") == {"text": "me", "author_id": 7}


@pytest.mark.asyncio
async def test_store_concurrent_sets_all_persist(tmp_path) -> None:
    import asyncio

    store = TagsStore(str(tmp_path / "tags"))
    await asyncio.gather(*[store.set(1, f"tag{i}", f"v{i}", author_id=i) for i in range(10)])
    # Every concurrent writer's entry survived the read-modify-write under the lock.
    assert store.list_names(1) == sorted(f"tag{i}" for i in range(10))


@pytest.mark.asyncio
async def test_store_delete_if_authorized_reason_codes(tmp_path) -> None:
    store = TagsStore(str(tmp_path / "tags"))
    assert await store.delete_if_authorized(1, "ghost", user_id=2, is_admin=False) == (False, "not_found")

    await store.set(1, "owned", "v", author_id=99)
    assert await store.delete_if_authorized(1, "owned", user_id=2, is_admin=False) == (False, "unauthorized")
    assert await store.delete_if_authorized(1, "owned", user_id=99, is_admin=False) == (True, "deleted")


@pytest.mark.asyncio
async def test_set_overwrite_transfers_authorship(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    first_ctx = _make_context(user_id=2)
    await plugin.set(first_ctx, "note", "original")
    second_ctx = _make_context(user_id=3)
    await plugin.set(second_ctx, "note", "updated")
    # New author owns the tag now — original author can no longer delete it.
    entry = plugin._store.get(1, "note")
    assert entry == {"text": "updated", "author_id": 3}


@pytest.mark.asyncio
async def test_list_chunks_names_into_pages_of_twenty(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    for i in range(25):
        await plugin._store.set(1, f"tag{i:02d}", "v", author_id=2)
    ctx = _make_context()
    await plugin.list(ctx)
    pages = ctx.paginate.call_args.args[0]
    assert len(pages) == 2
    # 20 names on the first page, 5 on the second (plus the header line each).
    assert len(pages[0].split("\n")) == 21
    assert len(pages[1].split("\n")) == 6
