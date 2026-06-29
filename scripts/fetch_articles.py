"""
fetch_articles.py
Fetches the latest note.com article for each Gaika team posted this week.
Uses note.com's public API to avoid JS-rendering issues.
Writes output/articles.json.
"""

import json
import time
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ── Config ─────────────────────────────────────────────────────────────────────
TEAMS = [
    "cool_parrot6215",
    "gaikafuru",
    "kiajobhunting",
    "gakusei_kangae",
    "masashi_uclab",
    "keylink_by_kk",
    "atsuya_044",
    "joyful_turtle486",
    "kanno_wmori",
    "saku03081",
    "re_0oji",
    "yuyu10y",
    "mtk____",
    "mafty_navueerin",
    "kyoichi_osaka",
    "toshiki_naka",
    "tomoro_0726",
    "lovely_rue455",
    "ionub",
    "legal_wren2006",
    "nasgor",
    "fast_crocus9353",
]

NOTE_API_CONTENTS = "https://note.com/api/v2/creators/{username}/contents?kind=note&page=1"
NOTE_API_ARTICLE  = "https://note.com/api/v2/notes/{key}"
NOTE_ARTICLE_URL  = "https://note.com/{username}/n/{key}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
}

JST = timezone(timedelta(hours=9))
OUTPUT = Path("output/articles.json")
DELAY  = 1.5   # seconds between requests — be polite to note.com


# ── Helpers ────────────────────────────────────────────────────────────────────

def week_start_jst() -> datetime:
    """Return 7 days ago from now (rolling 7-day window)."""
    return datetime.now(JST) - timedelta(days=7)


def parse_date(s: str) -> datetime | None:
    """Parse note.com publishAt strings (ISO 8601 variants)."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def get(url: str, label: str) -> dict | None:
    """GET JSON with basic error handling."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        print(f"  ✗ HTTP {e.response.status_code} — {label}", file=sys.stderr)
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e} — {label}", file=sys.stderr)
    return None


# ── Core logic ─────────────────────────────────────────────────────────────────

def fetch_team(username: str, cutoff: datetime) -> dict:
    """Return a structured dict for one team, with up to 2 recent articles.

    has_post is True if any of the 2 articles falls within the 7-day rolling
    window (cutoff). Both articles are always fetched regardless of date.
    """
    import re
    result = {
        "username": username,
        "profile_url": f"https://note.com/{username}",
        "has_post": False,
        "articles": [],
        "error": None,
    }

    # 1) Get the list of contents
    data = get(NOTE_API_CONTENTS.format(username=username), f"{username}/contents")
    if data is None:
        result["error"] = "Failed to fetch content list"
        return result

    contents = data.get("data", {}).get("contents", [])
    if not contents:
        result["error"] = "No articles found"
        return result

    # 2) Always take the 2 most recent articles (contents are newest-first)
    for item in contents[:2]:
        note_key  = item.get("key", "")
        published = parse_date(item.get("publishAt", ""))

        article = {
            "post_date":   item.get("publishAt"),
            "article_url": NOTE_ARTICLE_URL.format(username=username, key=note_key),
            "title":       item.get("name", ""),
            "body":        None,
            "error":       None,
        }

        # Mark has_post if this article is within the rolling 7-day window
        if published and published >= cutoff:
            result["has_post"] = True

        # 3) Fetch the full article body
        time.sleep(DELAY)
        article_data = get(NOTE_API_ARTICLE.format(key=note_key), f"{username}/{note_key}")
        if article_data:
            body = article_data.get("data", {}).get("body", "")
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s{2,}", " ", body).strip()
            article["body"] = body or "(本文を取得できませんでした)"
        else:
            article["body"] = "(本文を取得できませんでした)"
            article["error"] = "Article body fetch failed"

        result["articles"].append(article)

    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    cutoff = week_start_jst()
    print(f"Week cutoff (JST): {cutoff.isoformat()}")
    print(f"Fetching {len(TEAMS)} teams…\n")

    results = []
    for i, username in enumerate(TEAMS, 1):
        print(f"[{i:02d}/{len(TEAMS)}] {username}", end=" … ", flush=True)
        record = fetch_team(username, cutoff)
        status = "✓ post found" if record["has_post"] else "– no post this week"
        if record.get("error") and not record.get("articles"):
            status = f"✗ error: {record['error']}"
        print(status)
        results.append(record)
        time.sleep(DELAY)

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    posted = sum(1 for r in results if r["has_post"])
    print(f"\nDone. {posted}/{len(TEAMS)} teams posted this week.")
    print(f"Saved → {OUTPUT}")


if __name__ == "__main__":
    main()
