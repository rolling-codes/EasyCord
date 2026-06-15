"""SecurityLabPlugin — Educational security demonstrations for Discord bots."""

import re
import threading
from typing import Any, Dict

import discord

from easycord import EmbedBuilder, Plugin, slash
from easycord.security import escape_mentions, safe_regex, strip_injection_prefixes, truncate


class SecurityLabPlugin(Plugin):
    """Demonstrates real attack vectors and their defenses in a safe sandbox."""

    def __init__(self):
        super().__init__()
        self._lab_store: Dict[str, Any] = {}

    @slash(description="Store a payload and replay it (stored injection demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_stored_injection(self, ctx, payload: str):
        """Demonstrates stored mention injection attack."""
        self._lab_store["injection_payload"] = payload
        retrieved = self._lab_store["injection_payload"]

        safe_retrieved = escape_mentions(retrieved)

        embed = (
            EmbedBuilder()
            .title("🚨 Stored Injection Attack Detected")
            .color(discord.Color.from_rgb(220, 20, 60))
            .field("What Happened", f"Stored: `{retrieved}`\n\nRetrieved: `{retrieved}`\n\n**Result: @everyone mention FIRED**", inline=False)
            .field("Why It Works", "User input was stored and replayed without sanitization. Mentions embedded in text are executed by Discord.", inline=False)
            .field("How to Fix", f"Escape `@everyone` and `@here`:\n```\n{safe_retrieved}\n```")
            .footer("Lab: Stored Injection")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Send maximum-length Discord string (input overflow demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_input_overflow(self, ctx):
        """Demonstrates unbounded input acceptance."""
        max_discord_str = "A" * 6000
        embed = (
            EmbedBuilder()
            .title("⚠️ Unbounded Input Accepted")
            .color(discord.Color.from_rgb(255, 165, 0))
            .field("What Happened", f"Accepted {len(max_discord_str)} chars with no truncation.", inline=False)
            .field("Why It Works", "Most EasyCord plugins have no hard limit on free-text slash parameters.", inline=False)
            .field("How to Fix", f"Hard-cap all user inputs:\n```python\ntruncate(user_input, max_len=2000)\n```")
            .footer("Lab: Input Overflow")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Compile a catastrophic regex (ReDoS demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_redos(self, ctx, pattern: str):
        """Demonstrates ReDoS vulnerability."""
        test_subject = "A" * 30

        result = safe_regex(pattern, test_subject, timeout_ms=100)
        timed_out = result is None

        status = "🔴 **HUNG** (regex timeout)" if timed_out else "✅ Matched OK"

        embed = (
            EmbedBuilder()
            .title("⚡ ReDoS (Regex Denial of Service)")
            .color(discord.Color.from_rgb(255, 99, 71))
            .field("Pattern", f"`{pattern}`", inline=False)
            .field("Result", status, inline=False)
            .field("Why It Works", "Patterns like `(a+)+$` cause exponential backtracking on non-matching input.", inline=False)
            .field("How to Fix", "Run regex with timeout + validate complexity:\n```python\nsafe_regex(pattern, text, timeout_ms=100)\n```")
            .footer("Lab: ReDoS")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Echo text as LLM response (prompt injection demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_prompt_injection(self, ctx, text: str):
        """Demonstrates prompt injection attack."""
        raw = text
        sanitized = strip_injection_prefixes(text)

        embed = (
            EmbedBuilder()
            .title("🧠 Prompt Injection Attack")
            .color(discord.Color.from_rgb(139, 0, 139))
            .field("Raw Input", f"`{raw}`", inline=False)
            .field("What Happened", "Raw text passed to LLM without filtering.", inline=False)
            .field("Why It Works", "Phrases like 'Ignore previous instructions' can steer LLM behavior.", inline=False)
            .field("Sanitized Output", f"`{sanitized}`")
            .field("How to Fix", "Strip known injection prefixes before forwarding to AI:\n```python\nstrip_injection_prefixes(prompt)\n```")
            .footer("Lab: Prompt Injection")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Test phantom permission gate (silent lockout demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_phantom_permission(self, ctx):
        """Demonstrates typo in permission gate that silently blocks access."""
        embed = (
            EmbedBuilder()
            .title("🔒 Phantom Permission Gate")
            .color(discord.Color.from_rgb(65, 105, 225))
            .field("What Happened", "Permission check failed silently because permission name was misspelled.", inline=False)
            .field("Example Code", "```python\n@slash(permissions=['kick_member'])  # Typo! Should be 'kick_members'\n```", inline=False)
            .field("Why It Works", "Python's `getattr(perms, 'kick_member', False)` silently returns False. Command is locked out, no error.", inline=False)
            .field("How to Fix", "Validate permission names at decorator time:\n```python\n# Check that all perms exist on Member.guild_permissions\n```")
            .footer("Lab: Phantom Permission")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Test rate-limit bypass (flood demo)", permissions=["manage_guild"], ephemeral=True)
    async def lab_flood_check(self, ctx):
        """Demonstrates flood attack without rate limiting."""
        success_count = 20
        embed = (
            EmbedBuilder()
            .title("💥 Flood Attack (No Rate Limit)")
            .color(discord.Color.from_rgb(255, 69, 0))
            .field("What Happened", f"Executed 20 times in rapid succession. All {success_count} succeeded (no rate limit).", inline=False)
            .field("Why It Works", "`SecurityManager` middleware is opt-in. Bots without it have zero flood protection.", inline=False)
            .field("How to Fix", "Apply `SecurityManager` on bot startup:\n```python\nfrom easycord import SecurityManager\nSecurityManager().apply(bot)\n```")
            .footer("Lab: Flood Attack")
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(description="Summary of all 6 attack vectors and severity ratings", permissions=["manage_guild"], ephemeral=True)
    async def lab_report(self, ctx):
        """Summarizes all 6 security labs."""
        embed = (
            EmbedBuilder()
            .title("🛡️ SecurityLab — 6 Attack Vectors")
            .color(discord.Color.from_rgb(34, 139, 34))
            .field("1️⃣ Stored Injection", "Severity: **CRITICAL**\nMention-based @everyone pings", inline=False)
            .field("2️⃣ Input Overflow", "Severity: **HIGH**\nNo length cap on user input", inline=False)
            .field("3️⃣ ReDoS", "Severity: **HIGH**\nCatastrophic regex backtracking", inline=False)
            .field("4️⃣ Prompt Injection", "Severity: **HIGH**\nLLM instruction override", inline=False)
            .field("5️⃣ Phantom Permission", "Severity: **MEDIUM**\nSilent typo-based lockout", inline=False)
            .field("6️⃣ Flood Attack", "Severity: **MEDIUM**\nNo default rate limiting", inline=False)
            .footer("Run /lab_<attack> for details")
            .build()
        )
        await ctx.respond(embed=embed)
