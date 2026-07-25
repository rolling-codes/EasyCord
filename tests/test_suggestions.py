"""Tests for SuggestionsPlugin ID allocation and command flows under concurrency."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.suggestions import SuggestionsPlugin


def _make_plugin(tmp_path) -> SuggestionsPlugin:
    plugin = SuggestionsPlugin()
    plugin.config = PluginConfigManager(str(tmp_path / "suggestions"))
    return plugin


def _make_context(guild_id: int = 1, user_id: int = 2, manage_guild: bool = False) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock(spec=discord.Member)
    ctx.user.id = user_id
    ctx.user.name = "TestUser"
    ctx.user.avatar = None
    ctx.user.guild_permissions.manage_guild = manage_guild
    ctx.respond = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_get_next_id_is_monotonic(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    first = await plugin._get_next_id(1)
    second = await plugin._get_next_id(1)
    third = await plugin._get_next_id(1)
    assert [first, second, third] == [1, 2, 3]


@pytest.mark.asyncio
async def test_concurrent_get_next_id_yields_distinct_ids(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ids = await asyncio.gather(*[plugin._get_next_id(1) for _ in range(25)])
    # No duplicates, and the counter advanced exactly once per call.
    assert sorted(ids) == list(range(1, 26))


@pytest.mark.asyncio
async def test_counter_is_isolated_per_guild(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    assert await plugin._get_next_id(1) == 1
    assert await plugin._get_next_id(2) == 1
    assert await plugin._get_next_id(1) == 2


@pytest.mark.asyncio
async def test_counter_persists_across_reload(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._get_next_id(1)
    await plugin._get_next_id(1)
    # Fresh plugin pointed at the same store keeps counting where it left off.
    reopened = SuggestionsPlugin()
    reopened.config = PluginConfigManager(str(tmp_path / "suggestions"))
    assert await reopened._get_next_id(1) == 3


@pytest.mark.asyncio
async def test_plugin_on_load(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.on_load()  # covers log output/initialization


@pytest.mark.asyncio
async def test_suggest_channel_not_configured(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context()
    await plugin.suggest(ctx, "idea")
    ctx.respond.assert_called_once_with("❌ Suggestions channel not configured", ephemeral=True)


@pytest.mark.asyncio
async def test_suggest_channel_not_found(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    # Configure the channel in config but mock guild to return None
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()
    ctx.guild.get_channel.return_value = None
    await plugin.suggest(ctx, "idea")
    ctx.respond.assert_called_once_with("❌ Suggestions channel not found", ephemeral=True)


@pytest.mark.asyncio
async def test_suggest_posted_successfully(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()
    
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 999
    mock_channel.send = AsyncMock(return_value=mock_msg)
    ctx.guild.get_channel.return_value = mock_channel

    await plugin.suggest(ctx, "idea")

    # Assert reactions added and respond called
    mock_msg.add_reaction.assert_any_call("👍")
    mock_msg.add_reaction.assert_any_call("👎")
    ctx.respond.assert_called_once_with("✅ Suggestion #1 posted!", ephemeral=True)

    # Verify suggestion stored in config
    cfg = await plugin.config.get(1, "suggestions")
    assert cfg.get("1") is not None
    assert cfg["1"]["idea"] == "idea"
    assert cfg["1"]["message_id"] == 999


@pytest.mark.asyncio
async def test_suggest_forbidden_post(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.send.side_effect = discord.Forbidden(MagicMock(), "cannot post")
    ctx.guild.get_channel.return_value = mock_channel

    await plugin.suggest(ctx, "idea")
    ctx.respond.assert_called_once_with("❌ Cannot post to suggestions channel", ephemeral=True)


@pytest.mark.asyncio
async def test_suggestions_command(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context()

    # View when no suggestions exist
    await plugin.suggestions(ctx)
    ctx.respond.assert_called_once_with("No pending suggestions")

    # Populate a pending suggestion
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 999
    mock_channel.send = AsyncMock(return_value=mock_msg)
    ctx.guild.get_channel.return_value = mock_channel
    await plugin.suggest(ctx, "my cool idea")

    ctx2 = _make_context()
    await plugin.suggestions(ctx2)
    ctx2.respond.assert_called_once()
    embed = ctx2.respond.call_args.kwargs.get("embed")
    assert embed is not None
    assert embed.title == "Pending Suggestions (1)"


@pytest.mark.asyncio
async def test_suggestion_approve_reject_no_permission(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context(manage_guild=False)

    await plugin.suggestion_approve(ctx, 1)
    ctx.respond.assert_called_once_with("❌ You lack `manage_guild` permission", ephemeral=True)

    ctx2 = _make_context(manage_guild=False)
    await plugin.suggestion_reject(ctx2, 1)
    ctx2.respond.assert_called_once_with("❌ You lack `manage_guild` permission", ephemeral=True)


@pytest.mark.asyncio
async def test_suggestion_approve_reject_not_found(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = _make_context(manage_guild=True)

    await plugin.suggestion_approve(ctx, 1)
    ctx.respond.assert_called_once_with("❌ Suggestion not found", ephemeral=True)

    ctx2 = _make_context(manage_guild=True)
    await plugin.suggestion_reject(ctx2, 1)
    ctx2.respond.assert_called_once_with("❌ Suggestion not found", ephemeral=True)


@pytest.mark.asyncio
async def test_suggestion_approve_reject_success(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 999
    mock_channel.send = AsyncMock(return_value=mock_msg)
    ctx.guild.get_channel.return_value = mock_channel
    await plugin.suggest(ctx, "idea")

    # Approve it
    approve_ctx = _make_context(manage_guild=True)
    await plugin.suggestion_approve(approve_ctx, 1)
    approve_ctx.respond.assert_called_once_with("✅ Suggestion #1 approved")

    cfg_obj = await plugin.config.store.load(1)
    suggestions = cfg_obj.get_other("suggestions", {})
    assert suggestions["1"]["status"] == "approved"

    # Submit second suggestion and reject it — ctx2 also needs the channel mock
    suggest_ctx2 = _make_context()
    mock_msg2 = AsyncMock(spec=discord.Message)
    mock_msg2.id = 1000
    mock_channel.send = AsyncMock(return_value=mock_msg2)
    suggest_ctx2.guild.get_channel.return_value = mock_channel
    await plugin.suggest(suggest_ctx2, "idea 2")

    reject_ctx = _make_context(manage_guild=True)
    await plugin.suggestion_reject(reject_ctx, 2)
    reject_ctx.respond.assert_called_once_with("✅ Suggestion #2 rejected")

    cfg_obj2 = await plugin.config.store.load(1)
    suggestions2 = cfg_obj2.get_other("suggestions", {})
    assert suggestions2["2"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_suggest_accepts_thread_channel(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()

    mock_thread = MagicMock(spec=discord.Thread)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 555
    mock_thread.send = AsyncMock(return_value=mock_msg)
    ctx.guild.get_channel.return_value = mock_thread

    await plugin.suggest(ctx, "thread idea")
    ctx.respond.assert_called_once_with("✅ Suggestion #1 posted!", ephemeral=True)


@pytest.mark.asyncio
async def test_suggest_uses_custom_vote_emojis(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(
        1, "suggestions", suggestions_channel=123, upvote_emoji="⬆️", downvote_emoji="⬇️"
    )
    ctx = _make_context()

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 999
    mock_channel.send = AsyncMock(return_value=mock_msg)
    ctx.guild.get_channel.return_value = mock_channel

    await plugin.suggest(ctx, "idea")
    mock_msg.add_reaction.assert_any_call("⬆️")
    mock_msg.add_reaction.assert_any_call("⬇️")


@pytest.mark.asyncio
async def test_suggestions_listing_caps_at_ten_newest_first(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)

    def _seed(cfg) -> None:
        cfg.set_other(
            "suggestions",
            {str(i): {"user_id": 2, "idea": f"idea {i}", "message_id": i, "status": "pending"} for i in range(1, 13)},
        )

    await plugin.config.store.mutate(1, _seed)

    ctx = _make_context()
    await plugin.suggestions(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed")
    assert embed is not None
    assert embed.title == "Pending Suggestions (12)"
    lines = embed.description.split("\n")
    assert len(lines) == 10
    # Highest IDs come first
    assert lines[0].startswith("**#12**")
    assert lines[-1].startswith("**#3**")


@pytest.mark.asyncio
async def test_suggestions_listing_excludes_resolved(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)

    def _seed(cfg) -> None:
        cfg.set_other(
            "suggestions",
            {
                "1": {"user_id": 2, "idea": "approved one", "message_id": 1, "status": "approved"},
                "2": {"user_id": 2, "idea": "rejected one", "message_id": 2, "status": "rejected"},
                "3": {"user_id": 2, "idea": "still open", "message_id": 3, "status": "pending"},
            },
        )

    await plugin.config.store.mutate(1, _seed)

    ctx = _make_context()
    await plugin.suggestions(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed")
    assert embed is not None
    assert embed.title == "Pending Suggestions (1)"
    assert "still open" in embed.description
    assert "approved one" not in embed.description


@pytest.mark.asyncio
async def test_suggestions_listing_truncates_long_ideas(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    long_idea = "x" * 250

    def _seed(cfg) -> None:
        cfg.set_other(
            "suggestions",
            {"1": {"user_id": 2, "idea": long_idea, "message_id": 1, "status": "pending"}},
        )

    await plugin.config.store.mutate(1, _seed)

    ctx = _make_context()
    await plugin.suggestions(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed")
    assert embed is not None
    # "**#1** — " prefix plus at most 100 chars of the idea
    assert "x" * 100 in embed.description
    assert "x" * 101 not in embed.description


@pytest.mark.asyncio
async def test_suggestions_listing_skips_malformed_entries(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)

    def _seed(cfg) -> None:
        cfg.set_other(
            "suggestions",
            {
                "1": "not a dict",
                "2": {"user_id": 2, "idea": "valid", "message_id": 2, "status": "pending"},
            },
        )

    await plugin.config.store.mutate(1, _seed)

    ctx = _make_context()
    await plugin.suggestions(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed")
    assert embed is not None
    assert embed.title == "Pending Suggestions (1)"


@pytest.mark.asyncio
async def test_concurrent_suggest_preserves_all_entries(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)

    def _make_posting_ctx() -> MagicMock:
        ctx = _make_context()
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.id = 999
        mock_channel.send = AsyncMock(return_value=mock_msg)
        ctx.guild.get_channel.return_value = mock_channel
        return ctx

    await asyncio.gather(*[plugin.suggest(_make_posting_ctx(), f"idea {i}") for i in range(8)])

    cfg_obj = await plugin.config.store.load(1)
    # Config keys (suggestions_channel, ...) share the "suggestions" section
    # with the stored entries, so filter to the dict-typed suggestion records.
    stored = cfg_obj.get_other("suggestions", {})
    entries = {k: v for k, v in stored.items() if isinstance(v, dict)}
    # Every concurrent writer's entry survived the read-modify-write
    assert len(entries) == 8
    assert sorted(int(k) for k in entries) == list(range(1, 9))


@pytest.mark.asyncio
async def test_approve_leaves_other_suggestions_pending(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)

    def _seed(cfg) -> None:
        cfg.set_other(
            "suggestions",
            {
                "1": {"user_id": 2, "idea": "first", "message_id": 1, "status": "pending"},
                "2": {"user_id": 2, "idea": "second", "message_id": 2, "status": "pending"},
            },
        )

    await plugin.config.store.mutate(1, _seed)

    ctx = _make_context(manage_guild=True)
    await plugin.suggestion_approve(ctx, 1)

    cfg_obj = await plugin.config.store.load(1)
    suggestions = cfg_obj.get_other("suggestions", {})
    assert suggestions["1"]["status"] == "approved"
    assert suggestions["2"]["status"] == "pending"


# ---------------------------------------------------------------------------
# add_reaction Forbidden — lines 111-112 of suggestions.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_add_reaction_forbidden_does_not_propagate(tmp_path) -> None:
    """When add_reaction raises Forbidden the command must still complete successfully."""
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 888
    # send() succeeds, but add_reaction() raises Forbidden
    mock_channel.send = AsyncMock(return_value=mock_msg)
    mock_msg.add_reaction = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(), "no perms")
    )
    ctx.guild.get_channel.return_value = mock_channel

    # Must not raise
    await plugin.suggest(ctx, "reaction-forbidden idea")

    # Success response still sent
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    response_text = args[0] if args else ""
    assert "posted" in response_text.lower() or kwargs.get("ephemeral") is not True

    # Suggestion still stored despite reaction failure
    cfg_obj = await plugin.config.store.load(1)
    suggestions = cfg_obj.get_other("suggestions", {})
    assert any(v.get("idea") == "reaction-forbidden idea" for v in suggestions.values() if isinstance(v, dict))


@pytest.mark.asyncio
async def test_suggest_add_reaction_http_exception_does_not_propagate(tmp_path) -> None:
    """When add_reaction raises HTTPException the command completes without error."""
    plugin = _make_plugin(tmp_path)
    await plugin.config.update(1, "suggestions", suggestions_channel=123)
    ctx = _make_context()

    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_msg = AsyncMock(spec=discord.Message)
    mock_msg.id = 777
    mock_channel.send = AsyncMock(return_value=mock_msg)
    mock_msg.add_reaction = AsyncMock(
        side_effect=discord.HTTPException(MagicMock(), "http error")
    )
    ctx.guild.get_channel.return_value = mock_channel

    await plugin.suggest(ctx, "http-exception idea")

    ctx.respond.assert_called_once()
    cfg_obj = await plugin.config.store.load(1)
    suggestions = cfg_obj.get_other("suggestions", {})
    assert any(v.get("idea") == "http-exception idea" for v in suggestions.values() if isinstance(v, dict))
