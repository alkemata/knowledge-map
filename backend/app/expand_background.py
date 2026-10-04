"""Expand the demonstration world's illustrated background around existing notes."""

import argparse
import json
import os
import uuid
from pathlib import Path

from .database import new_session
from .models import KnowledgeMap
from .seed import NAMESPACE

OLD_BOUNDS = {"min_x": 0, "min_y": 0, "max_x": 6144, "max_y": 4096}
NEW_BOUNDS = {"min_x": -3798, "min_y": -2532, "max_x": 9942, "max_y": 6628}
IMAGE_URL = "/map-background-v2.png"


def expand(backup_file: Path) -> None:
    map_id = uuid.uuid5(NAMESPACE, "world")
    with new_session() as db:
        world = db.get(KnowledgeMap, map_id)
        if world is None:
            raise RuntimeError("The demonstration map was not found")
        if world.world_bounds == NEW_BOUNDS and world.tile_config.get("image_url") == IMAGE_URL:
            print("Five-times-larger background is already active")
            return
        if world.world_bounds != OLD_BOUNDS:
            raise RuntimeError("Map bounds differ from the expected original; no changes made")
        if backup_file.exists() or not backup_file.parent.is_dir():
            raise RuntimeError("Backup target must be a new file in an existing directory")
        previous = {
            "map_id": str(world.id),
            "world_bounds": world.world_bounds,
            "tile_config": world.tile_config,
            "default_camera": world.default_camera,
            "version": world.version,
        }
        old_umask = os.umask(0o077)
        try:
            backup_file.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
        finally:
            os.umask(old_umask)
        world.world_bounds = NEW_BOUNDS
        world.tile_config = {**world.tile_config, "image_url": IMAGE_URL}
        world.version += 1
        db.commit()
        old_area = (OLD_BOUNDS["max_x"] - OLD_BOUNDS["min_x"]) * (OLD_BOUNDS["max_y"] - OLD_BOUNDS["min_y"])
        new_area = (NEW_BOUNDS["max_x"] - NEW_BOUNDS["min_x"]) * (NEW_BOUNDS["max_y"] - NEW_BOUNDS["min_y"])
        print(f"Background expanded to {new_area / old_area:.3f} times the original area")
        print("Existing camera, placements, regions and relationships were not changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Explicitly expand the demonstration world")
    parser.add_argument("--backup-file", type=Path, required=True)
    args = parser.parse_args()
    if not args.demo:
        raise SystemExit("Refusing to alter the map without --demo")
    expand(args.backup_file)


if __name__ == "__main__":
    main()
