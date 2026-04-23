from easycord.decorators import slash, on


# ── slash ─────────────────────────────────────────────────────────────────────

def test_slash_marks_function():
    @slash()
    async def cmd(ctx):
        pass

    assert cmd._is_slash is True


def test_slash_uses_function_name_by_default():
    @slash()
    async def my_command(ctx):
        pass

    assert my_command._slash_name == "my_command"


def test_slash_custom_name():
    @slash(name="custom")
    async def cmd(ctx):
        pass

    assert cmd._slash_name == "custom"


def test_slash_default_description():
    @slash()
    async def cmd(ctx):
        pass

    assert cmd._slash_desc == "No description provided."


def test_slash_custom_description():
    @slash(description="Does a thing")
    async def cmd(ctx):
        pass

    assert cmd._slash_desc == "Does a thing"


def test_slash_no_guild_by_default():
    @slash()
    async def cmd(ctx):
        pass

    assert cmd._slash_guild is None


def test_slash_custom_guild():
    @slash(guild_id=12345)
    async def cmd(ctx):
        pass

    assert cmd._slash_guild == 12345


def test_slash_returns_original_function():
    async def original(ctx):
        pass

    wrapped = slash()(original)
    assert wrapped is original


# ── on ────────────────────────────────────────────────────────────────────────

def test_on_marks_function():
    @on("message")
    async def handler(msg):
        pass

    assert handler._is_event is True


def test_on_stores_event_name():
    @on("member_join")
    async def handler(member):
        pass

    assert handler._event_name == "member_join"


def test_on_returns_original_function():
    async def original(msg):
        pass

    wrapped = on("message")(original)
    assert wrapped is original


def test_on_different_event_names():
    @on("message_delete")
    async def h1(msg):
        pass

    @on("reaction_add")
    async def h2(reaction, user):
        pass

    assert h1._event_name == "message_delete"
    assert h2._event_name == "reaction_add"


# ── component / modal ────────────────────────────────────────────────────────

from easycord.decorators import component, modal


def test_component_called_without_id_defaults_to_function_name():
    @component()
    async def save(ctx):
        pass

    assert save._is_component is True
    assert save._component_id == "save"


def test_component_called_without_id_respects_scoped_flag():
    @component(scoped=False)
    async def save(ctx):
        pass

    assert save._component_scoped is False
    assert save._component_id == "save"


def test_modal_called_without_id_defaults_to_function_name():
    @modal()
    async def feedback(ctx, data):
        pass

    assert feedback._is_modal is True
    assert feedback._modal_id == "feedback"


def test_modal_called_without_id_respects_scoped_flag():
    @modal(scoped=False)
    async def feedback(ctx, data):
        pass

    assert feedback._modal_scoped is False
    assert feedback._modal_id == "feedback"


# ── task ──────────────────────────────────────────────────────────────────────

from easycord.decorators import task
import pytest


def test_task_decorator_stamps_attributes():
    from easycord import Plugin

    class MyPlugin(Plugin):
        @task(seconds=30)
        async def my_task(self):
            pass

    assert MyPlugin().my_task._is_task is True
    assert MyPlugin().my_task._task_interval == 30.0


def test_task_decorator_minutes():
    from easycord import Plugin

    class MyPlugin(Plugin):
        @task(minutes=2)
        async def my_task(self):
            pass

    assert MyPlugin().my_task._task_interval == 120.0


def test_task_decorator_hours():
    from easycord import Plugin

    class MyPlugin(Plugin):
        @task(hours=1)
        async def my_task(self):
            pass

    assert MyPlugin().my_task._task_interval == 3600.0


def test_task_decorator_combined():
    from easycord import Plugin

    class MyPlugin(Plugin):
        @task(hours=1, minutes=30, seconds=15)
        async def my_task(self):
            pass

    assert MyPlugin().my_task._task_interval == 3600 + 1800 + 15


def test_task_zero_interval_raises():
    with pytest.raises(ValueError, match="greater than zero"):
        task(seconds=0)
