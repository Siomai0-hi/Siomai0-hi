#!/usr/bin/env python3
"""
Procedural ASCII portrait for the neofetch card.

Used when me.jpg is not available yet. It is generated from a distance field
rather than hand-typed, so it stays smooth and can be re-tuned by changing a
couple of numbers instead of redrawing 30 lines of characters.

Run:  python3 tools/make_portrait.py
Writes assets/ascii.txt at exactly COLS x ROWS.
"""

from __future__ import annotations

import math
import pathlib

COLS, ROWS = 40, 30

# Dark -> light. Index 0 is the darkest.
RAMP = "@%#*+=-:. "
HAIR_RAMP = RAMP[:4]

# Terminal cells are about twice as tall as they are wide, so a shape that should
# look round on screen needs a cell-space radius roughly twice as wide as tall.
# All coordinates below are in cell space.
HEAD_CX, HEAD_CY = 20.0, 10.0
HEAD_RX, HEAD_RY = 13.0, 7.0

# Light direction (upper left).
LX, LY, LZ = -0.42, -0.58, 0.70

EYES = [(16.9, 10.1), (23.1, 10.1)]
MOUTH_Y, MOUTH_HALF = 13.7, 1.3
HAIR_Y = 8.6

NECK_TOP, NECK_HALF = 16.0, 3.1
SHOULDER_TOP = 19.0
SHOULDER_HALF_MAX = 19.0
SHOULDER_SKEW = 1.2


def clamp_idx(i: int) -> int:
    return max(0, min(len(RAMP) - 1, i))


def _shade(u: float, v: float, depth: float) -> str:
    """Sphere-ish normal inside the head, then a vertical falloff toward the jaw."""
    z = math.sqrt(max(0.0, 1.0 - u * u - v * v))
    lam = max(0.0, u * LX + v * LY + z * LZ)
    lit = 0.30 + 0.70 * lam
    lit -= 0.22 * max(0.0, depth)  # jaw drops into shadow
    return RAMP[clamp_idx(int(round((1.0 - lit) * (len(RAMP) - 1))))]


def build() -> str:
    grid = [[" "] * COLS for _ in range(ROWS)]

    for y in range(ROWS):
        fy = y + 0.5
        for x in range(COLS):
            fx = x + 0.5
            ch = None

            # Shoulders: a wide dome reaching the card edges, darker than skin.
            # A slight left offset breaks the symmetry so it reads as a person
            # rather than a diagram.
            if fy >= SHOULDER_TOP:
                t = (fy - SHOULDER_TOP) / (ROWS - SHOULDER_TOP)
                half = SHOULDER_HALF_MAX * min(1.0, t * 2.6)
                skew = SHOULDER_SKEW * (1.0 - t)
                if abs(fx - HEAD_CX - skew) <= half:
                    idx = int(round((1.0 - (0.34 - 0.20 * t)) * (len(RAMP) - 1)))
                    ch = RAMP[clamp_idx(idx)]

            # Neck, tucked between head and shoulders.
            if ch is None and NECK_TOP <= fy < SHOULDER_TOP + 1.0:
                if abs(fx - HEAD_CX) <= NECK_HALF:
                    idx = int(round((1.0 - 0.18) * (len(RAMP) - 1)))
                    ch = RAMP[clamp_idx(idx)]

            # Head, drawn last so it overlaps cleanly.
            u = (fx - HEAD_CX) / HEAD_RX
            v = (fy - HEAD_CY) / HEAD_RY
            if u * u + v * v <= 1.0:
                ch = _shade(u, v, v)
                if fy <= HAIR_Y:
                    ch = HAIR_RAMP[min(RAMP.index(ch), len(HAIR_RAMP) - 1)]
                elif MOUTH_Y <= fy <= MOUTH_Y + 0.9 and \
                        MOUTH_HALF <= abs(fx - HEAD_CX) <= MOUTH_HALF + 1.7:
                    ch = RAMP[clamp_idx(RAMP.index(ch) - 2)]

            # Eyes last of all so nothing overwrites them.
            if ch is not None and any(
                (fx - ex) ** 2 + (fy - ey) ** 2 <= 1.25 ** 2 for ex, ey in EYES
            ):
                ch = "@"

            if ch:
                grid[y][x] = ch

    return "\n".join("".join(r) for r in grid)


def main() -> int:
    art = build()
    out = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ascii.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(art + "\n", encoding="utf-8")

    print(art)
    rows = art.split("\n")
    print(f"\n{len(rows)} rows, widths {sorted({len(r) for r in rows})} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())