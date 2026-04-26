# Update Guide — Adding a New Game Version

When World of Warships updates, follow this guide to add support for the new version.

## Quick Method (Automated)

```powershell
cd D:\MMR
venv\Scripts\Activate.ps1
python update_version.py --game "D:\Games\Steam\steamapps\common\World of Warships" --version 15.4
```

This script handles all the steps below automatically. If it fails partway through, follow the manual steps.

---

## Manual Method

### Step 1: Find the new version number

Check your game's `bin` folder:
```powershell
ls "D:\Games\Steam\steamapps\common\World of Warships\bin" | Sort-Object Name | Select-Object -Last 3
```

The highest number is the current build (e.g. `12267945` for 15.3). The version string used internally is `15,3,0,12267945`.

### Step 2: Extract game scripts

```powershell
.\wowsunpack.exe -g "D:\Games\Steam\steamapps\common\World of Warships" extract -o "D:\MMR\scripts_new" "scripts/**"
```

### Step 3: Create the version folder

Replace `15_4_0` with the actual new version:

```powershell
$NEW_VER = "15_4_0"
$PREV_VER = "15_3_0"
$BASE = "D:\MMR\venv\Lib\site-packages\replay_unpack\clients\wows\versions"

mkdir "$BASE\$NEW_VER"
Copy-Item "$BASE\$PREV_VER\battle_controller.py" "$BASE\$NEW_VER\"
Copy-Item "$BASE\$PREV_VER\constants.py" "$BASE\$NEW_VER\"
Copy-Item "$BASE\$PREV_VER\players_info.py" "$BASE\$NEW_VER\"
Copy-Item "$BASE\$PREV_VER\__init__.py" "$BASE\$NEW_VER\"
Copy-Item -Recurse "D:\MMR\scripts_new\scripts" "$BASE\$NEW_VER\scripts"
```

### Step 4: Extract GameParams

For WoWs 15.3 and later, GameParams uses a new `%bin` format:

```powershell
.\wowsunpack.exe -g "D:\Games\Steam\steamapps\common\World of Warships" extract -o "D:\MMR\gp_raw" "content/GameParams.data"
python scripts\extract_gameparams.py --input "D:\MMR\gp_raw\content\GameParams.data" --output "D:\MMR\GameParams_new.json"
```

For WoWs versions before 15.3 (if needed for backfill):
```powershell
.\wowsunpack.exe -g "D:\Games\Steam\steamapps\common\World of Warships" game-params "D:\MMR\GameParams_new.json"
```

### Step 5: Generate data files

```powershell
$BUILD_NUM = "12267945"  # replace with actual build number
python scripts\generate_data.py `
    --gameparams "D:\MMR\GameParams_new.json" `
    --localization "D:\Games\Steam\steamapps\common\World of Warships\bin\$BUILD_NUM\res\texts\en\LC_MESSAGES\global.mo" `
    --output "D:\MMR\venv\Lib\site-packages\renderer\versions\$NEW_VER\resources"
```

### Step 6: Update map images

```powershell
.\wowsunpack.exe -g "D:\Games\Steam\steamapps\common\World of Warships" extract -o "D:\MMR\maps_new" "spaces/**/minimap.png" "spaces/**/minimap_water.png"
Copy-Item -Recurse -Force "D:\MMR\maps_new\spaces\*" "D:\MMR\venv\Lib\site-packages\renderer\resources\spaces\"
```

### Step 7: Test

```powershell
python -m render --replay path\to\recent.wowsreplay
```

---

## Troubleshooting Version Updates

### `version 15_X_0 is not supported`
The version folder wasn't created or the `__init__.py` is missing. Check:
```powershell
ls "D:\MMR\venv\Lib\site-packages\replay_unpack\clients\wows\versions\15_X_0"
```

### `PLANE_PATH is unknown` or similar alias errors
The new version removed or renamed a type in `alias.xml`. Check what changed:
```python
# compare alias.xml between old and new version
import re
old = open('versions/OLD/scripts/entity_defs/alias.xml').read()
new = open('versions/NEW/scripts/entity_defs/alias.xml').read()
# find tags in old but not new
```

### Method signature errors (e.g. `unexpected keyword argument`)
A method in `Avatar.def` or `Vehicle.def` changed its arguments. Compare the relevant `.def` file between versions and update `battle_controller.py` accordingly.

### `KeyError: <large number>` during rendering
A ship, projectile, or plane ID is missing from the data files. Re-run Step 5.

---

## Notes on the GameParams Format History

| Version | GameParams Format | Extraction Method |
|---------|------------------|-------------------|
| Up to ~14.x | Standard pickle | `wowsunpack game-params` |
| 15.0–15.2 | Standard pickle (JSON via wowsunpack) | `wowsunpack game-params` |
| 15.3+ | Custom `%bin` format (byte-reversed + zlib + pickle with custom classes + region-keyed) | `scripts/extract_gameparams.py` |

The 15.3 format wraps everything in a dict keyed by region (`ASIA`, `NA`, `EU`, etc.). Use `ASIA` for the Asia/Pacific server, `NA` for North America, `EU` for Europe.
