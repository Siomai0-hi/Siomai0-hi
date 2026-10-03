#!/usr/bin/env python3
"""
Build the neofetch-style profile SVGs (dark + light) from a single source of truth.

    assets/ascii.txt  +  STATIC below   ->   assets/dark_mode.svg
                                                assets/light_mode.svg

Why generate instead of hand-writing the SVG?
    The two themes must stay pixel-identical apart from colour. Generating both
    from one description makes that impossible to break by accident.

Column alignment
    Every key/value pair is positioned with explicit x coordinates (KEY_X and
    VALUE_X) rather than relying on spaces. That keeps the columns aligned even
    if the viewer falls back from Consolas to Courier New, whose glyph advance
    differs.

Dynamic values
    Every value that today.py refreshes is wrapped in <tspan id="...">. The ids
    are identical in both files because each SVG is a standalone document.
    If you add a new dynamic value, add its id here and in today.py.

Usage:
    python3 tools/build_svg.py
"""

from __future__ import annotations

import pathlib
from xml.sax.saxutils import escape

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ASCII_FILE = ROOT / "assets" / "ascii.txt"

# ── Static profile information ────────────────────────────────────────────────
# Everything here is hand-maintained. Anything that changes on its own (uptime,
# repo counts, stars, commits, followers, LOC) lives in today.py instead.
#
# TODO(owner): replace the TODO placeholders below with real values.
STATIC = {
    "name": "M. Davaajargal",
    "username": "Siomai0-hi",
    "birthday": "2007-09-03",  # YYYY-MM-DD -- drives the Uptime line
    "os": "Arch Linux",
    "host": "TODO",       # company
    "kernel": "TODO",     # job title
    "ide": "TODO",        # e.g. "VS Code · IntelliJ IDEA"
    # Comma-separated rather than " · " so the longest line fits inside 985px.
    "prog_langs": "Java, Python, JavaScript, C++",
    "comp_langs": "HTML, CSS, JSON, YAML",
    "real_langs": "English, Mongolian",
    "hobby_software": "TODO",
    "hobby_hardware": "TODO",
    "email_personal": "davkadavka617@gmail.com",
    "email_work": "TODO",
    "linkedin": "TODO",
    "discord": "TODO",
}

# ── Layout ────────────────────────────────────────────────────────────────────
# 985 x 530 total. 40x30 ASCII art on the left, neofetch info block on the right.
FONT_STACK = "Consolas, 'Liberation Mono', 'Courier New', monospace"
FONT_SIZE = 16
# Worst-case monospace advance (Courier New = 0.6em). Used to convert character
# columns into pixel x offsets so the two columns line up deterministically.
ADV = FONT_SIZE * 0.6  # 9.6px

W, H = 985, 530

ASCII_X = 16
ASCII_COLS = 40   # must match COLS in make_ascii.py
ASCII_ROWS = 30
ASCII_Y0 = 25
ASCII_LINE_H = 16  # 30 rows * 16 = 480px, ends at y=505

PANEL_X = 412
Y0 = 30
LINE_H = 19  # 25 lines * 19 = 475px, ends at y=505

# Character column where every value starts, measured from PANEL_X.
VALUE_COL = 25
VALUE_X = PANEL_X + int(round(VALUE_COL * ADV))  # 412 + 250 = 662

# How many characters fit to the right of VALUE_X before hitting the edge.
VALUE_CHARS = int((W - VALUE_X - 12) // ADV)

DASH = "─"
DOT = "."

# ── Colour themes ─────────────────────────────────────────────────────────────
# Dark: the colours the task asked for.
# Light: the same roles, darkened so each one clears ~4.5:1 on white.
THEMES = {
    "dark": {
        "file": "dark_mode.svg",
        "bg": "#161b22",
        "key": "#ffa657",
        "value": "#a5d6ff",
        "muted": "#6e7681",
        "ascii": "#a5d6ff",
        "add": "#3fb950",
        "del": "#f85149",
        "term": "#c9d1d9",
    },
    "light": {
        "file": "light_mode.svg",
        "bg": "#ffffff",
        "key": "#a15c00",
        "value": "#0550ae",
        "muted": "#57606a",
        "ascii": "#0550ae",
        "add": "#1a7f37",
        "del": "#cf222e",
        "term": "#24292f",
    },
}


# ── Line construction helpers ─────────────────────────────────────────────────
# A "line" is (kind, runs) where kind is:
#   "kv"     -> two aligned columns: `Key:`+leader at PANEL_X, value at VALUE_X
#   "inline" -> one run of text starting at PANEL_X (headers, rules, stats)
#   "blank"  -> vertical spacing only
# runs are (colour_role, text, tspan_id):
#   colour_role -> one of: key value muted add del term
#   tspan_id    -> unique id for today.py, or None for static text

def norm(runs: list) -> list:
    """Allow (role, text) as a shorthand for (role, text, None).

    Keeps the line builders readable without letting a missing id blow up
    somewhere deep in the renderer.
    """
    out = []
    for r in runs:
        if len(r) >= 3:
            out.append((r[0], r[1], r[2]))
        elif len(r) == 2:
            out.append((r[0], r[1], None))
        else:
            raise ValueError(f"run needs (role, text) or (role, text, id): {r!r}")
    return out


def leader(key_text: str) -> list:
    """Dotted leader filling the gap between a key and the value column."""
    pad = VALUE_COL - len(key_text) - 1  # -1 for the ':'
    n = max(2, min(pad, 14))
    return [("muted", " " + DOT * n + " ", None)]


def kv(key: str, value: str, vid: str | None = None, vrole: str = "value") -> tuple:
    """A `Key:<dotted leader>value` line, both columns explicitly positioned."""
    return ("kv", [
        ("key", key + ":", None),
        *leader(key),
        (vrole, value, vid),
    ])


def rule(label: str, width_chars: int = 58) -> tuple:
    """A `- Section -------...` divider line."""
    head = f"- {label} "
    fill = max(3, width_chars - len(head))
    return ("inline", [("muted", "- "), ("key", label), ("muted", " " + DASH * fill)])


def header() -> tuple:
    handle = f"{STATIC['name']}@{STATIC['username']}"
    return ("inline", [
        ("key", handle),
        ("muted", " " + DASH * max(3, 58 - len(handle) - 1)),
    ])


def stats_repos() -> tuple:
    """`Repos: N {Contributed: N} | Stars: N` -- inline, no dotted leaders."""
    return ("inline", [
        ("key", "Repos: ", None),
        ("value", "", "repos"),
        ("muted", " {", None),
        ("key", "Contributed: ", None),
        ("value", "", "contributed"),
        ("muted", "} | ", None),
        ("key", "Stars: ", None),
        ("value", "", "stars"),
    ])


def stats_commits() -> tuple:
    return ("inline", [
        ("key", "Commits: ", None),
        ("value", "", "commits"),
        ("muted", " | ", None),
        ("key", "Followers: ", None),
        ("value", "", "followers"),
    ])


def stats_loc() -> tuple:
    """`Lines of Code on GitHub: 1,234 (+5,678/-9,012)` -- LOC is the net value
    (additions - deletions); additions and deletions are the raw sums."""
    return ("inline", [
        ("key", "Lines of Code on GitHub:", None),
        *leader("Lines of Code on GitHub"),
        ("value", "", "loc"),
        ("muted", "  (+", None),
        ("add", "", "additions"),
        ("muted", "/-", None),
        ("del", "", "deletions"),
        ("muted", ")", None),
    ])


def build_lines() -> list:
    """The full neofetch info block, in display order. Order matters here."""
    blank = ("blank", [])
    return [
        header(),
        blank,
        kv("OS", STATIC["os"]),
        kv("Uptime", "0 years, 0 months, 0 days", "uptime"),
        kv("Host", STATIC["host"]),
        kv("Kernel", STATIC["kernel"]),
        kv("IDE", STATIC["ide"]),
        blank,
        kv("Languages.Programming", STATIC["prog_langs"]),
        kv("Languages.Computer", STATIC["comp_langs"]),
        kv("Languages.Real", STATIC["real_langs"]),
        blank,
        kv("Hobbies.Software", STATIC["hobby_software"]),
        kv("Hobbies.Hardware", STATIC["hobby_hardware"]),
        blank,
        rule("Contact"),
        kv("Email.Personal", STATIC["email_personal"]),
        kv("Email.Work", STATIC["email_work"]),
        kv("LinkedIn", STATIC["linkedin"]),
        kv("Discord", STATIC["discord"]),
        blank,
        rule("GitHub Stats"),
        stats_repos(),
        stats_commits(),
        stats_loc(),
    ]


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_ascii(c: dict) -> str:
    """Left panel: the ASCII portrait, one <text> per row."""
    if not ASCII_FILE.exists():
        raise SystemExit(
            f"error: {ASCII_FILE} missing.\n"
            f"       Run: python3 tools/make_ascii.py me.jpg"
        )
    rows = ASCII_FILE.read_text(encoding="utf-8").rstrip("\n").split("\n")
    out = [
        f'  <g font-family="{FONT_STACK}" font-size="{FONT_SIZE}" '
        f'fill="{c["ascii"]}" xml:space="preserve">'
    ]
    for i, row in enumerate(rows):
        y = ASCII_Y0 + i * ASCII_LINE_H
        # xml:space="preserve" keeps the leading/trailing spaces that shape the
        # portrait. Without it the XML parser collapses them and the art skews.
        out.append(f'    <text x="{ASCII_X}" y="{y}">{escape(row)}</text>')
    out.append("  </g>")
    return "\n".join(out)


def render_panel(lines: list, c: dict) -> str:
    """Right panel: the info block, with each column pinned to an x offset."""
    out = [
        f'  <g font-family="{FONT_STACK}" font-size="{FONT_SIZE}" '
        f'fill="{c["value"]}" xml:space="preserve">'
    ]
    for i, (kind, runs) in enumerate(lines):
        if kind == "blank" or not runs:
            continue
        y = Y0 + i * LINE_H
        runs = norm(runs)

        if kind == "kv":
            # Key + dotted leader start at PANEL_X and flow naturally; the value
            # is pinned to VALUE_X so every value lines up in one column.
            out.append(
                f'    <text x="{PANEL_X}" y="{y}">'
                + spans(runs[:2], c)
                + "</text>"
            )
            out.append(
                f'    <text x="{VALUE_X}" y="{y}">'
                + spans(runs[2:], c)
                + "</text>"
            )
        else:  # "inline" -- a single flowing group, no second column.
            out.append(
                f'    <text x="{PANEL_X}" y="{y}">'
                + spans(runs, c)
                + "</text>"
            )
    out.append("  </g>")
    return "\n".join(out)


def spans(runs: list, c: dict) -> str:
    """Turn (role, text, id) runs into <tspan> elements."""
    out = []
    for role, text, vid in runs:
        if text == "" and vid:
            # Empty placeholder run that exists purely to carry an id.
            out.append(f'<tspan id="{vid}" fill="{c[role]}"> </tspan>')
            continue
        if not text:
            continue
        attrs = f' fill="{c[role]}"'
        if vid:
            attrs = f' id="{vid}"' + attrs
        out.append(f'<tspan{attrs}>{escape(text)}</tspan>')
    return "".join(out)


def render_svg(theme_name: str, lines: list, ascii_block: str) -> str:
    c = THEMES[theme_name]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" role="img"
     aria-label="Terminal profile card for {escape(STATIC['name'])}">
  <title>{escape(STATIC['name'])}@{escape(STATIC['username'])}</title>
  <rect width="{W}" height="{H}" rx="10" fill="{c['bg']}"/>
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="none"
        stroke="{c['muted']}" stroke-opacity="0.35"/>
{ascii_block}
{render_panel(lines, c)}
</svg>
"""


def main() -> int:
    lines = build_lines()
    ascii_block = render_ascii(THEMES["dark"])

    for name, theme in THEMES.items():
        out = ROOT / "assets" / theme["file"]
        out.write_text(render_svg(name, lines, ascii_block), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")

    # Overflow guard: no line may run past the right edge of the card.
    budget = int((W - PANEL_X - 12) // ADV)
    worst = max(
        (sum(len(t) for _, t, _ in norm(runs)), i)
        for i, (_, runs) in enumerate(lines) if runs
    )
    flag = "ok" if worst[0] <= budget else "OVERFLOW"
    print(f"widest line: {worst[0]} chars (budget {budget}) [{flag}]")
    if flag == "OVERFLOW":
        raise SystemExit(
            f"error: line {worst[1]} is {worst[0]} chars wide, budget is {budget}.\n"
            "       Shorten the value in STATIC, or raise W / lower FONT_SIZE."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())