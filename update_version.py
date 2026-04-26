#!/usr/bin/env python3
"""
update_version.py
Adds support for a new WoWs game version.

Usage:
    python update_version.py --game "D:\\Games\\Steam\\steamapps\\common\\World of Warships" --version 15.4

This script:
1. Finds the latest game build number
2. Extracts game scripts using wowsunpack.exe
3. Creates the replay_unpack version folder
4. Extracts and decodes GameParams.data
5. Generates ships.json, projectiles.json, planes.json
6. Extracts updated map images
7. Creates renderer version folder with data files
"""

import argparse
import glob
import json
import os
import pickle
import re
import shutil
import site
import struct
import subprocess
import sys
import zlib
from io import BytesIO


def find_package(name):
    for path in site.getsitepackages():
        candidate = os.path.join(path, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Could not find installed package: {name}")


def find_wowsunpack():
    """Find wowsunpack.exe in current directory or PATH."""
    candidates = ['wowsunpack.exe', './wowsunpack.exe', 'wowsunpack']
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    raise FileNotFoundError(
        "wowsunpack.exe not found. Download from https://github.com/landaire/wowsunpack/releases "
        "and place it in your working directory."
    )


def get_latest_build_number(game_path):
    """Find the highest build number in the game's bin folder."""
    bin_path = os.path.join(game_path, 'bin')
    builds = [d for d in os.listdir(bin_path) if d.isdigit()]
    if not builds:
        raise ValueError(f"No build folders found in {bin_path}")
    return max(builds, key=int)


def run_wowsunpack(wowsunpack, game_path, output, pattern):
    """Run wowsunpack.exe to extract files."""
    cmd = [wowsunpack, '-g', game_path, 'extract', '-o', output, pattern]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"  {result.stdout.strip()}")
    if result.returncode != 0:
        raise RuntimeError(f"wowsunpack failed: {result.stderr}")


class MockUnpickler(pickle.Unpickler):
    """Handles the custom GameParams pickle format with unknown classes."""
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (ImportError, AttributeError):
            return type(name, (), {'__init__': lambda self, *a, **kw: None})


def to_dict(obj):
    """Recursively convert custom objects to plain dicts."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            key = str(k) if not isinstance(k, (str, int, float, bool)) else k
            result[key] = to_dict(v)
        return result
    elif isinstance(obj, (list, tuple)):
        return [to_dict(i) for i in obj]
    elif hasattr(obj, '__dict__'):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    else:
        return obj


def decode_gameparams_bin(data_path, region='ASIA'):
    """Decode the %bin format GameParams used in WoWs 15.3+."""
    print(f"  Decoding %bin format GameParams (region={region})...")
    with open(data_path, 'rb') as f:
        raw = f.read()

    if raw[:4] == b'%bin':
        # New format: skip 4-byte header, reverse, decompress, unpickle
        data = raw[4:][::-1]
        data = zlib.decompress(data)
        result = MockUnpickler(BytesIO(data), encoding='latin1').load()
        if isinstance(result, dict) and region in result:
            return {k: to_dict(v) for k, v in result[region].items()}
        elif isinstance(result, dict):
            # Try first available region
            first_key = next(iter(result))
            print(f"  Warning: region '{region}' not found, using '{first_key}'")
            return {k: to_dict(v) for k, v in result[first_key].items()}
    else:
        raise ValueError(
            "Unexpected GameParams format. "
            "For versions before 15.3, use wowsunpack game-params command directly."
        )


def load_localization(mo_path):
    """Load display names from the game's .mo localization file."""
    with open(mo_path, 'rb') as f:
        data = f.read()
    magic = struct.unpack('<I', data[:4])[0]
    endian = '<' if magic == 0x950412de else '>'
    revision, count, offset_orig, offset_trans = struct.unpack(f'{endian}IIII', data[4:20])
    localization = {}
    for i in range(count):
        orig_len, orig_off = struct.unpack(f'{endian}II', data[offset_orig + i*8: offset_orig + i*8 + 8])
        trans_len, trans_off = struct.unpack(f'{endian}II', data[offset_trans + i*8: offset_trans + i*8 + 8])
        orig = data[orig_off:orig_off+orig_len].decode('utf-8', errors='ignore')
        trans = data[trans_off:trans_off+trans_len].decode('utf-8', errors='ignore')
        localization[orig] = trans
    return localization


def clean_name(name):
    name = re.sub(r'\s*\(<[^)]+\)', '', name)
    name = re.sub(r'\s*\(old\)', '', name)
    return name.strip()


def get_display_name(index, internal_name, localization):
    for key in [f'IDS_{index}_FULL', f'IDS_{index}']:
        if key in localization:
            return clean_name(localization[key])
    parts = internal_name.split('_')
    return ' '.join(parts[1:]) if len(parts) > 1 else internal_name


def generate_data_files(game_params, localization, output_dir):
    """Generate ships.json, projectiles.json, planes.json from GameParams."""
    os.makedirs(output_dir, exist_ok=True)
    # Create __init__.py files for Python package recognition
    open(os.path.join(output_dir, '__init__.py'), 'w').close()
    parent = os.path.dirname(output_dir)
    if not os.path.exists(os.path.join(parent, '__init__.py')):
        open(os.path.join(parent, '__init__.py'), 'w').close()

    ships = {}
    projectiles = {}
    planes = {}

    for key, value in game_params.items():
        if not isinstance(value, dict):
            continue
        type_info = value.get('typeinfo', {})
        if not isinstance(type_info, dict):
            continue
        t = type_info.get('type')

        if t == 'Ship':
            species = type_info.get('species', '')
            if species == 'Auxiliary':
                continue
            ship_id = value.get('id')
            if ship_id is None:
                continue
            index = value.get('index', key)
            internal_name = value.get('name', key)
            display_name = get_display_name(index, internal_name, localization)

            components = {}
            for k, v in value.items():
                if not isinstance(v, dict):
                    continue
                comp = {}
                if 'maxDist' in v:
                    comp['maxDist'] = v['maxDist']
                if 'maxDistCoef' in v:
                    comp['maxDistCoef'] = v['maxDistCoef']
                if 'ammoList' in v:
                    comp['ammo_list'] = v['ammoList']
                if comp:
                    components[k] = comp

            hulls = {}
            upgrade_info = value.get('ShipUpgradeInfo', {})
            if isinstance(upgrade_info, dict):
                for comp_name, comp_data in upgrade_info.items():
                    if not isinstance(comp_data, dict):
                        continue
                    if comp_data.get('ucType') != '_Hull':
                        continue
                    hull_components = comp_data.get('components', {})
                    hull_list = hull_components.get('hull', []) if isinstance(hull_components, dict) else []
                    if not hull_list:
                        continue
                    hull_key = hull_list[0]
                    hull_data = value.get(hull_key, {})
                    if not hull_data:
                        continue
                    hull_params = game_params.get(comp_name, {})
                    hull_params_id = hull_params.get('id') if isinstance(hull_params, dict) else None
                    if hull_params_id is None:
                        continue
                    burn_nodes = len(hull_data.get('burnNodes', []))
                    flood_nodes = len(hull_data.get('floodNodes', []))
                    hulls[str(hull_params_id)] = [burn_nodes, flood_nodes]

            ships[str(ship_id)] = {
                'index': index, 'name': display_name, 'species': species,
                'level': value.get('level', 1), 'nation': type_info.get('nation', ''),
                'components': components, 'hulls': hulls,
            }

        elif t == 'Projectile':
            proj_id = value.get('id')
            if proj_id is None:
                continue
            species = type_info.get('species', '')
            ammo_type = value.get('ammoType', 'HE') if species == 'Artillery' else 'HE'
            projectiles[str(proj_id)] = ammo_type

        elif t == 'Aircraft':
            plane_id = value.get('id')
            if plane_id is None:
                continue
            species = type_info.get('species', '')
            type_map = {
                'Fighter': 'Fighter', 'TorpedoBomber': 'Bomber',
                'DiveBomber': 'Dive', 'SkipBomber': 'Dive',
                'RocketPlane': 'Bomber', 'Scout': 'Scout'
            }
            plane_type = type_map.get(species, 'Fighter')
            ammo_type = None
            if 'bombName' in value:
                ammo_type = 'HE'
            elif 'torpedoName' in value:
                ammo_type = 'torpedo'
            elif 'depthChargeName' in value:
                ammo_type = 'depthcharge'
            planes[str(plane_id)] = [plane_type, ammo_type]

    print(f"  Ships: {len(ships)}, Projectiles: {len(projectiles)}, Planes: {len(planes)}")

    with open(os.path.join(output_dir, 'ships.json'), 'w', encoding='utf-8') as f:
        json.dump(ships, f, indent=2)
    with open(os.path.join(output_dir, 'projectiles.json'), 'w', encoding='utf-8') as f:
        json.dump(projectiles, f, indent=2)
    with open(os.path.join(output_dir, 'planes.json'), 'w', encoding='utf-8') as f:
        json.dump(planes, f, indent=2)


def version_to_folder(version_str):
    """Convert '15.3' to '15_3_0'."""
    parts = version_str.split('.')
    while len(parts) < 3:
        parts.append('0')
    return '_'.join(parts[:3])


def main():
    parser = argparse.ArgumentParser(description='Add support for a new WoWs game version')
    parser.add_argument('--game', required=True, help='Path to WoWs installation')
    parser.add_argument('--version', required=True, help='Game version e.g. 15.3 or 15.4')
    parser.add_argument('--region', default='ASIA', help='Server region for GameParams (ASIA/NA/EU). Default: ASIA')
    parser.add_argument('--workdir', default='.', help='Working directory for temp files. Default: current dir')
    args = parser.parse_args()

    game_path = args.game
    version_folder = version_to_folder(args.version)
    workdir = os.path.abspath(args.workdir)

    print(f"WoWs Minimap Renderer — Version Updater")
    print(f"Game path:      {game_path}")
    print(f"Version:        {args.version} ({version_folder})")
    print(f"Working dir:    {workdir}")
    print()

    # Find tools
    try:
        wowsunpack = find_wowsunpack()
        replay_unpack_pkg = find_package('replay_unpack')
        renderer_pkg = find_package('renderer')
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Find build number
    print("Step 1: Finding latest build number...")
    build_number = get_latest_build_number(game_path)
    print(f"  Build number: {build_number}")
    print()

    # Extract scripts
    scripts_dir = os.path.join(workdir, f'scripts_{version_folder}')
    print(f"Step 2: Extracting game scripts to {scripts_dir}...")
    run_wowsunpack(wowsunpack, game_path, scripts_dir, 'scripts/**')
    print()

    # Create replay_unpack version folder
    versions_base = os.path.join(replay_unpack_pkg, 'clients', 'wows', 'versions')
    new_ver_dir = os.path.join(versions_base, version_folder)
    print(f"Step 3: Creating version folder {new_ver_dir}...")

    # Find most recent existing version to copy Python files from
    existing_versions = sorted(
        [d for d in os.listdir(versions_base) if re.match(r'\d+_\d+_\d+', d)],
        key=lambda x: [int(i) for i in x.split('_')]
    )
    if not existing_versions:
        print("ERROR: No existing version folders found to copy from")
        sys.exit(1)
    prev_ver = existing_versions[-1]
    print(f"  Copying Python files from {prev_ver}...")

    os.makedirs(new_ver_dir, exist_ok=True)
    for fname in ['battle_controller.py', 'constants.py', 'players_info.py', '__init__.py']:
        src = os.path.join(versions_base, prev_ver, fname)
        dst = os.path.join(new_ver_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    scripts_dst = os.path.join(new_ver_dir, 'scripts')
    if os.path.exists(scripts_dst):
        shutil.rmtree(scripts_dst)
    shutil.copytree(os.path.join(scripts_dir, 'scripts'), scripts_dst)
    print(f"  Version folder created")
    print()

    # Extract GameParams
    gp_raw_dir = os.path.join(workdir, 'gp_raw')
    gp_json_path = os.path.join(workdir, f'GameParams_{version_folder}.json')
    print(f"Step 4: Extracting GameParams.data...")
    run_wowsunpack(wowsunpack, game_path, gp_raw_dir, 'content/GameParams.data')

    gp_data_path = os.path.join(gp_raw_dir, 'content', 'GameParams.data')
    with open(gp_data_path, 'rb') as f:
        header = f.read(4)

    if header == b'%bin':
        print(f"  Detected %bin format (WoWs 15.3+)")
        game_params = decode_gameparams_bin(gp_data_path, args.region)
    else:
        print(f"  Detected standard format, trying wowsunpack game-params...")
        cmd = [wowsunpack, '-g', game_path, 'game-params', gp_json_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr}")
            sys.exit(1)
        with open(gp_json_path, 'r', encoding='utf-8') as f:
            game_params = json.load(f)

    print(f"  Loaded {len(game_params)} GameParams entries")
    print()

    # Load localization
    mo_path = os.path.join(game_path, 'bin', build_number, 'res', 'texts', 'en', 'LC_MESSAGES', 'global.mo')
    print(f"Step 5: Loading localization from {mo_path}...")
    if not os.path.exists(mo_path):
        print(f"  WARNING: Localization file not found, ship names will use internal names")
        localization = {}
    else:
        localization = load_localization(mo_path)
        print(f"  Loaded {len(localization)} strings")
    print()

    # Generate data files
    renderer_ver_dir = os.path.join(renderer_pkg, 'versions', version_folder, 'resources')
    print(f"Step 6: Generating data files to {renderer_ver_dir}...")
    generate_data_files(game_params, localization, renderer_ver_dir)
    print()

    # Extract maps
    maps_dir = os.path.join(workdir, f'maps_{version_folder}')
    spaces_dst = os.path.join(renderer_pkg, 'resources', 'spaces')
    print(f"Step 7: Extracting map images...")
    run_wowsunpack(wowsunpack, game_path, maps_dir, 'spaces/**/minimap.png')
    run_wowsunpack(wowsunpack, game_path, maps_dir, 'spaces/**/minimap_water.png')
    maps_src = os.path.join(maps_dir, 'spaces')
    if os.path.exists(maps_src):
        for item in os.listdir(maps_src):
            src = os.path.join(maps_src, item)
            dst = os.path.join(spaces_dst, item)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        print(f"  Map images updated")
    print()

    print("=" * 60)
    print(f"SUCCESS: WoWs {args.version} support added!")
    print()
    print("Test with:")
    print("  python -m render --replay path\\to\\your.wowsreplay")
    print()
    print("If you see method signature errors, check PATCHES.md for")
    print("guidance on updating battle_controller.py.")
    print("=" * 60)


if __name__ == '__main__':
    main()
