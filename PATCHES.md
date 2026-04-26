# Patch Documentation

This document describes every modification made to upstream packages and the reason for each change. This is essential context for future maintainers.

---

## replay_unpack/replay_reader.py

### Patch: Skip zero-size blocks in replay header

**Why:** WoWs 15.x introduced a 3-block replay format where the second block is empty (size=0). The original code called `json.loads(f.read(0))` which returns an empty string and throws `JSONDecodeError`.

**Change:** Added `if block_size == 0: continue` in the block-reading loop.

```python
# BEFORE:
for i in range(blocks_count - 1):
    block_size = struct.unpack("i", f.read(4))[0]
    data = json.loads(f.read(block_size))
    extra_data.append(data)

# AFTER:
for i in range(blocks_count - 1):
    block_size = struct.unpack("i", f.read(4))[0]
    if block_size == 0:
        continue
    data = json.loads(f.read(block_size))
    extra_data.append(data)
```

---

## replay_unpack/clients/wows/player.py

### Patch: Add debug logging to EntityMethod processing

**Why:** Added error logging to help diagnose packet parsing failures during development. Also adds the error without re-raising in strict mode for better diagnostics.

**Change:** Wrapped `entity.call_client_method` in try/except with logging.

---

## replay_unpack/clients/wows/versions/15_2_0/battle_controller.py

This file is copied from `14_11_0` with the following changes:

### Patch 1: Remove debug exit() call

**Why:** The original 14_11_0 `battle_controller.py` contained a debug line `if entity.id == 959830: exit()` in `_set_health`. This was a developer debug artifact that would crash the renderer if that specific entity ID appeared in a replay.

**Change:** Removed the two lines.

### Patch 2: Update `_on_consumable_used` signature

**Why:** In WoWs 15.2, the `onConsumableUsed` method on the `Vehicle` entity changed its signature. The `consumableType` integer argument was replaced by a `consumableUsageParams` binary blob. The consumable slot ID is now in byte 1 of this blob.

**Change:**
```python
# BEFORE (14_11_0 signature):
def _on_consumable_used(self, entity: Entity, consumableType, workTimeLeft):
    consumables = self._acc_consumables.setdefault(entity.id, [])
    consumables.append(
        Consumable(ship_id=entity.id, consumable_id=consumableType, duration=workTimeLeft)
    )

# AFTER (15_2_0 signature):
def _on_consumable_used(self, entity: Entity, consumableUsageParams, workTimeLeft):
    consumables = self._acc_consumables.setdefault(entity.id, [])
    consumable_id = consumableUsageParams[1] if isinstance(consumableUsageParams, (bytes, bytearray)) and len(consumableUsageParams) >= 2 else 0
    consumables.append(
        Consumable(ship_id=entity.id, consumable_id=consumable_id, duration=workTimeLeft)
    )
```

**Note:** The `consumableUsageParams` blob format is `[0x01, slot_id]` where `slot_id` matches the integer keys in `abilities.json`'s `id_to_index` mapping. Slot IDs 0-13 existed in 14.11; slots 4, 6, 8 were added later and are not yet in `abilities.json`.

### Patch 3: Fix ribbon tracking ID

**Why:** Ribbons were being stored under `avatar.id` (the Avatar entity ID) but the renderer's `LayerRibbon` looks them up by `owner_vehicle_id` (the ship's entity ID). In 15.x these IDs differ by 1.

**Change:**
```python
# BEFORE:
def update_ribbons(state):
    self._ribbons.setdefault(avatar.id, {})[state["ribbonId"]] = state["count"]

# AFTER:
def update_ribbons(state):
    vid = self._owner.get("shipId", avatar.id)
    self._ribbons.setdefault(vid, {})[state["ribbonId"]] = state["count"]
```

---

## renderer/layers/ship.py

### Patch 1: Graceful abilities fallback

**Why:** Ships added after 14.11 (new releases, event ships, etc.) are not present in the bundled `abilities.json`. The original code crashed with `KeyError` when encountering these ships.

**Change:** Changed `self._abilities[params_id]` to `self._abilities.get(params_id)` and added `if abilities is None: continue` to skip the consumable display for unknown ships.

### Patch 2: Graceful consumable slot fallback

**Why:** New consumable slot IDs (4, 6, 8) introduced after 14.11 are not in `abilities.json`. The original code crashed when encountering them.

**Change:** Added a nested try/except to skip unknown slot IDs rather than crashing.

---

## renderer/layers/health.py

### Patch: Graceful abilities fallback

**Why:** Same as ship.py — ships not in `abilities.json` crashed health bar rendering.

**Change:** `ability = self._abilities.get(...)` and guard `if ability is None: return` placed just before the burn/flood node section (which requires ability data), NOT before the health bar drawing (which does not).

---

## renderer/layers/markers.py

### Patch 1: Graceful abilities fallback

**Why:** Same as ship.py — ships not in `abilities.json` crashed marker rendering.

**Change:** `abilities = self._abilities.get(...)` and `if abilities is None: continue`.

### Patch 2: Graceful slot ID fallback in sonar/radar circle drawing

**Why:** The markers layer draws sonar/radar circles for consumable slot IDs 11 (Hydrophone) and 13 (Radar). If a ship has these consumables active but they are not present in that ship's `abilities.json` entry (e.g. a ship added after 14.11), the code crashed with `KeyError` on `id_to_index[aid]`.

**Change:** Added a guard before the `name` lookup to skip unknown slot IDs:

```python
# BEFORE:
for aid in {11, 13}.intersection(ac):
    name = f"{id_to_index[aid]}.{id_to_subtype[aid]}"

# AFTER:
for aid in {11, 13}.intersection(ac):
    if aid not in id_to_index or aid not in id_to_subtype:
        continue
    name = f"{id_to_index[aid]}.{id_to_subtype[aid]}"
```

---

## renderer/render.py

### Patch: Remove watermark

**Why:** This is a local proof-of-concept fork. The watermark referenced the original project's GitHub URL which is misleading given the code has been significantly modified.

**Change:** `_draw_header` method body replaced with `pass`.

---

## Version Folder Structure (per game version)

Each `replay_unpack/clients/wows/versions/15_X_0/` folder contains:

| File | Source | Notes |
|------|--------|-------|
| `__init__.py` | Copied from previous version | Imports `BattleController` |
| `battle_controller.py` | Copied from previous version | Update if method signatures changed |
| `constants.py` | Copied from previous version | Rarely changes |
| `players_info.py` | Copied from previous version | Rarely changes |
| `scripts/` | Extracted from game install | Must be updated every version |

The `scripts/` folder must be extracted fresh from the game installation using `wowsunpack.exe` for each game version. It contains:
- `entity_defs/` — XML definitions of all game entities and their method signatures
- `entity_defs/alias.xml` — Type aliases used throughout the entity definitions
- `component_defs/` — Component definitions

---

## Known Remaining Issues

### abilities.json not updated

The `abilities.json` file in `renderer/resources/` was generated by the original project's `create_data.py` script, which processed GameParams in a complex way to build per-ship consumable loadout data. This script is not yet updated to work with the 15.x GameParams format.

**Impact:** Consumable icons for ships using slot IDs 4, 6, or 8 will not display. The render will not crash (due to our graceful fallback), but the consumable indicator will be missing for those ships.

**Future fix:** Reverse-engineer `create_data.py` to work with the new GameParams format and the region-keyed structure introduced in 15.3.

### ship_bars images not updated

The health bar silhouette images in `renderer/resources/ship_bars/` are static assets bundled with the original project. Ships added after 14.11 will not have a silhouette image, causing health bars to display without the ship outline.
