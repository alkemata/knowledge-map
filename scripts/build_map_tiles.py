#!/usr/bin/env python3
"""Build a CRS.Simple WebP tile pyramid without loading it in the browser at once."""

import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image

TILE_SIZE = 256


def build_level(
    source: Image.Image,
    output: Path,
    zoom: int,
    width: int,
    height: int,
    quality: int,
) -> dict[str, int]:
    scale = 2**zoom
    level_width = max(1, round(width * scale))
    level_height = max(1, round(height * scale))
    resized = source.resize((level_width, level_height), Image.Resampling.LANCZOS)
    columns = math.ceil(level_width / TILE_SIZE)
    rows = math.ceil(level_height / TILE_SIZE)

    for column in range(columns):
        column_path = output / str(zoom) / str(column)
        column_path.mkdir(parents=True, exist_ok=True)
        for source_row in range(rows):
            left = column * TILE_SIZE
            top = source_row * TILE_SIZE
            crop = resized.crop((
                left,
                top,
                min(left + TILE_SIZE, level_width),
                min(top + TILE_SIZE, level_height),
            ))
            tile = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (221, 229, 211))
            tile.paste(crop, (0, 0))
            # CRS.Simple projects positive world Y into negative Leaflet tile rows.
            leaflet_row = source_row - rows
            tile.save(
                column_path / f"{leaflet_row}.webp",
                "WEBP",
                quality=quality,
                method=6,
            )
    resized.close()
    return {
        "zoom": zoom,
        "width": level_width,
        "height": level_height,
        "columns": columns,
        "rows": rows,
        "tiles": columns * rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Alkemata map tile pyramid")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=6144)
    parser.add_argument("--height", type=int, default=4096)
    parser.add_argument("--min-zoom", type=int, default=-4)
    parser.add_argument("--max-zoom", type=int, default=0)
    parser.add_argument("--quality", type=int, default=82)
    args = parser.parse_args()

    if args.width <= 0 or args.height <= 0:
        raise SystemExit("World dimensions must be positive")
    if args.min_zoom > args.max_zoom or args.max_zoom > 0:
        raise SystemExit("Expected min_zoom <= max_zoom <= 0")
    project_root = Path(__file__).resolve().parents[1]
    allowed_root = (project_root / "frontend" / "public").resolve()
    output = args.output.resolve()
    if output.name != "map-tiles" or allowed_root not in output.parents:
        raise SystemExit(f"Refusing to replace unsafe output directory: {output}")
    args.output = output
    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    with Image.open(args.source) as opened:
        source = opened.convert("RGB")
    levels = [
        build_level(
            source,
            args.output,
            zoom,
            args.width,
            args.height,
            args.quality,
        )
        for zoom in range(args.min_zoom, args.max_zoom + 1)
    ]
    source.close()

    metadata = {
        "schema_version": 1,
        "tile_size": TILE_SIZE,
        "format": "webp",
        "url_template": "/map-tiles/{z}/{x}/{y}.webp",
        "world_bounds": {
            "min_x": 0,
            "min_y": 0,
            "max_x": args.width,
            "max_y": args.height,
        },
        "min_zoom": args.min_zoom,
        "max_native_zoom": args.max_zoom,
        "max_zoom": 4,
        "levels": levels,
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Built {sum(level['tiles'] for level in levels)} tiles "
        f"for {args.width}x{args.height} world units."
    )


if __name__ == "__main__":
    main()
