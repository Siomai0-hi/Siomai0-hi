#!/usr/bin/env python3
"""
Normalise assets/ascii.txt to the exact COLS x ROWS grid the SVG expects.

Why this exists
    ascii.txt can be edited by hand in a browser ASCII-art converter, which
    produces whatever size the source image happened to be -- e.g. 51x21.
    The card is laid out for a fixed 40x30 grid, so anything else either
    overflows the left panel or leaves a gap. This script refits the art to
    exactly 40x30 and nothing else: no redrawing, no re-shading, no judgement.

Strategy
    1. Trim fully blank border rows/columns so the art fills the frame.
    2. Crop or pad columns to COLS.
    3. Crop or pad rows to ROWS.
    4. Centre whatever was left over, so short art does not sit at the top.

The result is plain ASCII/Unicode text with no HTML escaping problems and no
dependency on Pillow, so it is safe to run inside the workflow.

Usage:
    python3 tools/fit_ascii.py            # rewrite assets/ascii.txt in place
    python3 tools/fit_ascii.py --check    # report size, change nothing
"""

from __future__ import annotations

import argparse
import pathlib
import sys

COLS, ROWS = 40, 30
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TARGET = ROOT / "assets" / "ascii.txt"


def trim(lines: list[str]) -> list[str]:
    """Drop fully blank rows and columns from the edges."""
    rows = [r for r in lines]
    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()
    if not rows:
        return []
    width = max(len(r) for r in rows)
    padded = [r.ljust(width) for r in rows]
    while padded and not padded[0].strip():
        padded.pop(0)
    while padded and not padded[-1].strip():
        padded.pop()

    start, end = 0, width
    while start < end and all(not r[start].strip() for r in padded):
        start += 1
    while end > start and all(not r[end - 1].strip() for r in padded):
        end -= 1
    return [r[start:end] for r in padded]


def refit(lines: list[str], cols: int, rows: int) -> list[str]:
    """Crop or centre-pad lines to exactly cols x rows."""
    art = trim(lines)
    if not art:
        return [" " * cols for _ in range(rows)]

    # Columns: take the middle if too wide, centre-pad if too narrow.
    w = max(len(r) for r in art)
    if w > cols:
        off = (w - cols) // 2
        art = [r[off:off + cols].ljust(cols) for r in art]
    else:
        pad = (cols - w) // 2
        art = [" " * pad + r.ljust(w) for r in art]

    # Rows: same idea.
    h = len(art)
    if h > rows:
        off = (h - rows) // 2
        art = art[off:off + rows]
    else:
        top = (rows - h) // 2
        art = [" " * cols for _ in range(top)] + art
        art += [" " * cols for _ in range(rows - len(art))]

    return [r.ljust(cols)[:cols] for r in art]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report the current size and exit without writing")
    args = ap.parse_args()

    if not TARGET.exists():
        print(f"error: {TARGET} not found", file=sys.stderr)
        return 1

    raw = TARGET.read_text(encoding="utf-8").rstrip("\n").split("\n")
    cur = (len(raw), max((len(r) for r in raw), default=0))

    if args.check:
        ok = cur == (ROWS, COLS)
        print(f"ascii.txt is {cur[0]}x{cur[1]}, want {ROWS}x{COLS} "
              f"[{'ok' if ok else 'needs refit'}]")
        return 0 if ok else 1

    art = refit(raw, COLS, ROWS)
    TARGET.write_text("\n".join(art) + "\n", encoding="utf-8")

    print(f"refit {cur[0]}x{cur[1]} -> {ROWS}x{COLS}  ({TARGET.relative_to(ROOT)})")
    print(art)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())