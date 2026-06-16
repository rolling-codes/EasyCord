# EasyCord v5.47.1 Release Notes

Patch release — test-suite cleanup only, no public API changes.

### Fixed

- `tests/test_server_stats.py`: the bare `except (asyncio.CancelledError, Exception): pass` around background-task teardown in `test_setup_creates_channels` now has an explanatory comment. It's load-bearing — cancelling the stats refresh loop and then `await`-ing it re-raises `CancelledError` at the await point, and this catches it:

```python
task = plugin._loops.get(guild_id)
if task:
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass  # task is being torn down for test cleanup; outcome is irrelevant
```

- `tests/test_word_filter.py`: removed an unused `ctx2` from `test_guilds_isolated` — the test only ever exercises `ctx1`; guild 2's isolation is verified by reading its config store directly, not through a second context.

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.47.1/easycord-5.47.1-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.47.1/easycord-5.47.1.tar.gz"
```
