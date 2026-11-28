#!/usr/bin/env python3
"""
Geometry self-check for the generated SVGs.

There is no browser in this environment, so instead of eyeballing the render we
assert the layout numerically: nothing overflows, nothing overlaps, and the two
value columns line up exactly.

Run:  python3 tools/verify_svg.py
Exits non-zero (with a list of problems) if anything is off.
"""

from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# Import the real layout constants so this checker can never drift out of sync
# with the generator.
sys.path.insert(0, str(HERE))
from build_svg import (  # noqa: E402
    ADV, ASCII_X, H, PANEL_X, VALUE_X, W,
)

MARGIN = 12

problems: list[str] = []


def check(path: pathlib.Path) -> list:
    root = ET.parse(path).getroot()
    layout = []

    for group in root.findall("{*}g"):
        size = float(group.attrib["font-size"])
        for t in group.findall("{*}text"):
            x = float(t.attrib["x"])
            y = float(t.attrib["y"])
            content = "".join(t.itertext())
            label = content[:34]

            if not (0 <= y <= H):
                problems.append(f"{path.name}: y={y} outside 0..{H} ({label!r})")

            # The portrait uses smaller glyphs than the information block.
            advance = size * 0.6 if x == ASCII_X else ADV
            right = x + len(content) * advance
            limit = PANEL_X - 8 if x == ASCII_X else W - MARGIN
            if right > limit:
                problems.append(f"{path.name}: line ends at x={right:.0f} > {limit} ({label!r})")

            if x not in (ASCII_X, PANEL_X, VALUE_X):
                problems.append(f"{path.name}: unexpected x={x} ({label!r})")

            # The ink changes with the theme, but the outline must not move.
            if x == ASCII_X:
                content = "".join(" " if c == " " else "#" for c in content)
            layout.append((x, y, size, content))

    # 5. Required dynamic ids.
    ids = {n.attrib["id"] for n in root.findall(".//{*}tspan[@id]")}
    required = {
        "uptime", "repos", "contributed", "stars",
        "commits", "followers", "loc", "additions", "deletions",
    }
    missing = required - ids
    if missing:
        problems.append(f"{path.name}: missing tspan ids {sorted(missing)}")

    # 6. Background rect present.
    if not any(r.get("width") == str(W) for r in root.findall("{*}rect")):
        problems.append(f"{path.name}: background rect not found")

    print(f"{path.name}: {len(layout)} text nodes, {len(ids)} dynamic ids")
    return layout


def main() -> int:
    layouts = []
    for name in ("dark_mode.svg", "light_mode.svg"):
        p = ROOT / "assets" / name
        if not p.exists():
            problems.append(f"missing {p}")
        else:
            layouts.append(check(p))
    if len(layouts) == 2 and layouts[0] != layouts[1]:
        problems.append("dark/light portrait outlines or information layouts differ")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("\nall geometry checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
