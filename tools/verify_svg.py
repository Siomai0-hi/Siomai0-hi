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
import xml.dom.minidom as minidom

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# Import the real layout constants so this checker can never drift out of sync
# with the generator.
sys.path.insert(0, str(HERE))
from build_svg import (  # noqa: E402
    ADV, ASCII_COLS, ASCII_X, H, PANEL_X, VALUE_X, W,
)

MARGIN = 12

problems: list[str] = []


def check(path: pathlib.Path) -> None:
    doc = minidom.parse(str(path))
    texts = doc.getElementsByTagName("text")

    for t in texts:
        x = float(t.getAttribute("x"))
        y = float(t.getAttribute("y"))
        content = "".join(
            n.firstChild.nodeValue if n.firstChild else ""
            for n in t.getElementsByTagName("tspan")
        )
        label = (content or t.firstChild.nodeValue if t.firstChild else "")[:34]

        # 1. Vertical bounds.
        if not (0 <= y <= H):
            problems.append(f"{path.name}: y={y} outside 0..{H} ({label!r})")

        # 2. Horizontal bounds, assuming Courier New (the widest likely fallback).
        right = x + len(content) * ADV
        if right > W - MARGIN:
            problems.append(
                f"{path.name}: line ends at x={right:.0f} > {W - MARGIN} ({label!r})"
            )

        # 3. The ASCII panel must not run into the info panel.
        if x == ASCII_X and len(content) == ASCII_COLS and right > PANEL_X - 8:
            problems.append(
                f"{path.name}: ASCII art ends at {right:.0f}, collides with panel at {PANEL_X}"
            )

        # 4. Only the two known columns may be used.
        if x not in (ASCII_X, PANEL_X, VALUE_X):
            problems.append(f"{path.name}: unexpected x={x} ({label!r})")

    # 5. Required dynamic ids.
    ids = {n.getAttribute("id") for n in doc.getElementsByTagName("tspan") if n.getAttribute("id")}
    required = {
        "uptime", "repos", "contributed", "stars",
        "commits", "followers", "loc", "additions", "deletions",
    }
    missing = required - ids
    if missing:
        problems.append(f"{path.name}: missing tspan ids {sorted(missing)}")

    # 6. Background rect present.
    rects = doc.getElementsByTagName("rect")
    if not any(r.getAttribute("width") == str(W) for r in rects):
        problems.append(f"{path.name}: background rect not found")

    print(f"{path.name}: {len(texts)} text nodes, {len(ids)} dynamic ids -> ok")


def main() -> int:
    for name in ("dark_mode.svg", "light_mode.svg"):
        p = ROOT / "assets" / name
        if not p.exists():
            problems.append(f"missing {p}")
        else:
            check(p)

    # The two files must differ only in colour. Strip every attribute that is
    # legitimately theme-dependent (fills, the border stroke, the <rect> tags)
    # and require the remaining structure to be byte-identical.
    import re
    strip = lambda s: [
        ln for ln in s.splitlines()
        if "fill=" not in ln and "<rect" not in ln and "stroke=" not in ln
    ]
    d = strip((ROOT / "assets" / "dark_mode.svg").read_text(encoding="utf-8"))
    l = strip((ROOT / "assets" / "light_mode.svg").read_text(encoding="utf-8"))
    if d != l:
        problems.append("dark/light layouts differ structurally (not just colour)")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("\nall geometry checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())