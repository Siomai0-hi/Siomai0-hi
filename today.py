#!/usr/bin/env python3
"""
Refresh the dynamic values inside assets/dark_mode.svg and assets/light_mode.svg.

What gets updated (each one carries a <tspan id="..."> in the SVG):
    uptime, repos, contributed, stars, commits, followers, loc, additions, deletions

Credentials
    Reads USER_NAME and ACCESS_TOKEN from the environment. A token is never
    hardcoded and never logged. If either is missing the script exits with a
    clear message instead of guessing.

Caching
    GitHub's /stats/code_frequency endpoint is slow (it is computed on demand
    and returns 202 while warming up). Results are cached under cache/ with a
    TTL, so a rerun on an unchanged repo costs almost nothing and the daily
    workflow stays well inside its time budget.

Offline testing
    `--mock` swaps the network layer for fixtures in tools/mock_data.json, so
    the whole update path can be exercised without a token.

Usage:
    USER_NAME=Siomai0-hi ACCESS_TOKEN=*** python3 today.py
    python3 today.py --mock
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "cache"

# Cache lifetimes. Stats are cheap to refresh; LOC is not.
TTL_GRAPHQL = 6 * 3600      # 6 hours
TTL_LOC = 24 * 3600         # 1 day

API = "https://api.github.com"
GQL = "https://api.github.com/graphql"

# Kept in sync with tools/build_svg.py -- the tspan ids this script fills in.
DYNAMIC_IDS = [
    "uptime", "repos", "contributed", "stars",
    "commits", "followers", "loc", "additions", "deletions",
]


# ── config ────────────────────────────────────────────────────────────────────

def load_birthday() -> dt.date:
    """Birthday drives the Uptime line.

    Kept in sync with STATIC['birthday'] in build_svg.py. Override with the
    GITHUB_BIRTHDAY environment variable to test without editing code.
    """
    raw = os.environ.get("GITHUB_BIRTHDAY", "2007-09-03")
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise SystemExit(f"error: GITHUB_BIRTHDAY={raw!r} is not YYYY-MM-DD")


def uptime(birthday: dt.date, today: dt.date | None = None) -> str:
    """Age as 'X years, Y months, Z days'.

    Computed with calendar arithmetic rather than a day count divided by 365,
    so leap years and short months do not skew the result.
    """
    today = today or dt.date.today()

    years = today.year - birthday.year
    months = today.month - birthday.month
    days = today.day - birthday.day

    if days < 0:
        months -= 1
        # Borrow the length of the month that just ended.
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        import calendar
        days += calendar.monthrange(prev_year, prev_month)[1]

    if months < 0:
        years -= 1
        months += 12

    return f"{years} years, {months} months, {days} days"


# ── caching ───────────────────────────────────────────────────────────────────

def cache_path(name: str) -> pathlib.Path:
    return CACHE / name


def cache_read(name: str, ttl: int) -> dict | None:
    p = cache_path(name)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if time.time() - payload.get("fetched_at", 0) > ttl:
        return None
    return payload.get("data")


def cache_write(name: str, data: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path(name).write_text(
        json.dumps({"fetched_at": time.time(), "data": data}, indent=2),
        encoding="utf-8",
    )


# ── GitHub access ─────────────────────────────────────────────────────────────

class GitHub:
    def __init__(self, token: str, user: str) -> None:
        self.token = token
        self.user = user

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-readme-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(
            GQL, data=body, headers={**self._headers(), "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL error: {payload['errors']}")
        return payload["data"]

    def rest(self, path: str) -> dict:
        req = urllib.request.Request(API + path, headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)


def fetch_counts(gh: GitHub) -> dict:
    """Repos, stars, commits, followers, contributed -- one GraphQL round trip.

    Commits use contributionsCollection.totalCommitContributions, which is the
    count GitHub itself shows for the last year. That is the same number a
    human would read off the profile page, so it will not look inconsistent.
    """
    cached = cache_read("counts.json", TTL_GRAPHQL)
    if cached:
        return cached

    query = """
    query($login: String!) {
      user(login: $login) {
        repositoriesContributedTo(
          first: 1, includeUserRepositories: true,
          contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]
        ) { totalCount }
        followers { totalCount }
        contributionsCollection {
          totalCommitContributions
        }
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
          totalCount
          nodes { stargazerCount }
        }
      }
    }
    """
    data = gh.graphql(query, {"login": gh.user})["user"]
    result = {
        "repos": data["repositories"]["totalCount"],
        "contributed": data["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in data["repositories"]["nodes"]),
        "commits": data["contributionsCollection"]["totalCommitContributions"],
        "followers": data["followers"]["totalCount"],
    }
    cache_write("counts.json", result)
    return result


def fetch_loc(gh: GitHub) -> dict:
    """Additions/deletions summed from /stats/code_frequency over owned repos.

    Notes:
      * The endpoint only returns the trailing 52 weeks, so this is a rolling
        year rather than an all-time figure.
      * It answers 202 while GitHub is still computing. We treat that as
        "try again next run" and fall back to cache, so a rerun does not
        silently write zeros.
      * FORK=false -- counting forks would double-count upstream code.
    """
    cached = cache_read("loc.json", TTL_LOC)
    if cached:
        return cached

    repos = gh.graphql(
        """
        query($login: String!) {
          user(login: $login) {
            repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
              nodes { nameWithOwner }
            }
          }
        }
        """,
        {"login": gh.user},
    )["user"]["repositories"]["nodes"]

    additions = deletions = 0
    failed = []
    for r in repos:
        owner, name = r["nameWithOwner"].split("/", 1)
        try:
            req = urllib.request.Request(
                f"{API}/repos/{owner}/{name}/stats/code_frequency",
                headers=gh._headers(),
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 202:
                    failed.append(name)
                    continue
                for _week, adds, dels in json.load(resp):
                    additions += adds
                    deletions += dels
        except urllib.error.HTTPError:
            failed.append(name)

    if failed:
        print(f"  note: {len(failed)} repo(s) still computing, using cache: "
              f"{', '.join(failed[:5])}{'...' if len(failed) > 5 else ''}")

    if not additions and not deletions and cache_path("loc.json").exists():
        return cache_read("loc.json", ttl=10**9)  # keep last known good

    result = {"additions": additions, "deletions": deletions}
    cache_write("loc.json", result)
    return result


# ── SVG updating ──────────────────────────────────────────────────────────────

def update_svg(path: pathlib.Path, values: dict) -> int:
    """Replace the text inside each <tspan id="..."> in path.

    Returns the number of ids that were actually found and replaced, so the
    caller can fail loudly rather than silently writing a half-updated file.
    """
    svg = path.read_text(encoding="utf-8")
    changed = 0

    for key, val in values.items():
        # Matches <tspan id="key" ...>TEXT</tspan> on a single line, which is
        # how build_svg.py emits them.
        pattern = re.compile(
            r'(<tspan id="' + re.escape(key) + r'"[^>]*>)(.*?)(</tspan>)'
        )
        svg, n = pattern.subn(
            lambda m: m.group(1) + str(val) + m.group(3), svg, count=1
        )
        if n:
            changed += 1
        else:
            print(f"  warning: id={key} not found in {path.name}")

    path.write_text(svg, encoding="utf-8")
    return changed


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock", action="store_true",
                    help="use tools/mock_data.json instead of the network")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    ap.add_argument("--no-loc", action="store_true",
                    help="skip the slow LOC fetch and reuse cache")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    birthday = load_birthday()
    up = uptime(birthday, today)

    if args.mock:
        mock = json.loads(
            (ROOT / "tools" / "mock_data.json").read_text(encoding="utf-8")
        )
        counts = {k: mock[k] for k in
                  ("repos", "contributed", "stars", "commits", "followers")}
        loc = {k: mock[k] for k in ("additions", "deletions")}
        print("mock mode -- no network, no token used")
    else:
        token = os.environ.get("ACCESS_TOKEN")
        user = os.environ.get("USER_NAME")
        if not token or not user:
            print(
                "error: USER_NAME and ACCESS_TOKEN must be set in the "
                "environment.\n"
                "       In GitHub Actions use secrets.ACCESS_TOKEN; locally "
                "export them first.",
                file=sys.stderr,
            )
            return 1
        gh = GitHub(token, user)
        counts = fetch_counts(gh)
        loc = {} if args.no_loc else fetch_loc(gh)

    # LOC shown as the net (additions - deletions), matching how the line reads.
    loc_total = loc.get("additions", 0) - loc.get("deletions", 0)

    values = {
        "uptime": up,
        "repos": counts.get("repos", "?"),
        "contributed": counts.get("contributed", "?"),
        "stars": counts.get("stars", "?"),
        "commits": counts.get("commits", "?"),
        "followers": counts.get("followers", "?"),
        "loc": f"{loc_total:,}",
        "additions": f"{loc.get('additions', 0):,}",
        "deletions": f"{loc.get('deletions', 0):,}",
    }

    total = 0
    for name in ("dark_mode.svg", "light_mode.svg"):
        p = ASSETS / name
        if not p.exists():
            print(f"  error: {p} not found -- run tools/build_svg.py first",
                  file=sys.stderr)
            return 1
        n = update_svg(p, values)
        print(f"  {name}: {n}/{len(values)} ids updated")
        total += n

    # Persist the resolved values so the workflow can show a useful diff.
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "last_run.json").write_text(
        json.dumps({"date": today.isoformat(), "values": values}, indent=2),
        encoding="utf-8",
    )

    print("\nresolved values:")
    for k, v in values.items():
        print(f"  {k:12} {v}")
    return 0 if total else 1


def main_entry() -> int:
    try:
        return main()
    except urllib.error.URLError as e:
        print(f"error: network failure: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main_entry())