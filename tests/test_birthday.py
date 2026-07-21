"""Tests for BirthdayPlugin — pure functions, store logic, and command flow."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock


from easycord.plugins.birthday import (
    BirthdayPlugin,
    _days_until,
    _sort_upcoming,
    _validate_date,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(guild_id: int = 100, user_id: int = 1) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.id = 55
    ctx.is_admin = True
    ctx.member = MagicMock()
    ctx.member.guild_permissions = MagicMock()
    ctx.member.guild_permissions.manage_guild = True
    return ctx


def _plugin(tmp_path) -> BirthdayPlugin:
    p = BirthdayPlugin.__new__(BirthdayPlugin)
    BirthdayPlugin.__init__(p, store_path=str(tmp_path / "birthday"))
    return p


# ---------------------------------------------------------------------------
# Layer 1 — Pure function tests
# ---------------------------------------------------------------------------

class TestPureFunctions:
    # _validate_date

    def test_validate_valid_date(self) -> None:
        assert _validate_date(6, 15) is True

    def test_validate_feb_29(self) -> None:
        # Feb 29 is special-cased as valid
        assert _validate_date(2, 29) is True

    def test_validate_feb_30(self) -> None:
        assert _validate_date(2, 30) is False

    def test_validate_month_13(self) -> None:
        assert _validate_date(13, 1) is False

    def test_validate_day_zero(self) -> None:
        assert _validate_date(6, 0) is False

    def test_validate_day_31_valid_month(self) -> None:
        assert _validate_date(1, 31) is True

    def test_validate_day_31_invalid_month(self) -> None:
        # April has 30 days
        assert _validate_date(4, 31) is False

    def test_validate_month_zero(self) -> None:
        assert _validate_date(0, 15) is False

    # _days_until

    def test_days_until_today(self) -> None:
        today = datetime.date(2026, 6, 15)
        assert _days_until(6, 15, today) == 0

    def test_days_until_tomorrow(self) -> None:
        today = datetime.date(2026, 6, 15)
        assert _days_until(6, 16, today) == 1

    def test_days_until_wraps_year(self) -> None:
        today = datetime.date(2026, 1, 1)
        days = _days_until(12, 31, today)
        # Dec 31 is 364 days after Jan 1 in a non-leap year
        assert days in (364, 365)

    def test_days_until_past_date_wraps_to_next_year(self) -> None:
        today = datetime.date(2026, 6, 15)
        # Jan 1 is in the past; next occurrence is next year
        days = _days_until(1, 1, today)
        assert days > 0

    def test_days_until_same_day_next_month(self) -> None:
        today = datetime.date(2026, 6, 15)
        assert _days_until(7, 15, today) == 30

    def test_days_until_feb29_when_next_year_also_non_leap(self) -> None:
        # 2026 and 2027 are both non-leap; the next Feb 29 is in 2028.
        # Previously raised an uncaught ValueError on date(2027, 2, 29).
        today = datetime.date(2026, 6, 28)
        expected = (datetime.date(2028, 2, 29) - today).days
        assert _days_until(2, 29, today) == expected

    def test_days_until_feb29_earlier_in_a_leap_year(self) -> None:
        # In a leap year, before Feb 29 -> the upcoming Feb 29 is this year.
        today = datetime.date(2028, 1, 1)
        assert _days_until(2, 29, today) == (datetime.date(2028, 2, 29) - today).days

    def test_sort_upcoming_with_feb29_entry_does_not_crash(self) -> None:
        today = datetime.date(2026, 6, 28)
        birthdays = {
            "1": {"month": 2, "day": 29},
            "2": {"month": 7, "day": 1},
        }
        result = _sort_upcoming(birthdays, today)
        # July 1 (a few days out) sorts ahead of Feb 29 2028 (~600 days out).
        assert [t[0] for t in result] == [2, 1]

    # _sort_upcoming

    def test_sort_upcoming_orders_correctly(self) -> None:
        today = datetime.date(2026, 6, 15)
        birthdays = {
            "1": {"month": 6, "day": 20},
            "2": {"month": 6, "day": 16},
            "3": {"month": 6, "day": 18},
        }
        result = _sort_upcoming(birthdays, today)
        user_ids = [t[0] for t in result]
        assert user_ids == [2, 3, 1]

    def test_sort_upcoming_empty(self) -> None:
        today = datetime.date(2026, 6, 15)
        assert _sort_upcoming({}, today) == []

    def test_sort_upcoming_today_is_first(self) -> None:
        today = datetime.date(2026, 6, 15)
        birthdays = {
            "1": {"month": 7, "day": 1},
            "2": {"month": 6, "day": 15},
        }
        result = _sort_upcoming(birthdays, today)
        assert result[0][0] == 2  # user 2 has today's birthday

    def test_sort_upcoming_ignores_bad_entries(self) -> None:
        today = datetime.date(2026, 6, 15)
        birthdays = {
            "abc": {"month": 6, "day": 20},
            "1": {"month": 6, "day": 16},
        }
        result = _sort_upcoming(birthdays, today)
        assert len(result) == 1
        assert result[0][0] == 1


# ---------------------------------------------------------------------------
# Layer 2 — Store tests (tmp_path)
# ---------------------------------------------------------------------------

class TestBirthdayStore:
    async def test_set_and_get_birthday(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_id = 100
        user_id = 42

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("birthday", {})
            data.setdefault("birthdays", {})[str(user_id)] = {"month": 3, "day": 14}
            cfg.set_other("birthday", data)
            await p._store.save(cfg)

        cfg2 = await p._store.load(guild_id)
        data2 = cfg2.get_other("birthday", {})
        assert data2["birthdays"][str(user_id)] == {"month": 3, "day": 14}

    async def test_unset_birthday(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_id = 100
        user_id = 42

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("birthday", {})
            data.setdefault("birthdays", {})[str(user_id)] = {"month": 3, "day": 14}
            cfg.set_other("birthday", data)
            await p._store.save(cfg)

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("birthday", {})
            data["birthdays"].pop(str(user_id), None)
            cfg.set_other("birthday", data)
            await p._store.save(cfg)

        cfg3 = await p._store.load(guild_id)
        data3 = cfg3.get_other("birthday", {})
        assert str(user_id) not in data3.get("birthdays", {})

    async def test_guilds_are_isolated(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_a, guild_b = 100, 200
        user_id = 1

        async with p._guild_lock(guild_a):
            cfg = await p._store.load(guild_a)
            data = cfg.get_other("birthday", {})
            data.setdefault("birthdays", {})[str(user_id)] = {"month": 5, "day": 1}
            cfg.set_other("birthday", data)
            await p._store.save(cfg)

        cfg_b = await p._store.load(guild_b)
        data_b = cfg_b.get_other("birthday", {})
        assert str(user_id) not in data_b.get("birthdays", {})


# ---------------------------------------------------------------------------
# Layer 3 — Command flow tests
# ---------------------------------------------------------------------------

class TestBirthdayCommands:
    async def test_birthday_set_valid(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        await p.birthday_set(ctx, 6, 15)

        ctx.respond.assert_called_once()
        call_kwargs = ctx.respond.call_args
        assert "ephemeral" in call_kwargs.kwargs and call_kwargs.kwargs["ephemeral"] is True

        cfg = await p._store.load(100)
        data = cfg.get_other("birthday", {})
        assert data["birthdays"]["1"] == {"month": 6, "day": 15}

    async def test_birthday_set_invalid_date(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        await p.birthday_set(ctx, 2, 30)

        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        response_text = args[0] if args else ""
        assert "Invalid" in response_text or "invalid" in response_text

    async def test_birthday_unset(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        # First set it
        await p.birthday_set(ctx, 6, 15)
        ctx.respond.reset_mock()

        # Then unset it
        await p.birthday_unset(ctx)
        ctx.respond.assert_called_once()

        cfg = await p._store.load(100)
        data = cfg.get_other("birthday", {})
        assert "1" not in data.get("birthdays", {})

    async def test_birthday_unset_not_registered(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=99)

        await p.birthday_unset(ctx)

        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        response_text = args[0] if args else ""
        assert "don't have" in response_text or "no birthday" in response_text.lower()

    async def test_birthday_channel_sets_channel(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        channel = MagicMock()
        channel.id = 999
        channel.mention = "#birthdays"

        await p.birthday_channel(ctx, channel)

        ctx.respond.assert_called_once()
        cfg = await p._store.load(100)
        data = cfg.get_other("birthday", {})
        assert data["channel_id"] == 999

    async def test_birthday_list_empty(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await p.birthday_list(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_birthday_list_shows_entries(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx_set = _ctx(guild_id=100, user_id=1)

        await p.birthday_set(ctx_set, 6, 20)

        ctx_list = _ctx(guild_id=100, user_id=2)
        await p.birthday_list(ctx_list)

        ctx_list.respond.assert_called_once()
        _, kwargs = ctx_list.respond.call_args
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert embed.description is not None
        assert "<@1>" in embed.description
