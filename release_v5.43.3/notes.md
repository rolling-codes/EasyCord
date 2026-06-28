## EasyCord v5.43.3 - 2026-06-27

### Release Notice
v5.43.3 is a patch release on top of v5.43.2. It carries forward all of the
plugin creator (v5.43.0) and Phase 1 orchestration (v5.43.1/v5.43.2) features
unchanged, and adds targeted bug fixes. There are no breaking changes.

---

### Fixed

- **Economy balance race.** `EconomyPlugin` balance mutations now run under a
  per-guild lock. Because `store.load`/`store.save` are async, concurrent
  `/transfer`, `/daily`, and message-reward operations could interleave their
  load → modify → save sequences and lose updates. `/transfer` now applies both
  legs (debit sender, credit recipient) under one lock, so a sender can no
  longer be overdrawn and currency can no longer be lost between the two legs.
- **`/leaderboard` command collision.** Resolved a slash-command name collision
  between the economy and levels plugins; the economy leaderboard now registers
  as `/economy_leaderboard`.
- **Starboard dead code.** Removed unreachable code in `StarboardPlugin`.

### Verification

- `python scripts/check_release_metadata.py` — passed.
- `pytest tests/` — 606 passed.

### Release Assets

Downloads and documentation are available from:
- https://github.com/rolling-codes/EasyCord/releases/tag/v5.43.3
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.3/easycord-5.43.3-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.3/easycord-5.43.3.tar.gz

### Upgrade Notes

**From v5.43.2:**
- Direct upgrade; no breaking changes.
- The economy `/transfer` and balance paths are now concurrency-safe.
- If you referenced the economy leaderboard command, it is now
  `/economy_leaderboard`.

---

## Installation

```bash
# From PyPI (when released)
pip install easycord==5.43.3

# From GitHub wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.43.3/easycord-5.43.3-py3-none-any.whl"

# From source
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
git checkout v5.43.3
pip install -e .
```
