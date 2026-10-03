<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/dark_mode.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/light_mode.svg">
  <img alt="Terminal profile card for M. Davaajargal" src="assets/dark_mode.svg">
</picture>

## What this card shows

Everything inside the image is generated, not hand-typed. The card has two
sources and one updater:

| Piece | Made by | Refreshed by |
|---|---|---|
| ASCII portrait | `tools/make_ascii.py` or `tools/make_portrait.py` | only when you replace `me.jpg` |
| Layout, colours, columns | `tools/build_svg.py` | only when you edit `tools/build_svg.py` |
| Uptime, repos, stars, commits, followers, LOC | placeholder values in the SVG | `today.py`, daily via GitHub Actions |

Both themes come out of a single generator, so they cannot drift apart.

## Regenerating it yourself

```bash
pip install -r requirements.txt

# Replace the ASCII portrait with your photo (40x30 characters).
cp ~/path/to/me.jpg .
python3 tools/make_ascii.py me.jpg

# Rebuild both SVGs from the portrait plus the STATIC block.
python3 tools/build_svg.py

# Update the numbers using your real account.
USER_NAME=Siomai0-hi ACCESS_TOKEN=*** python3 today.py

# Check nothing overflowed or lost an id.
python3 tools/verify_svg.py
```

To preview the numbers without a token, `python3 today.py --mock` reads
`tools/mock_data.json`.

## Notes on the numbers

- **Commits** is the trailing-12-month total GitHub shows on your profile, so it
  matches what a visitor sees there.
- **LOC** is a rolling 52-week sum from `/stats/code_frequency`, netted as
  `additions - deletions`. GitHub has no all-time LOC figure, and this endpoint
  excludes forks so upstream code is not counted twice.
- **Stars** counts only repositories you own, not ones you contributed to.

<!--
Generated files. Edit the scripts, not these:
  assets/dark_mode.svg, assets/light_mode.svg, assets/ascii.txt
-->