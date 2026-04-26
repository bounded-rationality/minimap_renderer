#!/usr/bin/env python3
"""
generate_data.py
Generates ships.json, projectiles.json, and planes.json for a given
WoWs version from GameParams.json and the game's localization file.

Usage:
    python generate_data.py \
        --gameparams GameParams.json \
        --localization "path/to/global.mo" \
        --output "path/to/renderer/versions/15_3_0/resources"

The output directory will be created if it doesn't exist.
__init__.py files will be created to make it a valid Python package.
"""

import argparse
import json
import os
import re
import struct


def load_localization(mo_path):
    """
    Load display name strings from the game's compiled .mo localization file.
    Returns a dict of {key: translated_string}.
    """
    with open(mo_path, 'rb') as f:
        data = f.read()

    magic = struct.unpack('<I', data[:4])[0]
    if magic == 0x950412de:
        endian = '<'
    elif magic == 0xde120495:
        endian = '>'
    else:
        raise ValueError(f"Not a valid .mo file: {mo_path}")

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
    """Remove internal date suffixes and (old) markers from ship names."""
    name = re.sub(r'\s*\(<[^)]+\)', '', name)
    name = re.sub(r'\s*\(old\)', '', name)
    return name.strip()


def get_display_name(index, internal_name, localization):
    """
    Get the player-facing ship name from localization.
    Falls back to stripping the internal name prefix if not found.

    Internal names follow the pattern: XXXX###_DisplayName
    e.g. PASB729_Georgia -> Georgia
    """
    for key in [f'IDS_{index}_FULL', f'IDS_{index}']:
        if key in localization:
            return clean_name(localization[key])
    # Fallback: strip the internal code prefix
    parts = internal_name.split('_')
    return ' '.join(parts[1:]) if len(parts) > 1 else internal_name


def generate(game_params, localization, output_dir):
    """
    Process GameParams and generate the three JSON data files.

    ships.json format:
    {
        "<ship_id>": {
            "index": "PASB729",        # internal index code
            "name": "Georgia",          # display name
            "species": "Battleship",    # ship type
            "level": 9,                 # tier
            "nation": "USA",
            "components": {             # component data for range calculations
                "A_Artillery": {"maxDist": 22620.0, "ammo_list": [...]},
                "A_FireControl": {"maxDistCoef": 1.1}
            },
            "hulls": {                  # hull data for fire/flood nodes
                "<hull_params_id>": [4, 2]  # [burn_nodes, flood_nodes]
            }
        }
    }

    projectiles.json format:
    {"<proj_id>": "AP"}   # or "HE", "CS"

    planes.json format:
    {"<plane_id>": ["Bomber", "torpedo"]}   # [plane_type, ammo_type]
    """
    os.makedirs(output_dir, exist_ok=True)
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

        # ---- Ships ----
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

            # Build components dict from ship's component keys
            # Each component key (A_Artillery, B_FireControl, etc.) may contain
            # maxDist (gun range), maxDistCoef (fire control multiplier), ammoList
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

            # Build hulls dict from ShipUpgradeInfo
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
                    hull_key = hull_list[0]  # e.g. 'A_Hull'
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
                'index': index,
                'name': display_name,
                'species': species,
                'level': value.get('level', 1),
                'nation': type_info.get('nation', ''),
                'components': components,
                'hulls': hulls,
            }

        # ---- Projectiles (shells, torpedoes, bombs) ----
        elif t == 'Projectile':
            proj_id = value.get('id')
            if proj_id is None:
                continue
            species = type_info.get('species', '')
            # For artillery shells, use the ammoType field (AP/HE/CS)
            # For everything else, treat as HE for coloring purposes
            ammo_type = value.get('ammoType', 'HE') if species == 'Artillery' else 'HE'
            projectiles[str(proj_id)] = ammo_type

        # ---- Aircraft ----
        elif t == 'Aircraft':
            plane_id = value.get('id')
            if plane_id is None:
                continue
            species = type_info.get('species', '')
            type_map = {
                'Fighter': 'Fighter',
                'TorpedoBomber': 'Bomber',
                'DiveBomber': 'Dive',
                'SkipBomber': 'Dive',
                'RocketPlane': 'Bomber',
                'Scout': 'Scout',
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

    return ships, projectiles, planes


def main():
    parser = argparse.ArgumentParser(description='Generate renderer data files from GameParams')
    parser.add_argument('--gameparams', required=True, help='Path to GameParams.json')
    parser.add_argument('--localization', required=True, help='Path to global.mo localization file')
    parser.add_argument('--output', required=True, help='Output directory for data files')
    args = parser.parse_args()

    print(f"Loading GameParams from {args.gameparams}...")
    with open(args.gameparams, 'r', encoding='utf-8') as f:
        game_params = json.load(f)
    print(f"Loaded {len(game_params)} entries")

    print(f"Loading localization from {args.localization}...")
    if os.path.exists(args.localization):
        localization = load_localization(args.localization)
        print(f"Loaded {len(localization)} strings")
    else:
        print("WARNING: Localization file not found, using internal names")
        localization = {}

    print("Generating data files...")
    ships, projectiles, planes = generate(game_params, localization, args.output)
    print(f"Ships: {len(ships)}, Projectiles: {len(projectiles)}, Planes: {len(planes)}")

    with open(os.path.join(args.output, 'ships.json'), 'w', encoding='utf-8') as f:
        json.dump(ships, f, indent=2)
    with open(os.path.join(args.output, 'projectiles.json'), 'w', encoding='utf-8') as f:
        json.dump(projectiles, f, indent=2)
    with open(os.path.join(args.output, 'planes.json'), 'w', encoding='utf-8') as f:
        json.dump(planes, f, indent=2)

    print(f"Saved to {args.output}")


if __name__ == '__main__':
    main()
