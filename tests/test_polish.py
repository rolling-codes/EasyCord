import asyncio
import pytest
import discord
from easycord import Bot, Plugin, BotConfig, slash
from easycord.testing import FakeContext, invoke

class MockPlugin(Plugin):
    name = "test_plugin"
    version = "1.2.3"
    author = "Tester"
    description = "A test plugin"

    @slash()
    async def test_cmd(self, ctx):
        await ctx.respond("ok")

@pytest.mark.asyncio
async def test_plugin_metadata():
    p = MockPlugin()
    assert p.name == "test_plugin"
    assert p.version == "1.2.3"
    assert p.author == "Tester"
    assert p.description == "A test plugin"

@pytest.mark.asyncio
async def test_startup_diagnostics(capsys):
    bot = Bot(enable_health_command=True)
    bot.add_plugin(MockPlugin())
    
    # We can't easily trigger on_ready without a full login, but we can call
    # it manually to check the print output.
    await bot.on_ready()
    
    captured = capsys.readouterr()
    assert "EasyCord v" in captured.out
    assert "Plugins: 1" in captured.out
    assert "Commands: 2" in captured.out

@pytest.mark.asyncio
async def test_health_command():
    bot = Bot(enable_health_command=True)
    bot.add_plugin(MockPlugin())
    bot._start_time = 1000 # Mock start time
    
    # Trigger health command via registry
    # We need to find the health command in the tree
    health_cmd = next(c for c in bot.tree.get_commands() if c.name == "health")
    
    ctx = FakeContext.make()
    await health_cmd.callback(ctx.interaction)
    
    assert ctx.responses
    embed = ctx.responses[-1].embed
    assert embed is not None
    assert embed.title == "Bot Health & Telemetry"
    # Check if plugin metadata is in the embed
    plugin_field = next(f for f in embed.fields if f.name == "Plugins")
    assert "test_plugin (v1.2.3)" in plugin_field.value

@pytest.mark.asyncio
async def test_autocomplete_validation_error():
    bot = Bot()
    
    class BadPlugin(Plugin):
        @slash()
        async def bad_cmd(self, ctx, opt: str):
            pass
            
        # Invalid signature: 2 args instead of 1 or 3
        async def bad_ac(self, ctx, current):
            return []

    p = BadPlugin()
    # Manually register autocomplete with bad signature
    # This should happen during add_plugin -> _scan_methods -> _register_slash
    
    with pytest.raises(TypeError) as excinfo:
        # We simulate what _scan_methods does
        bot._register_slash(
            p.bad_cmd,
            name="bad_cmd",
            description="test",
            guild_id=None,
            autocomplete={"opt": p.bad_ac},
            source_plugin="BadPlugin"
        )
    
    assert "Invalid autocomplete signature" in str(excinfo.value)
    assert "Expected (current) or (ctx, current, options)" in str(excinfo.value)

@pytest.mark.asyncio
async def test_route_collision_error_formatting():
    from easycord.registry import InteractionRegistry, InteractionEntry
    registry = InteractionRegistry()
    
    def cb1(): pass
    def cb2(): pass
    
    registry.register_component("test:{id:int}", cb1, source_plugin="PluginA")
    
    with pytest.raises(ValueError) as excinfo:
        registry.register_component("test:{name:int}", cb2, source_plugin="PluginB")
        
    assert "collides with pattern" in str(excinfo.value)
    assert "PluginA" in str(excinfo.value)
    assert "PluginB" in str(excinfo.value)

@pytest.mark.asyncio
async def test_bot_config_health_toggle():
    cfg = BotConfig(token="test", enable_health_command=True)
    bot = cfg.build_bot()
    assert any(c.name == "health" for c in bot.tree.get_commands())
    
    cfg2 = BotConfig(token="test", enable_health_command=False)
    bot2 = cfg2.build_bot()
    assert not any(c.name == "health" for c in bot2.tree.get_commands())
