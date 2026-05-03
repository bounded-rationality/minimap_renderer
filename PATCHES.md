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

## replay_unpack/clients/wows/versions/15_X_0/battle_controller.py

### Patch 1: Fix _on_consumable_used signature

**Why:** In WoWs 15.2+, the `onConsumableUsed` method changed its signature to include `consumableUsageParams`. The original signature does not accept this keyword argument, causing a `TypeError` on every consumable use event.

**Change:**

```python
# BEFORE:
def _on_consumable_used(self, entity: Entity, consumableType, workTimeLeft):

# AFTER:
def _on_consumable_used(self, entity: Entity, consumableType=None, workTimeLeft=None, consumableUsageParams=None, **kwargs):
```

### Patch 2: Fix ribbon tracking ID

**Why:** Ribbons were being stored under `avatar.id` (the Avatar entity ID) but the renderer's `LayerRibbon` looks them up by `owner_vehicle_id` (the ship's entity ID). In 15.x these IDs differ, causing ribbons to never display.

**Change:**

```python
# BEFORE:
def update_ribbons(state):
    self._ribbons.setdefault(avatar.id, {})[state["ribbonId"]] = state["count"]

# AFTER:
def update_ribbons(state):
    self._ribbons.setdefault(self._owner.get("shipId", avatar.id), {})[state["ribbonId"]] = state["count"]
```

---

## renderer/layers/ship.py

### Patch 1: Graceful abilities lookup

**Why:** Ships added after 14.11 are not present in the bundled `abilities.json`. The original code crashed with `KeyError` when encountering these ships.

**Change:** `self._abilities[params_id]` → `self._abilities.get(params_id)`

### Patch 2: Guard consumable rendering for unknown ships

**Why:** When `abilities` is `None` (unknown ship), the code must skip consumable rendering entirely. The guard must be placed **before** the `try` block, not inside it, to avoid a `SyntaxError`.

**Change:**

```python
# BEFORE:
for aid, _ in ac.items():
    abilities = self._abilities.get(params_id)
    try:
        index = abilities["id_to_index"][aid]
    except KeyError:
        ...

# AFTER:
for aid, _ in ac.items():
    abilities = self._abilities.get(params_id)
    if abilities is None: continue
    try:
        index = abilities["id_to_index"][aid]
    except KeyError:
        ...
```

### Patch 3: Graceful consumable slot fallback

**Why:** New consumable slot IDs (4, 6, 8) introduced after 14.11 are not in `abilities.json`. The original code crashed when encountering them.

**Change:** Added a nested `try/except` to fall back to the clan abilities lookup, then skip if still not found.

---

## renderer/layers/health.py

### Patch: Graceful abilities fallback

**Why:** Same as ship.py — ships not in `abilities.json` crashed health bar rendering.

**Change:** `ability = self._abilities[...]` → `ability = self._abilities.get(...)` and guard `if ability is None: return` placed just before the burn/flood node section (which requires ability data), NOT before the health bar drawing (which does not).

---

## renderer/layers/markers.py

### Patch 1: Graceful abilities fallback

**Why:** Same as ship.py — ships not in `abilities.json` crashed marker rendering.

**Change:** `abilities = self._abilities[...]` → `abilities = self._abilities.get(...)` and `if abilities is None: continue`.

### Patch 2: Graceful slot ID fallback in sonar/radar circle drawing

**Why:** The markers layer draws sonar/radar circles for consumable slot IDs 11 (Hydrophone) and 13 (Radar). If a ship has these consumables active but they are not in `abilities.json`, the code crashed with `KeyError`.

**Change:**

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

**Why:** This is a community fork. The watermark referenced the original project's GitHub URL which is misleading given the significant modifications made.

**Change:** `_draw_header` method body replaced with `pass`.

---

## Version Folder Structure (per game version)

Each `replay_unpack/clients/wows/versions/15_X_0/` folder contains:

| File | Source | Notes |
|------|--------|-------|
| `__init__.py` | Copied from previous version | Imports BattleController |
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

The `abilities.json` file in `renderer/resources/` was generated by the original project's `create_data.py` script, which is not yet updated to work with the 15.x GameParams format.

**Impact:** Consumable icons for ships using slot IDs 4, 6, or 8 will not display. The render will not crash (due to graceful fallback), but the consumable indicator will be missing for those ships.

**Future fix:** Update `create_data.py` to work with the new GameParams format and the region-keyed structure introduced in 15.3.

### ship_bars images

Resolved. Ship bar silhouette images have been updated from the current game client. After future game updates, run `extract.py` and copy the new images across — this is covered in the "Keeping up to date" section of README.md.
