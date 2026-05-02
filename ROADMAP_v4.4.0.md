# EasyCord v4.4.0 Localization Roadmap

**Phase 1 (v4.4.0):** Completed 2026-05-02  
**Phase 2+ (v4.5.0+):** Planning in progress

---

## Vision

v4.4.0 elevates EasyCord's localization system from production-ready to industry-leading. Build Discord bots that seamlessly support multiple languages at scale, with minimal developer overhead and maximum flexibility.

**Core principles:**
- **Zero overhead for English-only bots** — No required configuration changes
- **Simple for basic multi-language support** — Drop in JSON files, bot speaks multiple languages
- **Powerful for advanced use cases** — Custom language detection, lazy-loaded catalogs, ICU pluralization
- **Observable** — Clear metrics and logging for translation coverage, missing translations, auto-translation quality
- **Type-safe** — Full TypeScript support (optional, via stubs)

---

## Phase 1: Enhanced Translation Management

### Feature 1.1: Locale File Format Support

**Problem:** Currently, translations must be registered programmatically via `LocalizationManager(translations={...})`. This doesn't scale for large translation catalogs.

**Solution:** Support common file formats for bulk translation loading:
- **JSON** (recommended) — Simple, widely used
- **YAML** (optional) — Human-readable for translators
- **CSV** (optional) — Import/export from translation services (Crowdin, Weblate)

**API (proposed):**
```python
from easycord import LocalizationManager

manager = LocalizationManager.from_directory("locales/")
# Loads: locales/en.json, locales/es.json, locales/fr.json, etc.

manager = LocalizationManager.from_file("locales/es.yaml", locale="es")

manager = LocalizationManager.from_csv("translations.csv", source_locale="en")
```

**File format (JSON):**
```json
{
  "commands": {
    "ping": {
      "name": "ping",
      "description": "Check bot status",
      "response": "Pong! 🏓"
    }
  },
  "errors": {
    "user_not_found": "User {user_id} not found",
    "permission_denied": "You don't have permission to use this command"
  }
}
```

**Benefits:**
- Translator-friendly (can use standard translation management tools)
- Separates content from code
- Enables easy version control of translations
- Supports incremental translation workflows (partial translations per language)

**Testing:** File loading, format validation, merge behavior, fallback on missing files

---

### Feature 1.2: Lazy-Loaded Translations

**Problem:** Embedding all translations in memory is inefficient for bots supporting 20+ languages with large catalogs.

**Solution:** Load translations on-demand, with optional caching:

**API (proposed):**
```python
from easycord import LocalizationManager, LazyTranslationLoader

# Load translations on-first-access
loader = LazyTranslationLoader(
    base_dir="locales/",
    cache_strategy="memory",  # or "lru" for bounded cache, "none" for disk-only
)

manager = LocalizationManager(translations_loader=loader)

# First call to get("es", ...) loads es.json
# Subsequent calls use cache
```

**Behavior:**
- Translations are loaded into memory only when a locale is first requested
- Optional LRU cache for bounded memory usage (e.g., keep 5 most-recent locales in memory)
- Missing translation files fail gracefully (log warning, fall back to default locale)
- Cache statistics available for monitoring

**Benefits:**
- Reduce memory footprint for bots with many languages
- Fast boot time (don't load all translations on startup)
- Observable cache hit rate and memory usage

**Testing:** Cache hit rates, memory bounds, concurrent access, fallback behavior

---

## Phase 2: Smart Language Detection & Selection

### Feature 2.1: Automatic Locale Detection from Discord

**Problem:** Users must manually specify their language. Discord provides user locale via gateway, but EasyCord doesn't leverage it.

**Solution:** Auto-detect user locale from Discord's `preferred_locale` field:

**API (proposed):**
```python
from easycord import LocalizationManager

manager = LocalizationManager(
    auto_detect_user_locale=True,  # Use Discord's preferred_locale
    fallback_to_guild=True,         # Fall back to guild locale if user locale unavailable
    fallback_to_default=True        # Fall back to app default if neither available
)

# In a command:
@bot.slash(description="...")
async def cmd(ctx):
    # ctx.get_locale() returns best-guess from auto-detection
    msg = manager.get("key", locale=ctx.get_locale())
```

**Behavior:**
- User locale set in Discord User Settings → `Localization` → `Language`
- Fallback chain: user locale → guild locale → default locale → English
- Logging tracks locale selection (for observability)
- Metrics track coverage (% of users with supported language)

**Benefits:**
- User experience seamlessly respects Discord settings
- No friction for multi-language servers
- Observable language adoption

**Testing:** Fallback chain, discord-provided locale parsing, unsupported locale handling

---

### Feature 2.2: Guild-Level Locale Override

**Problem:** Multi-language servers need per-guild language settings, but there's no built-in API.

**Solution:** Store guild language preference via `ServerConfigStore`:

**API (proposed):**
```python
from easycord import Bot, ServerConfig

bot = Bot()

@bot.slash(description="Set server language")
async def set_lang(ctx, language: str):
    supported = ["en", "es", "fr", "de"]
    if language not in supported:
        await ctx.respond(f"Supported: {', '.join(supported)}", ephemeral=True)
        return
    
    cfg = ServerConfig.load(ctx.guild.id)
    cfg.set("language", language)
    cfg.save()
    
    await ctx.respond(f"Server language set to {language}")

# In any command:
@bot.slash()
async def cmd(ctx):
    cfg = ServerConfig.load(ctx.guild.id)
    guild_lang = cfg.get("language", "en")
    msg = manager.get("key", locale=guild_lang)
```

**Behavior:**
- Stored in per-guild config JSON (existing `ServerConfigStore`)
- Accessible via admin-only command
- Defaults to auto-detected user locale or app default if not set
- Logged for audit trail

**Benefits:**
- Multi-language servers can enforce consistent bot language
- Integrates cleanly with existing config system
- Observable language adoption per guild

**Testing:** Config storage, admin checks, fallback behavior

---

## Phase 3: Advanced Pluralization & Formatting

### Feature 3.1: ICU Message Format Support (Optional)

**Problem:** Simple string templates don't handle pluralization, gender, or complex formatting across languages. Each language has different rules.

**Solution:** Optional ICU MessageFormat support for advanced formatting:

**API (proposed):**
```python
from easycord import LocalizationManager

manager = LocalizationManager.from_directory("locales/", format_style="icu")

# Locale file (locales/en.json)
{
  "items_count": "{count, plural, =0 {You have no items} one {You have one item} other {You have {count} items}}"
}

# Usage:
msg = manager.format("items_count", count=5)
# Returns: "You have 5 items"
```

**Format styles:**
- `"simple"` (default) — `.format(name=value)` templating
- `"icu"` — Full ICU message format with pluralization, gender, date/time formatting

**Benefits:**
- Proper pluralization across languages (not all languages pluralize like English)
- Gender-aware translations where needed
- Date/time/number formatting respects locale conventions

**Testing:** Format parsing, pluralization rules per language, edge cases

---

### Feature 3.2: Typed Translation Keys (Strict Mode)

**Problem:** String keys are error-prone and don't provide IDE autocomplete. Typos lead to runtime fallbacks.

**Solution:** Optional strict typing for translation keys:

**Implementation approach (no code changes needed):**
- Document how to use typing stubs (`.pyi` files) to provide type checking
- Provide type stub generator that reads translation JSON and generates type hints
- Support both strict mode (only defined keys allowed) and permissive mode (any key, type-checked if defined)

**Example (mypy/pyright):**
```python
# locales/en.json
{"greetings": {"hello": "Hello"}}

# Generated stub (locales/__init__.pyi)
def get(key: Literal["greetings.hello", ...], ...) -> str: ...

# Usage
manager.get("greetings.hello")  # ✓ type-checked
manager.get("typo.key")         # ✗ type checker error
```

**Benefits:**
- Catch translation key typos at development time
- IDE autocomplete for available translation keys
- No runtime overhead (purely static analysis)

**Testing:** Type stub generation, mypy/pyright validation

---

## Phase 4: Observability & Operations

### Feature 4.1: Translation Coverage Metrics

**Problem:** No visibility into which languages are supported, what % of keys are translated, or which keys are missing translations.

**Solution:** Built-in metrics for translation completeness:

**API (proposed):**
```python
from easycord import LocalizationManager

manager = LocalizationManager.from_directory("locales/")

# Get coverage stats
coverage = manager.coverage_report()
# Returns:
# {
#   "en": {"total_keys": 100, "translated": 100, "coverage": 1.0},
#   "es": {"total_keys": 100, "translated": 85, "coverage": 0.85},
#   "fr": {"total_keys": 100, "translated": 92, "coverage": 0.92},
# }

missing = manager.missing_keys("es")
# Returns: ["errors.unknown", "admin.ban_reason", ...]

# Export report
manager.export_coverage_report("coverage.json")
```

**Behavior:**
- Auto-calculated when translations load
- Updated when translations are registered/updated
- Available for logging, metrics export, or dashboard display

**Benefits:**
- Identify incomplete translations before release
- Plan localization efforts (which languages need work)
- Monitor translation quality over time

**Testing:** Coverage calculation, incremental updates, edge cases (partial translations)

---

### Feature 4.2: Missing Translation Logging

**Problem:** When a translation key is missing, the fallback is silent. Developers don't know which keys need translation.

**Solution:** Log and track missing translations:

**API (proposed):**
```python
from easycord import LocalizationManager
import logging

logger = logging.getLogger("easycord.i18n")
logger.setLevel(logging.DEBUG)  # or WARNING for prod

manager = LocalizationManager.from_directory("locales/")
manager.track_missing_keys = True  # Enable tracking

# When a key is missing:
msg = manager.get("unknown.key", locale="es", default="fallback")
# Logs at DEBUG level:
# "Missing translation key 'unknown.key' for locale 'es', using fallback"

# At end of request/session:
missing_in_session = manager.get_missing_keys_summary()
# Use for metrics, alerting, or localization prioritization
```

**Behavior:**
- Track missing keys per locale, per session
- Log at DEBUG (no noise in production)
- Metrics available for monitoring/alerting
- Reset per request or on-demand

**Benefits:**
- Identify gaps in translation coverage during development
- Data-driven localization prioritization
- Production alerting on unexpected missing translations

**Testing:** Tracking accuracy, log output, session isolation

---

## Phase 5: Integration & Ecosystem

### Feature 5.1: Translation Service Integration (Future)

**Stretch goal:** API for integrating with translation services:

**Possible integrations:**
- **Crowdin** — Upload missing keys, download translated content
- **Weblate** — Collaborative translation management
- **OpenAI/Claude translation API** — Auto-translation with professional quality (paid)

**Tentative API:**
```python
from easycord import LocalizationManager
from easycord.i18n_providers import CrowdinIntegration

manager = LocalizationManager.from_directory("locales/")
crowdin = CrowdinIntegration(project_id="abc123", token=os.getenv("CROWDIN_TOKEN"))

# Sync missing keys to Crowdin
crowdin.upload_missing_keys(manager)

# Download translated content from Crowdin
new_translations = crowdin.download_translations()
manager.merge_translations(new_translations)
```

**Benefits:**
- Streamlined translator workflow
- Quality control via professional translation services
- Version control integration

---

### Feature 5.2: Community Localization Kit

**Stretch goal:** Toolkit for community contributions:

**Package includes:**
- Translation template (en.json with all available keys)
- Style guide (translation conventions, terminology)
- Format validation tool
- Crowdin/Weblate setup docs
- Translation status dashboard (GitHub Pages)

**Benefits:**
- Lower barrier for community translators
- Consistent quality across languages
- Visible progress tracking

---

## Implementation Timeline

| Phase | Effort | Priority | Target |
|-------|--------|----------|--------|
| 1.1 — File format support | 2 weeks | **P0** | Month 1 |
| 1.2 — Lazy loading | 1 week | P1 | Month 1 |
| 2.1 — Locale auto-detection | 1 week | **P0** | Month 2 |
| 2.2 — Guild language override | 1 week | P1 | Month 2 |
| 3.1 — ICU format | 2 weeks | P2 | Month 3 |
| 3.2 — Typed keys | 1 week | P2 | Month 3 |
| 4.1 — Coverage metrics | 1 week | **P0** | Month 2 |
| 4.2 — Missing key logging | 3 days | P1 | Month 2 |
| 5.1 — Service integration | TBD | P3 | Future |
| 5.2 — Community kit | TBD | P3 | Future |

**P0 = Critical for v4.4.0**  
**P1 = High value, nice to have**  
**P2 = Polish, future major**  
**P3 = Stretch goals**

---

## Success Criteria

### v4.4.0 Release Gate

- ✅ File format support working (JSON, YAML optional)
- ✅ Lazy loading implemented
- ✅ Locale auto-detection from Discord
- ✅ Coverage metrics available
- ✅ Missing key logging in DEBUG mode
- ✅ 100+ new tests (Phase 1-4 coverage)
- ✅ Migration guide from v4.3.1
- ✅ Documentation for all features
- ✅ Example bot using new localization features
- ✅ No breaking changes to existing i18n API

### Quality Gates

- **Test coverage:** 90%+ for new code
- **Performance:** Cold start <50ms overhead, lazy load <10ms
- **Memory:** <50% increase for multi-language bots
- **Backward compat:** All v4.3.1 code runs unchanged

---

## Open Questions

1. **ICU MessageFormat library choice?** (unicode-org/icu4j vs third-party)
2. **Lazy loader cache eviction policy?** (LRU size limit, TTL-based, both)
3. **Integration scope?** (Crowdin/Weblate in v4.4.0 or later?)
4. **Type stub generation tool** — as built-in utility or separate CLI?

---

## Stakeholder Feedback

- [ ] Architecture review (maintainers)
- [ ] Feature prioritization (community)
- [ ] Performance targets (ops)
- [ ] Translation service partnerships (if applicable)

---

## Related Issues & PRs

- v4.3.1: Localization auto-translator source priority fix
- v4.3: Localization infrastructure foundation
- PR #33: Original localization feature reference (archived)

---

## Appendix: v4.3.1 Foundation

v4.4.0 builds on solid v4.3.1 foundation:
- ✅ Core `LocalizationManager` (locale resolution, fallback chain)
- ✅ Auto-translator callback support with caching
- ✅ Embed timestamp helpers
- ✅ `Composer` localization methods
- ✅ Type checking support
- ✅ Comprehensive test coverage (117 tests passing)
- ✅ Production-ready and stable

No breaking changes planned. v4.4.0 extends, not replaces.
