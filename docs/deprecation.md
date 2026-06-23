# Deprecation Helpers

Two decorators manage the lifecycle of EasyCord APIs and your own plugin functions.

```python
from easycord import deprecated, version_introduced
```

---

## `@deprecated`

Marks a function or method as deprecated. A `DeprecationWarning` is emitted at **call time** (not at import time), so users get an actionable warning when they actually invoke the old API.

```python
@deprecated("5.50.0", replacement="new_feature")
def old_feature(ctx):
    ...
```

Calling `old_feature(ctx)` emits:

```
DeprecationWarning: old_feature is deprecated since v5.50.0. Use new_feature instead.
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `version` | `str` | The version in which the API was deprecated |
| `replacement` | `str \| None` | Name of the replacement API (optional) |
| `reason` | `str \| None` | Additional explanation (optional) |

### With a reason

```python
@deprecated(
    "5.50.0",
    replacement="bot.event_bus.subscribe",
    reason="Direct plugin cross-calls create tight coupling",
)
def on_user_join(self, callback):
    ...
```

Warning message becomes:

```
DeprecationWarning: on_user_join is deprecated since v5.50.0.
Use bot.event_bus.subscribe instead. Direct plugin cross-calls create tight coupling
```

### Introspection

The decorator sets `__deprecated__` and `__replacement__` attributes on the wrapped function:

```python
assert old_feature.__deprecated__ == "5.50.0"
assert old_feature.__replacement__ == "new_feature"
```

---

## `@version_introduced`

Documents when a function was added. No runtime cost — the decorator sets `__version_introduced__` on the wrapped function and returns it unchanged.

```python
@version_introduced("5.50.0")
def new_feature(ctx):
    ...

assert new_feature.__version_introduced__ == "5.50.0"
```

Useful for generated API docs and introspection tooling.

---

## Suppressing warnings in tests

Use Python's standard `warnings` module:

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    old_feature(ctx)
```

Or configure pytest to filter them in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning:mypackage",
]
```
