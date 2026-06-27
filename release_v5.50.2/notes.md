# EasyCord v5.50.2 Release Notes

Bugfix release. Corrects an off-by-one in the interaction component TTL boundary that let a just-expired component (`ttl=0`) resolve as active on coarse-resolution clocks.

---

## Fixed

### Interaction component TTL is now strict at the expiry instant

`InteractionRegistry._entry_active` considered an entry active while `expires_at >= now`. A component registered with `ttl=0` has `expires_at` equal to its registration time, so when it was resolved within the same clock tick the `>=` comparison reported it as still active and `resolve_component` returned it.

The boundary is now strict:

```python
# easycord/registry.py
return entry.expires_at is None or entry.expires_at > time.time()
```

A component is inactive **at and after** its expiry instant. This removes a platform-dependent flake: the off-by-one was masked on fine-grained clocks (Linux CI, ~1 µs `time.time()`) but reproduced on coarse-resolution clocks (Windows, ~15 ms), where registration and resolution fall in the same tick. The repo's own `tests/test_stress.py::TestInteractionRegistryStress::test_component_ttl_expires` now passes deterministically on every platform; the full suite is 1181 passing.

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.2/easycord-5.50.2-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.2/easycord-5.50.2.tar.gz"
```
