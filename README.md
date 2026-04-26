# WoWs Minimap Renderer (Community Fork)

A community-maintained fork of [WoWs-Builder-Team/minimap_renderer](https://github.com/WoWs-Builder-Team/minimap_renderer), updated to support World of Warships 15.2 and beyond.

**Original authors:** @notyourfather and @Trackpad  
**This fork maintained by:** community contributors  
**Original repo:** https://github.com/WoWs-Builder-Team/minimap_renderer

> This fork was created because the original project was abandoned as of WoWs 14.11. All credit for the core rendering engine goes to the original authors. This fork is licensed under the same AGPL-3.0 license as the original.

---

## What This Does

Renders World of Warships `.wowsreplay` files into `.mp4` video files showing an animated minimap with ship positions, shots, torpedoes, planes, smoke, health bars, ribbons, chat, and more.

## What Changed From The Original

See [CHANGELOG.md](CHANGELOG.md) for a full list. The high-level changes are:

- Fixed replay file reader to handle the new 3-block format introduced in WoWs 15.x
- Added support for WoWs 15.2 and 15.3 game versions
- Fixed consumable tracking (new `consumableUsageParams` format in 15.2+)
- Fixed ribbon display (keyed by wrong ID in 15.2+)
- Made abilities lookups fail gracefully for ships missing from the database
- Added data generation scripts to regenerate ship/projectile/plane databases from the game installation
- Added a new GameParams decoder for the `%bin` format introduced in 15.3
- Removed the watermark (this is a local PoC fork, not a redistribution)

---

## Requirements

- **Python 3.10** (exactly — not 3.11, 3.12 or newer)
- **Git**
- **[wowsunpack.exe](https://github.com/landaire/wowsunpack/releases)** — place in your working directory
- A World of Warships installation (Steam or standalone)
- Windows 10/11

---

## First-Time Setup

### 1. Install Python 3.10

Download from https://www.python.org/downloads/release/python-31011/ — use the **Windows installer (64-bit)** and tick **"Add Python to PATH"** before installing.

Verify:
```powershell
py -3.10 --version
```

### 2. Install Git

Download from https://git-scm.com/download/win and install with defaults.

### 3. Create a working directory

```powershell
mkdir D:\MMR
cd D:\MMR
```

Place `wowsunpack.exe` in `D:\MMR\`.

### 4. Create a virtual environment

```powershell
py -3.10 -m venv venv
venv\Scripts\Activate.ps1
```

If you get a script execution error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 5. Install the renderer

```powershell
pip install langdetect hanzidentifier
pip install --upgrade --force-reinstall git+https://github.com/WoWs-Builder-Team/minimap_renderer.git
```

### 6. Apply patches

Copy all files from the `patches/` folder in this repo into `D:\MMR\`, then run:

```powershell
python apply_patches.py
```

This patches the installed packages in your venv to fix compatibility with 15.x replays.

### 7. Set up game data for the current version

See [UPDATE_GUIDE.md](UPDATE_GUIDE.md) for the full version update process. For first-time setup, run:

```powershell
python update_version.py --game "D:\Games\Steam\steamapps\common\World of Warships" --version 15.3
```

---

## Rendering a Replay

```powershell
cd D:\MMR
venv\Scripts\Activate.ps1
python -m render --replay path\to\your.wowsreplay
```

Output will be saved as an `.mp4` in the same directory.

---

## Updating For a New Game Version

When WoWs updates, run:

```powershell
python update_version.py --game "D:\Games\Steam\steamapps\common\World of Warships" --version 15.4
```

See [UPDATE_GUIDE.md](UPDATE_GUIDE.md) for details on what this does and how to troubleshoot if it fails.

---

## Architecture Overview

For a new session picking this up, here's how the system fits together:

```
.wowsreplay file
       │
       ▼
replay_unpack  ←── game scripts (entity_defs, alias.xml) per version
(packet parser)         extracted from game install via wowsunpack
       │
       ▼
battle_controller  ←── version-specific Python in versions/15_X_0/
(game state tracker)
       │
       ▼
renderer  ←── ships.json, projectiles.json, planes.json per version
(minimap drawing)       generated from GameParams.data via scripts/
       │
       ▼
    .mp4 file
```

### Key files and what they do

| File | Purpose |
|------|---------|
| `replay_unpack/replay_reader.py` | Reads and decrypts `.wowsreplay` files. Patched to skip empty blocks in 15.x format. |
| `replay_unpack/clients/wows/versions/15_X_0/` | Per-version folder. Contains `battle_controller.py` (game state), `scripts/` (entity definitions from game install). |
| `replay_unpack/clients/wows/versions/15_X_0/battle_controller.py` | Tracks game state from packets. Key changes: `_on_consumable_used` signature, `_update_ribbons` ID fix. |
| `renderer/layers/ship.py` | Draws ship icons. Patched for graceful abilities fallback. |
| `renderer/layers/health.py` | Draws health bars. Patched for graceful abilities fallback. |
| `renderer/layers/markers.py` | Draws sonar/radar circles. Patched for graceful abilities fallback. |
| `renderer/render.py` | Main orchestrator. Watermark removed. |
| `renderer/versions/15_X_0/resources/` | Per-version data: `ships.json`, `projectiles.json`, `planes.json`. |

### Why there's a version folder per game version

`replay_unpack` uses the game's internal entity definition files (`scripts/entity_defs/`) to understand how to parse binary packets. These change every version as Wargaming adds/modifies game mechanics. The `battle_controller.py` also sometimes needs updating if method signatures change.

### The GameParams problem (15.3+)

In 15.3, Wargaming changed `GameParams.data` from a standard pickle format to a custom `%bin` format (byte-reversed, zlib-compressed, then pickled with custom classes). The `scripts/extract_gameparams.py` script handles this automatically.

---

## Troubleshooting

**`version 15_X_0 is not supported`** — Run `update_version.py` for the new version.

**`KeyError: <ship_id>`** in rendering — The ship is missing from `ships.json`. Re-run `update_version.py`.

**`unpack requires a buffer of N bytes`** — A method signature changed in the new version. Check `battle_controller.py` and compare the relevant `.def` file with the previous version.

**`ModuleNotFoundError: No module named 'langdetect'`** — Run `pip install langdetect hanzidentifier`.

**`JSONDecodeError` reading replay** — The replay file may be from a newer version whose block format isn't supported. Run `update_version.py`.

---

## License

AGPL-3.0 — same as the original project. All modifications are open source.
