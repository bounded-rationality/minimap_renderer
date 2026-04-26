# Changelog

## [Community Fork] — 2026-03-22

Initial community fork based on the original WoWs-Builder-Team/minimap_renderer project, last supported at WoWs 14.11.

### Added
- Support for WoWs 15.2 replay format
- Support for WoWs 15.3 replay format
- `scripts/extract_gameparams.py` — decoder for the new `%bin` GameParams format introduced in 15.3
- `scripts/generate_data.py` — generates `ships.json`, `projectiles.json`, `planes.json` from game installation
- `update_version.py` — single-command version updater
- `apply_patches.py` — applies all code patches to installed packages

### Fixed
- **Replay reader** (`replay_unpack/replay_reader.py`): Skip zero-size blocks in the 3-block replay format introduced in WoWs 15.x
- **Consumable tracking** (`battle_controller.py`): `onConsumableUsed` method signature changed in 15.2 — `consumableType` replaced by `consumableUsageParams` blob. Consumable ID now extracted from byte 1 of the blob.
- **Ribbon display** (`battle_controller.py`): Ribbons were being stored under `avatar.id` but renderer looks them up by `vehicle.shipId`. Fixed `_update_ribbons` to use `shipId`.
- **Abilities fallback** (`renderer/layers/ship.py`, `health.py`, `markers.py`): Ships not in the abilities database (new/event ships) now fail gracefully instead of crashing the render.
- **Consumable icon fallback** (`renderer/layers/ship.py`): Unknown consumable slot IDs now skipped instead of crashing.

### Changed
- Watermark removed from renders (this is a local PoC fork, not a redistribution of the software)
- Ship display names now sourced from the game's localization files (`global.mo`) instead of internal GameParams names
- Data generation updated to handle the new GameParams region-based structure in 15.3

### Known Issues
- `abilities.json` is not being regenerated from current game data — consumable icons for slot IDs 4, 6, 8 (new slots added after 14.11) will not display
- The `create_data.py` script from the original repo is not yet updated for 15.x GameParams format
