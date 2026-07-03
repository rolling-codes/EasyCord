# Documentation Restructure Plan

## Current State (25 guides)
Too many docs. Users get lost between "where do I start?" and "how do I do X?" Overlap between related topics.

## Proposed Structure (12 core guides)
Consolidated, goal-oriented, easy navigation. No clicks wasted.

---

## New Documentation Map

```
📚 CORE GUIDES (12 total)

1. GETTING STARTED (entry point)
   ├─ Installation & your first bot
   ├─ Project layout
   ├─ First slash command
   └─ Quick next steps → [2], [3], [4]

2. BUILDING COMMANDS (merged: Interactions + Subcommand Groups)
   ├─ Slash commands with typed parameters
   ├─ Autocomplete
   ├─ Context menus
   ├─ Subcommand groups and namespaces
   ├─ Buttons, select menus, modals
   └─ When to use what (decision tree)

3. COMMAND SYNC & REGISTRATION
   ├─ How Discord command registration works
   ├─ Sync workflow (preview → diff → apply)
   ├─ Guild-scoped vs global
   ├─ Removal confirmation
   └─ Troubleshooting out-of-sync

4. REQUEST LIFECYCLE (merged: Middleware + Hooks + Error Handling)
   ├─ How requests flow through the bot
   ├─ Middleware: guards, rate limiting, logging
   ├─ Error handling waterfall (per-command → global)
   ├─ Lifecycle hooks (before/after command, plugin load/unload)
   ├─ Building custom middleware
   └─ Security patterns

5. INTERACTIVE FEATURES
   ├─ Dynamic component routing (buttons, dropdowns with URL-style routes)
   ├─ Built-in UI helpers (ctx.confirm, ctx.paginate, ctx.ask_form)
   ├─ Component TTL and expiry
   └─ Multi-step interactions (forms, wizard flows)

6. ORGANIZING CODE
   ├─ Plugin architecture (why, when, how)
   ├─ Plugin lifecycle and state
   ├─ Event bus for decoupled communication
   ├─ Task scheduling (@task, intervals, error handling)
   ├─ Separating concerns
   └─ Testing plugins in isolation

7. STORAGE & STATE
   ├─ Per-guild storage patterns
   ├─ SQLite backend setup
   ├─ Memory database for dev/testing
   ├─ Concurrency safety (mutate contract)
   ├─ Database backend comparison
   └─ When to use what (decision tree)

8. AI FEATURES (optional)
   ├─ What AI features are available (and that they're optional)
   ├─ Conversation memory for multi-turn chat
   ├─ Built-in AI plugins (OpenClaw, AIModeratorPlugin)
   ├─ Provider selection (Claude, OpenAI, etc.)
   ├─ Rate limiting and eviction
   └─ Offline mode (bot works without AI)

9. BUILT-IN PLUGINS
   ├─ Overview of 28 bundled plugins (categories)
   ├─ Quick-start for each: economy, levels, moderation, reminders, etc.
   ├─ Storage requirements
   ├─ Customization patterns
   └─ Links to full reference

10. TESTING
    ├─ Why test (offline, no Discord needed, confident deploys)
    ├─ Unit testing with PluginTestSuite
    ├─ Fakes and builders (FakeContextBuilder)
    ├─ Invoking commands without Discord
    ├─ Test patterns by use case
    └─ Coverage and CI integration

11. ADVANCED DEVELOPMENT
    ├─ Type checking with Pyright
    ├─ Hot-reload development (reload without restart)
    ├─ Developer CLI (easycord new, doctor, inspect)
    ├─ Publishing plugins to PyPI
    ├─ Deprecation and versioning
    └─ Performance profiling

12. TROUBLESHOOTING & REFERENCE
    ├─ Common day-one issues with fixes
    ├─ Full Context API reference (quick lookup)
    ├─ FAQ: "Why doesn't my command show up?"
    ├─ FAQ: "How do I store user data?"
    ├─ FAQ: "How do I test without Discord?"
    └─ Glossary (guild, context, plugin, etc.)
```

---

## Navigation Strategy

### For Users
**Goal-based entry**: "I want to…"
- Add a command → [Building Commands]
- Store data → [Storage & State]
- Add AI → [AI Features]
- Test my bot → [Testing]
- Deploy → [Testing] then [Troubleshooting]

**No nested "see also" links**. Each guide is self-contained. At the bottom, "Learn more":
- If you want X (natural next step) → [Guide Name]
- If you want Y → [Guide Name]

### For Developers
**Workflow-based entry**: "I'm doing X…"
- Building a new feature → [Building Commands] → [Organizing Code] → [Testing]
- Debugging → [Request Lifecycle] → [Troubleshooting]
- Deploying → [Storage & State] → [Testing]

---

## Implementation Timeline

### Phase 1 (v5.51.0 — In Progress)
- [x] README: Add "Day 1" guide (done in PR #72)
- [x] Create `docs/RESTRUCTURE_PLAN.md` with consolidated guide plan
- [x] Update `docs/README.md` with goal-based navigation
- [x] Consolidate: `Interactions.md` + `Subcommand-groups.md` + `Components-dynamic-routing.md` → **Building Commands**
- [x] Consolidate: `Middleware-patterns.md` + `Error-handling.md` + `Hooks.md` → **Request Lifecycle**
- [x] Consolidate: `Plugin-authoring.md` + `Event-bus.md` + `Task-scheduling.md` → **Organizing Code**
- [ ] Consolidate: `Context-interactive-ui.md` standalone (already self-contained)

### Phase 2 (v5.52.0)
- Remove old 15 guides (interactions.md, subcommand-groups.md, etc.)
- Add decision trees to remaining guides ("When to use X vs Y?")
- Verify navigation is non-programmer-friendly

### Phase 3 (v5.53.0)
- Add visual diagrams (request flow, plugin lifecycle)
- Video walkthroughs (Day 1, adding storage, testing)
- Community examples gallery

---

## Example: "Building Commands" (Consolidated)

Current state:
- `interactions.md` (40KB) — slash commands, autocomplete, components
- `subcommand-groups.md` (8KB) — SlashGroup
- `components-dynamic-routing.md` (12KB) — dynamic routing

Consolidated `building-commands.md` (60KB):
1. Slash commands 101 (what, why, how)
2. Parameters and types (str, int, float, discord.User, etc.)
3. Autocomplete
4. When to use subcommand groups (decision tree)
5. Subcommand groups (SlashGroup API, permission inheritance)
6. Buttons and select menus
7. Dynamic component routing (URL-style routes, TTL)
8. Modals (multi-field forms)
9. Context menus
10. Common patterns & pitfalls

**Navigation**:
- Top: Quick index (links to sections 1-9)
- Each section: Self-contained, one concept
- Bottom: "Next: [Organizing Code] or [Testing Commands]"

---

## Success Metrics

✅ New user picks a "I want to…" goal and finds the right guide in one click
✅ No guide longer than 15KB (breaks into sections naturally)
✅ Decision trees replace ambiguous "when to use X" questions
✅ No nested "see also" links (dead ends)
✅ Docs fully self-contained: no "read X first" chains beyond "Start here"
✅ 25 guides → 12, reducing navigation paralysis by 50%
