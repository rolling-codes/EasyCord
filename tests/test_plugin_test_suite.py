"""Demo: using PluginTestSuite reduces plugin test boilerplate."""
from __future__ import annotations

import pytest

from easycord import Plugin, slash
from easycord.testing import PluginTestSuite, __all__ as testing_all


class PingPlugin(Plugin):
    @slash(description="Ping")
    async def ping(self, ctx):
        await ctx.respond("Pong!")


class EchoPlugin(Plugin):
    @slash(description="Echo a message")
    async def echo(self, ctx, message: str):
        await ctx.respond(message)


class SecretPlugin(Plugin):
    @slash(description="Secret response")
    async def secret(self, ctx):
        await ctx.respond("shh", ephemeral=True)


class TestPingPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.plugin = self.make_plugin(PingPlugin)

    async def test_ping_responds_pong(self):
        ctx = await self.invoke_command("ping")
        self.assert_last_response(ctx, "Pong!")

    async def test_ping_response_count(self):
        ctx = await self.invoke_command("ping")
        self.assert_response_count(ctx, 1)

    async def test_ping_response_contains(self):
        ctx = await self.invoke_command("ping")
        self.assert_response_contains(ctx, "Pon")


class TestEchoPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.make_plugin(EchoPlugin)

    async def test_echo_returns_message(self):
        ctx = await self.invoke_command("echo", message="hello world")
        self.assert_last_response(ctx, "hello world")


class TestSecretPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.make_plugin(SecretPlugin)

    async def test_secret_is_ephemeral(self):
        ctx = await self.invoke_command("secret")
        self.assert_ephemeral(ctx)


class TestPluginTestSuiteExport:
    """PluginTestSuite is importable from easycord.testing __all__."""

    def test_in_all(self):
        assert "PluginTestSuite" in testing_all

    def test_importable(self):
        from easycord.testing import PluginTestSuite as PTS
        assert PTS is PluginTestSuite
