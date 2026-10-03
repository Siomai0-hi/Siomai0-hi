#!/usr/bin/env python3
"""
Convert a photo (me.jpg) into ASCII art for the neofetch-style profile README.

Output: assets/ascii.txt  -- exactly COLS x ROWS characters.

Why Pillow instead of ascii-image-converter?
    ascii-image-converter is not installed on this machine, and the task allows
    either. Pillow is already a dependency, so using it keeps things simple.

Usage:
    python3 tools/make_ascii.py me.jpg
    python3 tools/make_ascii.py me.jpg --cols 40 --rows 30 --invert

If me.jpg does not exist yet, run `python3 tools/make_ascii.py --placeholder`
to write a neutral placeholder portrait so the build pipeline still works.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image, ImageOps

# Output shape. 40x30 matches the left panel of the SVG (see tools/build_svg.py).
COLS = 40
ROWS = 30

# ascii-image-converter style ramp: darkest -> lightest.
RAMP = "@%#*+=-:. "

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "assets" / "ascii.txt"


def to_ascii(image: Image.Image, cols: int, rows: int, invert: bool) -> str:
    """Downscale the image to cols x rows and map luminance onto RAMP.

    Character cells are about twice as tall as they are wide, so the row count
    is halved relative to the column count to avoid a squashed portrait.
    """
    # 1. Flatten to greyscale and auto-correct contrast so the face reads clearly.
    img = ImageOps.grayscale(image)
    img = ImageOps.autocontrast(img, cutoff=1)

    # 2. Match the target grid, compensating for character cell aspect ratio.
    target_w = cols
    target_h = max(1, rows)
    img = img.resize((target_w, target_h), Image.LANCZOS)

    pixels = list(img.getdata())

    # 3. Map each pixel to one character.
    n = len(RAMP)
    lines = []
    for y in range(target_h):
        row = pixels[y * target_w : (y + 1) * target_w]
        chars = []
        for p in row:
            idx = int(p * (n - 1) / 255)
            if invert:
                idx = (n - 1) - idx
            chars.append(RAMP[idx])
        lines.append("".join(chars))

    return "\n".join(lines)


def placeholder(cols: int, rows: int) -> str:
    """A neutral frame used until the real photo is dropped in.

    Deliberately plain: it should be obvious that it is not a real portrait,
    so nobody accidentally ships it.
    """
    lines = []
    for y in range(rows):
        # Top and bottom border rows, hollow box in between.
        if y in (0, rows - 1):
            lines.append("+" + "-" * (cols - 2) + "+")
        elif y == 2:
            lines.append("|" + " " * (cols - 2) + "|")
        else:
            # A simple head-and-shoulders silhouette so the box is not empty.
            cx, cy = (cols - 1) / 2, rows * 0.38
            head_r = cols * 0.15
            body_r = cols * 0.30
            row_chars = []
            for x in range(cols):
                d_head = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                shoulder_y = rows * 0.86
                in_body = y > shoulder_y and abs(x - cx) < body_r * (1 - (shoulder_y - y) / (rows * 0.5))
                row_chars.append("#" if (d_head < head_r or in_body) else " ")
            lines.append("|" + "".join(row_chars)[1:-1] + "|")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", nargs="?", help="path to me.jpg")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--rows", type=int, default=ROWS)
    ap.add_argument("--invert", action="store_true", help="flip light/dark mapping")
    ap.add_argument("--placeholder", action="store_true", help="write a placeholder instead")
    args = ap.parse_args()

    if args.placeholder or not args.image:
        art = placeholder(args.cols, args.rows)
        src = "placeholder"
    else:
        path = pathlib.Path(args.image)
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 1
        with Image.open(path) as im:
            art = to_ascii(im, args.cols, args.rows, args.invert)
        src = str(path)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(art + "\n", encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}  ({args.cols}x{args.rows})  from {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())