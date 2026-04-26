import json
from pathlib import Path
from renderer.render import RenderDual
from replay_parser import ReplayParser
from renderer.utils import LOGGER

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Render two replays from the same battle side by side (dual mode)."
    )
    parser.add_argument("--replay1", type=str, required=True, help="First replay file (green team)")
    parser.add_argument("--replay2", type=str, required=True, help="Second replay file (red team)")
    parser.add_argument("--green-tag", type=str, default=None, help="Label for green team (optional)")
    parser.add_argument("--red-tag", type=str, default=None, help="Label for red team (optional)")
    namespace = parser.parse_args()

    path1 = Path(namespace.replay1)
    path2 = Path(namespace.replay2)
    video_path = path1.parent.joinpath(f"{path1.stem}_dual.mp4")

    LOGGER.info("Parsing replay 1 (green)...")
    with open(namespace.replay1, "rb") as f:
        replay1_info = ReplayParser(
            f, strict=True, raw_data_output=False
        ).get_info()

    LOGGER.info("Parsing replay 2 (red)...")
    with open(namespace.replay2, "rb") as f:
        replay2_info = ReplayParser(
            f, strict=True, raw_data_output=False
        ).get_info()

    v1 = replay1_info['open']['clientVersionFromExe']
    v2 = replay2_info['open']['clientVersionFromExe']
    LOGGER.info(f"Replay 1 version: {v1}")
    LOGGER.info(f"Replay 2 version: {v2}")

    arena1 = replay1_info['hidden']['replay_data'].game_arena_id
    arena2 = replay2_info['hidden']['replay_data'].game_arena_id
    if arena1 != arena2:
        LOGGER.warning(
            f"Warning: Arena IDs don't match ({arena1} vs {arena2}). "
            "These replays may not be from the same battle."
        )

    LOGGER.info("Rendering dual replay...")
    renderer = RenderDual(
        green_replay_data=replay1_info["hidden"]["replay_data"],
        red_replay_data=replay2_info["hidden"]["replay_data"],
        green_tag=namespace.green_tag,
        red_tag=namespace.red_tag,
        use_tqdm=True,
    )
    renderer.start(str(video_path))
    LOGGER.info(f"The video file is at: {str(video_path)}")
    LOGGER.info("Done.")
