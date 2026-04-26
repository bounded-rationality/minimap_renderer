#!/usr/bin/env python3
"""
extract_gameparams.py
Decodes WoWs GameParams.data (both legacy pickle and new %bin format)
and saves as JSON.

Usage:
    python extract_gameparams.py --input path/to/GameParams.data --output GameParams.json [--region ASIA]

The %bin format was introduced in WoWs 15.3. It wraps data in a region-keyed
dict (ASIA, NA, EU, etc.). Use --region to select which region's data to extract.
"""

import argparse
import json
import os
import pickle
import zlib
from io import BytesIO


class MockUnpickler(pickle.Unpickler):
    """Handles custom pickle classes in GameParams without crashing."""
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (ImportError, AttributeError):
            return type(name, (), {'__init__': lambda self, *a, **kw: None})


def to_dict(obj):
    """Recursively convert custom GameParams objects to plain Python dicts."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            # JSON keys must be strings
            key = str(k) if not isinstance(k, (str, int, float, bool)) else k
            result[key] = to_dict(v)
        return result
    elif isinstance(obj, (list, tuple)):
        return [to_dict(i) for i in obj]
    elif hasattr(obj, '__dict__'):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    else:
        return obj


def decode(data_path, region='ASIA'):
    """
    Decode GameParams.data and return as a plain dict.

    Supports:
    - Legacy format (standard pickle, used up to ~15.2)
    - %bin format (custom format introduced in 15.3:
      4-byte '%bin' header, remaining bytes reversed, zlib compressed,
      then pickled with custom classes, wrapped in region dict)
    """
    with open(data_path, 'rb') as f:
        raw = f.read()

    header = raw[:4]

    if header == b'%bin':
        print(f"Detected %bin format (WoWs 15.3+)")
        data = raw[4:][::-1]
        data = zlib.decompress(data)
        result = MockUnpickler(BytesIO(data), encoding='latin1').load()

        if isinstance(result, dict):
            available_regions = list(result.keys())
            print(f"Available regions: {available_regions}")
            if region in result:
                print(f"Using region: {region}")
                gp_raw = result[region]
            else:
                fallback = available_regions[0]
                print(f"Warning: region '{region}' not found, using '{fallback}'")
                gp_raw = result[fallback]
        else:
            gp_raw = result

        return {k: to_dict(v) for k, v in gp_raw.items()}

    else:
        print(f"Detected legacy pickle format")
        try:
            result = MockUnpickler(BytesIO(raw), encoding='latin1').load()
            return {k: to_dict(v) for k, v in result.items()}
        except Exception as e:
            raise ValueError(
                f"Failed to decode GameParams: {e}\n"
                "If this is a newer version, the format may have changed again."
            )


def main():
    parser = argparse.ArgumentParser(description='Decode WoWs GameParams.data to JSON')
    parser.add_argument('--input', required=True, help='Path to GameParams.data')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--region', default='ASIA',
                        help='Region to extract for %bin format (ASIA/NA/EU). Default: ASIA')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        raise SystemExit(1)

    print(f"Decoding {args.input}...")
    game_params = decode(args.input, args.region)
    print(f"Decoded {len(game_params)} entries")

    print(f"Saving to {args.output}...")
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(game_params, f)
    print("Done")


if __name__ == '__main__':
    main()
