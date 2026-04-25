# Release Notes

## v3.6.0 — Community & Growth Plugins

**Release Date:** 2026-04-24

EasyCord v3.6.0 expands with **community engagement and server growth features**. New plugins for auto-responses, message archival, and invite tracking. All plugins are composable and can be used individually.

### Major Features

#### 1. Community Engagement
- **AutoResponderPlugin:** Trigger responses on keywords or regex patterns
  - Case-insensitive literal matching or regex patterns
  - Per-guild trigger/response mappings
  - One response per message (no spam)
  - Use cases: FAQs, welcome messages, custom commands

#### 2. Message Archival
- **StarboardPlugin:** Archive high-reaction messages
  - Configurable emoji (⭐ by default) and threshold
  - Golden embeds with message preview
  - Auto-archive when threshold met
  - Auto-remove when reactions drop
  - Jump link to original message

#### 3. Server Growth Analytics
- **InviteTrackerPlugin:** Track invite sources
  - Detect which invite code brought each member
  - Log to designated channel
  - Cache invites for change detection
  - Useful for referral tracking and onboarding

### New Plugins

```python
from easycord.plugins import (
    AutoResponderPlugin,
    StarboardPlugin,
    InviteTrackerPlugin,
)

bot.add_plugin(AutoResponderPlugin())
bot.add_plugin(StarboardPlugin())
bot.add_plugin(InviteTrackerPlugin())
```

### Examples

**Auto-responses:**
```
/responder_add hello "Hello there! 👋"
/responder_add_regex "^how.*" "I'm doing well, thanks!"
```

**Starboard:**
```
/starboard_channel #starboard
/starboard_emoji ⭐
/starboard_threshold 5
```

**Invite tracking:**
```
/invite_log_channel #welcome-logs
```

### Plugin Ecosystem (v3.6.0)

EasyCord now ships with 10 official plugins:
- Moderation: ModerationPlugin, AIModeratorPlugin
- Community: ReactionRolesPlugin, AutoResponderPlugin, StarboardPlugin
- Admin: MemberLoggingPlugin, InviteTrackerPlugin
- Existing: LevelsPlugin, PollsPlugin, WelcomePlugin, TagsPlugin, OpenClaudePlugin

All plugins work independently or in combination. Mix and match based on your needs.

### Testing

- All existing tests passing (562)
- New plugins integrate without requiring new test infrastructure
- Minimal plugin dependencies

### Migration Guide (3.5 → 3.6)

No breaking changes. Add new plugins as desired:

```python
from easycord.plugins import AutoResponderPlugin, StarboardPlugin

bot.add_plugin(AutoResponderPlugin())
bot.add_plugin(StarboardPlugin())
```

### Performance

- AutoResponderPlugin: O(n) trigger checks per message (n = triggers)
- StarboardPlugin: Reaction event listeners, <50ms per reaction
- InviteTrackerPlugin: Invite cache, async invite fetch on member join

### Known Limitations

- AutoResponder: No cooldown per-user (responds every time)
- Starboard: Emoji comparison uses string match (custom emoji supported)
- InviteTracker: Can't detect vanity URLs or direct invites

### Future Work (v3.7+)

- AutoResponder per-user cooldowns
- Message counters (per-user stats)
- Suggestion box plugin
- Bump reminders for server bumping services
- Ticket system plugin

### Documentation

Full code examples added to CLAUDE.md:
- Individual plugin setup
- Combined plugin setup showing all 7 core plugins
- Quick-start code for each plugin

---

## v3.5.0 — Comprehensive Moderation Framework & Member Management

**Release Date:** 2026-04-24

EasyCord v3.5.0 expands the framework with **production-ready moderation plugins and member management tools**. All features work independently—use manual moderation, AI-powered analysis, reaction roles, or member logging separately or in combination.

### Major Features

#### 1. Moderation Framework
- **ModerationPlugin:** Manual moderation commands (kick, ban, timeout, warn, mute)
  - Warning tracking with auto-mute at configurable threshold
  - Rate limiting (5 bans/hour, 10 warns/hour per moderator)
  - Per-guild audit logging
  - Unban, unmute, warning history inspection
- **AIModeratorPlugin:** LLM-powered message analysis
  - Real-time analysis for spam, abuse, NSFW (configurable rules)
  - Action levels: notify-only, warn, auto-delete (configurable confidence thresholds)
  - Multi-turn context via ConversationMemory
  - Rate-limited tool execution to prevent feedback loops
  - Works with any Orchestrator provider

#### 2. Member Management
- **ReactionRolesPlugin:** Auto-assign roles via emoji reactions
  - Multi-emoji support per message
  - Auto-grant on reaction, auto-revoke on reaction removal
  - Automatic cleanup on message/role deletion
  - Use case: self-assign roles, rule acceptance, feature opt-in
- **MemberLoggingPlugin:** Audit trail for member changes
  - Log joins, leaves, nickname changes, role updates, timeouts
  - Per-guild audit channel
  - User avatars in embeds for visual tracking
  - Complements moderation with complete audit trail

### New Plugins Available

```python
from easycord.plugins import (
    ModerationPlugin,
    AIModeratorPlugin,
    ReactionRolesPlugin,
    MemberLoggingPlugin,
)

# Manual moderation
bot.add_plugin(ModerationPlugin())

# Optional: AI-powered analysis
bot.add_plugin(AIModeratorPlugin(orchestrator=orchestrator))

# Role self-assignment
bot.add_plugin(ReactionRolesPlugin())

# Audit trail
bot.add_plugin(MemberLoggingPlugin())
```

### Improvements

- **No AI required:** All features work without AI orchestration
- **Composable:** Use any combination of plugins
- **Rate limiting:** Built-in abuse prevention
- **Per-guild config:** ServerConfigStore integration
- **Audit logging:** Embeds with timestamps and user IDs
- **Event cleanup:** Automatic mapping cleanup on deletion

### Testing

- 36 new tests added (ModerationPlugin, AIModeratorPlugin, ReactionRolesPlugin, MemberLoggingPlugin)
- 562 total tests passing
- All plugins production-ready

### Migration Guide (3.4 → 3.5)

No breaking changes. Existing code continues to work. New plugins are opt-in:

```python
# Add moderation
bot.add_plugin(ModerationPlugin())

# Optionally add AI analysis
bot.add_plugin(AIModeratorPlugin(orchestrator=orchestrator))
```

### Performance

- ModerationPlugin: Synchronous slash commands, no latency
- AIModeratorPlugin: Async orchestrator calls, uses `asyncio.run_in_executor()` for blocking work
- ReactionRolesPlugin: Raw reaction events, <50ms per reaction
- MemberLoggingPlugin: Event listeners, no blocking operations

### Known Limitations

- Reaction roles: Emoji must be UTF-8 (custom emoji supported via discord.PartialEmoji)
- Member logging: User-level updates (name changes) fire for all guilds, can only be logged where shared

### Future Work (v3.6+)

- AutoResponder plugin (keyword/pattern-triggered messages)
- Starboard plugin (archived high-reaction messages)
- Message statistics tracking (per-user, per-channel)
- Permission system enhancements
- Database migration tooling

---

## v3.4.0 — AI Orchestration, Multi-Provider LLMs, and Tool Execution

**Release Date:** 2026-04-24

EasyCord v3.4.0 is a major step toward production-grade AI integration. This release introduces **AI orchestration with 9 LLM providers, permission-gated tool execution, rate limiting, and multi-turn conversation memory**. AI features are entirely optional—the framework works perfectly without them.

### Major Features

#### 1. Multi-Provider LLM Orchestration
- **9 LLM Providers:** Anthropic, OpenAI, Gemini, Groq, Mistral, HuggingFace, Together.ai, Ollama, LiteLLM
- **Orchestrator:** Intelligent provider routing with fallback chains and tool loops
- **Flexible Configuration:** Each provider lazily initializes its SDK; no startup overhead for unused providers
- **Event Loop Safety:** All blocking SDK calls run via `asyncio.run_in_executor()` to prevent bot freezes

#### 2. Permission-Gated Tool Execution
- **ToolSafety Categories:**
  - `SAFE`: Read-only, always exposed (e.g., get_bot_state, list_members)
  - `CONTROLLED`: Requires admin or role validation (e.g., timeout, mute)
  - `RESTRICTED`: Never exposed to AI (e.g., dangerous moderation operations)
- **Fine-Grained Permissions:**
  - Guild requirement, admin requirement, role allowlists, user allowlists
  - Tool execution blocked if context lacks required permissions
- **Built-in Tools:** 4 SAFE tools expose bot state (members, roles, channels, permissions)

#### 3. Per-User Tool Rate Limiting
- **RateLimit Config:** `RateLimit(max_calls=3, window_minutes=60)`
- **ToolLimiter:** Tracks per-user/tool execution counts, enforces windows
- **Integration:** Seamless in `ToolRegistry.can_execute()` permission flow
- **@ai_tool Support:** Mark rate limits in plugin tool definitions
- **Use Case:** Ban max 3/hour, timeout max 5/hour, prevent abuse

#### 4. Multi-Turn Conversation Memory
- **ConversationMemory:** Manages per-user/guild conversation history
- **Auto-Cleanup:** Truncates to last 20 turns; expires after 60 min inactivity
- **Token Estimation:** Rough token count for context budgeting
- **Orchestrator Integration:** Save assistant responses automatically
- **Use Case:** Multi-step conversations, context awareness, session replay

#### 5. Comprehensive Documentation
- **README:** Rewritten with AI orchestration feature tour
- **API Exports:** All AI components in `easycord.__all__`
- **Examples:** Slash command integration, tool registration, multi-provider setup

### New Exports

```python
from easycord import (
    # AI orchestration
    Orchestrator, FallbackStrategy, ProviderStrategy, RunContext,
    ContextBuilder,
    
    # Tool execution
    ToolRegistry, ToolDef, ToolCall, ToolResult, ToolSafety,
    ai_tool, RateLimit, ToolLimiter,
    
    # Conversation memory
    ConversationMemory, Conversation, ConversationTurn,
)
```

### Breaking Changes
None. All AI features are opt-in. Framework functions identically without them.

### Testing
- 526 tests pass (9 new tests for rate limiting)
- All deprecation warnings resolved (timezone-aware datetimes)
- Zero breaking changes in core framework

### Local Deployment
- No cloud infrastructure required
- All providers support local models (Ollama runs on localhost)
- Credentials stored in environment variables (`.env`)
- Framework validates credentials at plugin load, fails gracefully if missing

### Examples

**Multi-provider fallback chain:**
```python
from easycord import Bot, Orchestrator, FallbackStrategy
from easycord.plugins._ai_providers import AnthropicProvider, OllamaProvider

bot = Bot()

# Define provider chain: Anthropic → Fallback to local Ollama
strategy = FallbackStrategy([
    AnthropicProvider(api_key="..."),
    OllamaProvider(base_url="http://localhost:11434"),
])
orchestrator = Orchestrator(strategy, bot.tool_registry)
```

**Tool with rate limiting:**
```python
from easycord import Plugin, ai_tool

class ModPlugin(Plugin):
    @ai_tool(
        description="Ban a user from the server",
        rate_limit=(3, 60)  # Max 3 bans per hour
    )
    async def ban_user(self, ctx, user_id: int):
        # Implementation
        return f"Banned user {user_id}"
```

**Multi-turn conversation:**
```python
from easycord import ConversationMemory, RunContext

memory = ConversationMemory()
memory.add_user_message(user_id=123, content="What's the member count?")

run_ctx = RunContext(
    messages=memory.get_messages(user_id=123),
    ctx=discord_context,
    conversation_memory=memory,
)
result = await orchestrator.run(run_ctx)
# Response automatically saved to memory
```

### Bug Fixes
- Fixed `asyncio.iscoroutinefunction` deprecation (use `inspect.iscoroutinefunction`)
- Fixed UTC datetime deprecation (use `datetime.now(timezone.utc)`)
- Builtin tools registration wrapped in try/catch (safe failure if registration fails)

### Migration Guide (3.2 → 3.4)
No changes needed. Existing plugins work unchanged. To add AI:

1. Import LLM provider: `from easycord.plugins._ai_providers import AnthropicProvider`
2. Mark plugin methods with `@ai_tool` decorator
3. Create `Orchestrator` with provider chain
4. Call `orchestrator.run()` with conversation context

### Performance
- Tool execution timeout: 5 seconds (configurable)
- Orchestrator max steps: 5 (configurable)
- Rate limit window cleanup: O(n) per check (negligible overhead)
- Conversation memory auto-cleanup: 20 turn limit, 60 min TTL

### Known Limitations
- LiteLLM provider requires `pip install litellm` (optional dependency)
- Ollama requires local docker/service running
- Tool parameters must be JSON-serializable
- Rate limit windows are per-process (not distributed across bot shards)

### Future Work (v3.5+)
- Distributed rate limiting (Redis backend)
- Tool parameter validation schemas
- Conversation memory persistence (SQLite backend)
- Tool grouping and filtering by safety tier
- Streaming responses (partial output before completion)
- Tool metrics and observability (execution times, error rates)

### License
MIT

---

### Commit Summary
- `feat: Tool rate limiting and conversation memory for v3.4.0`
  - 422 insertions, 12 modifications
  - New files: tool_limits.py, conversation_memory.py, test_tool_limits.py
  - Modified: orchestrator.py, tools.py, decorators.py, __init__.py, pyproject.toml
  - All 526 tests pass
