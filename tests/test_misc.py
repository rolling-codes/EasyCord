"""Tests for builders, conversation_memory extras, registry, shared plugin helpers."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import discord
import pytest

from easycord.builders.embed import EmbedBuilder
from easycord.builders.button import ButtonRowBuilder
from easycord.builders.modal import ModalBuilder
from easycord.builders.select import SelectMenuBuilder
from easycord.conversation_memory import Conversation, ConversationMemory, ConversationTurn
from easycord.registry import InteractionRegistry
from easycord.plugins._shared import (
    format_template,
    read_json_file,
    require_guild,
    write_json_file,
)


# ---------------------------------------------------------------------------
# EmbedBuilder
# ---------------------------------------------------------------------------

class TestEmbedBuilder:
    def test_build_minimal(self) -> None:
        embed = EmbedBuilder().title("Hi").build()
        assert embed.title == "Hi"

    def test_build_no_title_raises(self) -> None:
        with pytest.raises(ValueError):
            EmbedBuilder().build()

    def test_description(self) -> None:
        embed = EmbedBuilder().title("T").description("D").build()
        assert embed.description == "D"

    def test_field(self) -> None:
        embed = EmbedBuilder().title("T").field("Name", "Val").build()
        assert embed.fields[0].name == "Name"
        assert embed.fields[0].value == "Val"

    def test_footer(self) -> None:
        embed = EmbedBuilder().title("T").footer("foot").build()
        assert embed.footer.text == "foot"

    def test_color(self) -> None:
        embed = EmbedBuilder().title("T").color(discord.Color.red()).build()
        assert embed.color == discord.Color.red()

    def test_multiple_fields(self) -> None:
        embed = (
            EmbedBuilder()
            .title("T")
            .field("A", "1")
            .field("B", "2")
            .build()
        )
        assert len(embed.fields) == 2


# ---------------------------------------------------------------------------
# ButtonRowBuilder
# ---------------------------------------------------------------------------

class TestButtonRowBuilder:
    def test_build_empty(self) -> None:
        view = ButtonRowBuilder().build()
        assert isinstance(view, discord.ui.View)

    def test_build_with_button(self) -> None:
        view = ButtonRowBuilder().button("Click", custom_id="btn").build()
        assert len(view.children) == 1

    def test_button_styles(self) -> None:
        view = (
            ButtonRowBuilder()
            .button("A", custom_id="a", style="success")
            .button("B", custom_id="b", style="danger")
            .build()
        )
        assert len(view.children) == 2

    def test_link_button(self) -> None:
        view = ButtonRowBuilder().button("Link", style="link", url="https://example.com").build()
        assert len(view.children) == 1

    def test_unknown_style_defaults_to_primary(self) -> None:
        view = ButtonRowBuilder().button("X", custom_id="x", style="nonexistent").build()
        assert view.children[0].style == discord.ButtonStyle.primary


# ---------------------------------------------------------------------------
# ModalBuilder
# ---------------------------------------------------------------------------

class TestModalBuilder:
    @pytest.mark.asyncio
    async def test_send_no_title_raises(self) -> None:
        from easycord.builders.modal import ModalBuilder
        from unittest.mock import AsyncMock
        ctx = MagicMock()
        ctx.ask_form = AsyncMock(return_value={})
        with pytest.raises(ValueError):
            await ModalBuilder().send(ctx)

    @pytest.mark.asyncio
    async def test_send_calls_ask_form(self) -> None:
        from easycord.builders.modal import ModalBuilder
        from unittest.mock import AsyncMock
        ctx = MagicMock()
        ctx.ask_form = AsyncMock(return_value={"reason": "test"})
        result = await (
            ModalBuilder()
            .title("Feedback")
            .field("reason", "Why?", placeholder="Tell us...")
            .field("detail", "Details", required=False)
            .send(ctx)
        )
        ctx.ask_form.assert_called_once()
        assert result == {"reason": "test"}


# ---------------------------------------------------------------------------
# SelectMenuBuilder
# ---------------------------------------------------------------------------

class TestSelectMenuBuilder:
    def test_build_returns_view(self) -> None:
        from easycord.builders.select import SelectMenuBuilder
        view = SelectMenuBuilder().option("A", "a").build(custom_id="sel")
        assert isinstance(view, discord.ui.View)

    def test_options_added(self) -> None:
        from easycord.builders.select import SelectMenuBuilder
        view = (
            SelectMenuBuilder()
            .option("Option A", "a")
            .option("Option B", "b")
            .build(custom_id="sel")
        )
        assert len(view.children) == 1
        select = view.children[0]
        assert len(select.options) == 2

    def test_placeholder(self) -> None:
        from easycord.builders.select import SelectMenuBuilder
        view = (
            SelectMenuBuilder()
            .placeholder("Pick one")
            .option("A", "a")
            .build(custom_id="sel")
        )
        assert view.children[0].placeholder == "Pick one"

    def test_no_options_raises(self) -> None:
        from easycord.builders.select import SelectMenuBuilder
        with pytest.raises(ValueError):
            SelectMenuBuilder().build(custom_id="sel")


# ---------------------------------------------------------------------------
# Conversation + ConversationMemory extras
# ---------------------------------------------------------------------------

class TestConversation:
    def test_add_turn_and_to_messages(self) -> None:
        conv = Conversation(user_id=1, guild_id=10)
        conv.add_turn("user", "hello")
        conv.add_turn("assistant", "hi")
        msgs = conv.to_messages()
        assert msgs == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

    def test_max_turns_eviction(self) -> None:
        conv = Conversation(user_id=1, guild_id=10, max_turns=2)
        conv.add_turn("user", "a")
        conv.add_turn("user", "b")
        conv.add_turn("user", "c")
        msgs = conv.to_messages()
        assert len(msgs) == 2
        assert msgs[0]["content"] == "b"

    def test_estimate_tokens(self) -> None:
        conv = Conversation(user_id=1, guild_id=10)
        conv.add_turn("user", "abcd")  # 4 chars → 1 token
        assert conv.estimate_tokens() >= 1

    def test_is_expired_false_for_new(self) -> None:
        conv = Conversation(user_id=1, guild_id=10)
        assert conv.is_expired() is False


class TestConversationMemoryExtra:
    def test_add_assistant_message(self) -> None:
        m = ConversationMemory()
        m.add_assistant_message(1, "reply", guild_id=10)
        msgs = m.get_messages(1, guild_id=10)
        assert msgs[-1] == {"role": "assistant", "content": "reply"}

    def test_clear(self) -> None:
        m = ConversationMemory()
        m.add_user_message(1, "hi", guild_id=10)
        m.clear(1, guild_id=10)
        assert m.get_messages(1, guild_id=10) == []

    def test_stats(self) -> None:
        m = ConversationMemory()
        m.add_user_message(1, "a", guild_id=10)
        m.add_user_message(2, "b", guild_id=10)
        stats = m.get_stats()
        assert stats["total_conversations"] == 2
        assert stats["total_turns"] == 2

    def test_invalid_max_conversations_raises(self) -> None:
        with pytest.raises(ValueError):
            ConversationMemory(max_conversations=0)

    def test_get_or_create_reuses_active(self) -> None:
        m = ConversationMemory()
        c1 = m.get_or_create(1, 10)
        c2 = m.get_or_create(1, 10)
        assert c1 is c2


# ---------------------------------------------------------------------------
# InteractionRegistry
# ---------------------------------------------------------------------------

class TestInteractionRegistry:
    def test_register_component(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("btn1", lambda: None)
        assert "btn1" in reg.components

    def test_register_duplicate_component_raises(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("btn1", lambda: None)
        with pytest.raises(ValueError):
            reg.register_component("btn1", lambda: None)

    def test_register_modal(self) -> None:
        reg = InteractionRegistry()
        reg.register_modal("modal1", lambda: None)
        assert "modal1" in reg.modals

    def test_register_duplicate_modal_raises(self) -> None:
        reg = InteractionRegistry()
        reg.register_modal("m1", lambda: None)
        with pytest.raises(ValueError):
            reg.register_modal("m1", lambda: None)

    def test_register_component_with_plugin(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("c1", lambda: None, source_plugin="MyPlugin")
        assert reg.components["c1"]["plugin"] == "MyPlugin"


# ---------------------------------------------------------------------------
# Plugin shared helpers
# ---------------------------------------------------------------------------

class TestSharedHelpers:
    def test_require_guild_present(self) -> None:
        ctx = MagicMock()
        guild = MagicMock()
        ctx.guild = guild
        assert require_guild(ctx) is guild

    def test_require_guild_absent(self) -> None:
        ctx = MagicMock()
        ctx.guild = None
        assert require_guild(ctx) is None

    def test_format_template(self) -> None:
        assert format_template("Hello {name}!", name="World") == "Hello World!"

    def test_read_json_file_missing_returns_empty(self, tmp_path) -> None:
        result = read_json_file(tmp_path / "nonexistent.json")
        assert result == {}

    def test_read_json_file_valid(self, tmp_path) -> None:
        path = tmp_path / "data.json"
        path.write_text('{"key": "val"}', encoding="utf-8")
        assert read_json_file(path) == {"key": "val"}

    def test_read_json_file_invalid_json_returns_empty(self, tmp_path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        assert read_json_file(path) == {}

    def test_read_json_file_non_dict_returns_empty(self, tmp_path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert read_json_file(path) == {}

    def test_write_json_file_roundtrip(self, tmp_path) -> None:
        path = tmp_path / "out.json"
        write_json_file(path, {"a": 1})
        result = read_json_file(path)
        assert result == {"a": 1}
