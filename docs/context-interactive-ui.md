# Interactive UI

EasyCord's `Context` object exposes five methods for presenting interactive Discord UI elements — confirmation buttons, paginated messages, select menus, modals, and text prompts — without writing any `discord.ui` boilerplate.

All five methods are available on every `ctx` object inside a `@slash` command.

---

## `ctx.confirm()`

Show a Yes/No button prompt and wait for the user to click one.

```python
async def confirm(
    prompt: str,
    *,
    timeout: float = 30,
    yes_label: str = "Yes",
    no_label: str = "Cancel",
    ephemeral: bool = False,
) -> bool | None
```

Returns `True` (yes), `False` (no/cancel), or `None` (timed out without a click).

```python
@slash(description="Ban a member")
async def ban(self, ctx, member: discord.Member):
    confirmed = await ctx.confirm(
        f"Ban **{member.display_name}**? This cannot be undone.",
        timeout=30,
        ephemeral=True,
    )
    if confirmed is None:
        await ctx.respond("Timed out — no action taken.", ephemeral=True)
    elif confirmed:
        await ctx.ban(member)
        await ctx.respond(f"Banned {member.display_name}.", ephemeral=True)
    else:
        await ctx.respond("Cancelled.", ephemeral=True)
```

Always handle the `None` (timeout) case — users frequently abandon buttons.

---

## `ctx.paginate()`

Show a multi-page browsable message with ◀ / ▶ navigation buttons.

```python
async def paginate(
    pages: list[str | discord.Embed],
    *,
    timeout: float = 120,
    ephemeral: bool = False,
) -> None
```

`pages` may contain strings, `discord.Embed` objects, or a mix of both. The buttons disable automatically when the user reaches either end.

```python
@slash(description="Browse the leaderboard")
async def leaderboard(self, ctx):
    rows = await self.bot.db.fetch_leaderboard()
    pages = [
        "\n".join(f"{i+1}. {r['name']} — {r['score']}" for r in chunk)
        for chunk in [rows[i:i+10] for i in range(0, len(rows), 10)]
    ]
    await ctx.paginate(pages, ephemeral=True)
```

To use embeds:

```python
embeds = [discord.Embed(title=f"Page {i+1}", description=page) for i, page in enumerate(pages)]
await ctx.paginate(embeds)
```

---

## `ctx.choose()`

Show a select menu and return the value the user picks, or `None` on timeout.

```python
async def choose(
    prompt: str,
    options: list[str | dict],
    *,
    timeout: float = 60,
    placeholder: str = "Select an option",
    ephemeral: bool = False,
) -> str | None
```

Options can be plain strings or dicts with `label`, `value`, and optional `description`:

```python
@slash(description="Set your preferred language")
async def set_language(self, ctx):
    choice = await ctx.choose(
        "Choose your language:",
        [
            {"label": "English", "value": "en", "description": "English (US)"},
            {"label": "French", "value": "fr", "description": "Français"},
            {"label": "Japanese", "value": "ja", "description": "日本語"},
        ],
        ephemeral=True,
    )
    if choice is None:
        return  # timed out
    await self.bot.db.set(ctx.user.id, "locale", choice)
    await ctx.respond(f"Language set to `{choice}`.", ephemeral=True)
```

When `options` is a list of plain strings, the label and value are the same string.

---

## `ctx.prompt()`

Show a single-field modal and return what the user typed, or `None` if they dismiss it.

```python
async def prompt(
    label: str,
    *,
    placeholder: str | None = None,
    max_length: int | None = None,
    timeout: float = 660,
) -> str | None
```

```python
@slash(description="Set your bio")
async def set_bio(self, ctx):
    bio = await ctx.prompt(
        "Your bio",
        placeholder="Tell the server about yourself…",
        max_length=200,
    )
    if bio is None:
        return  # dismissed
    await self.bot.db.set(ctx.user.id, "bio", bio)
    await ctx.respond("Bio saved!", ephemeral=True)
```

`timeout` defaults to 660 seconds (11 minutes) — the maximum Discord allows for modal responses.

---

## `ctx.ask_form()`

Show a multi-field modal and return a dict mapping field names to submitted values, or `None` if dismissed.

```python
async def ask_form(
    title: str,
    **fields: dict,
) -> dict[str, str] | None
```

Each keyword argument becomes a text input field. The dict value accepts any `discord.ui.TextInput` kwargs: `label`, `placeholder`, `max_length`, `min_length`, `required`, and `style` (`"short"` or `"paragraph"`).

```python
@slash(description="Submit a bug report")
async def report(self, ctx):
    result = await ctx.ask_form(
        "Bug Report",
        title=dict(label="Title", max_length=100),
        description=dict(label="Description", style="paragraph", max_length=1000),
        steps=dict(label="Steps to reproduce", style="paragraph", required=False),
    )
    if result is None:
        return  # dismissed

    embed = discord.Embed(title=result["title"], description=result["description"])
    if result.get("steps"):
        embed.add_field(name="Steps", value=result["steps"])
    await ctx.respond("Report submitted. Thank you!", ephemeral=True)
    await ctx.send_to(BUG_CHANNEL_ID, embed=embed)
```

The returned dict keys match the keyword argument names (`"title"`, `"description"`, `"steps"` in the example above).

---

## Timeout behaviour

Every interactive UI method returns `None` when the user doesn't interact within the timeout window. The safe pattern is:

```python
result = await ctx.confirm("Are you sure?")
if result is None:
    await ctx.respond("Timed out.", ephemeral=True)
    return
if not result:
    await ctx.respond("Cancelled.", ephemeral=True)
    return
# proceed
```

---

## Ephemeral UI

All five methods accept `ephemeral=True` (except `ctx.prompt()` and `ctx.ask_form()`, which use modals — modals are always user-private). Use ephemeral for confirmations and forms to keep the channel tidy:

```python
confirmed = await ctx.confirm("Delete this message?", ephemeral=True)
```
