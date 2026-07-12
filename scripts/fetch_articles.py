"""
fetch_articles.py  —  Gaika Monitor article logger
===================================================
Maintains data/article_log.json as a persistent store.

Each run:
  1. Fetches the top 5 articles per team from the note.com API
  2. Adds any URL not already in the log (fetches body via __NUXT__)
  3. Leaves existing entries untouched (preserves analysis)

Usage:
    python scripts/fetch_articles.py

After this, run the analysis step (Claude), then generate_report.py.
"""

import json
import re
import sys
import time
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
NOTE_ARTICLE_URL  = "https://note.com/{username}/n/{key}"
ARTICLES_PER_TEAM = 5   # check top N from each team to catch anything new

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

JST     = timezone(timedelta(hours=9))
LOG     = Path("data/article_log.json")
DELAY   = 1.5


# ── Helpers ────────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(JST).isoformat()


def parse_date(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def week_ago() -> datetime:
    return datetime.now(JST) - timedelta(days=7)


def load_log() -> dict:
    if LOG.exists():
        return json.loads(LOG.read_text(encoding="utf-8"))
    return {"last_updated": now_iso(), "articles": {}}


def save_log(log: dict) -> None:
    LOG.parent.mkdir(exist_ok=True)
    log["last_updated"] = now_iso()
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def api_get(url: str, label: str) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        print(f"  HTTP {e.response.status_code} -- {label}", file=sys.stderr)
    except Exception as e:
        print(f"  {type(e).__name__}: {e} -- {label}", file=sys.stderr)
    return None


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    for ent, rep in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')]:
        s = s.replace(ent, rep)
    return re.sub(r"\s{2,}", " ", s).strip()


# Non-content images embedded on every note.com page (icons, logos, profile pics,
# banners) — excluded so `images` only holds article body screenshots/photos.
IMAGE_NOISE_PATTERNS = (
    "/poc-image/", "/profile_", "profile.png", "note-banner", "loading_",
)


def extract_images(html: str) -> list[str]:
    """
    Pull embedded content-image URLs (screenshots, photos) from the article HTML.
    Many participants post their actual balance only as an app screenshot, so the
    plain-text body alone can be misleading — these URLs let a later analysis pass
    go view the image directly instead of guessing the number from prose.
    """
    urls = re.findall(r'https://assets\.st-note\.com/[^"\\ ]+', html)
    seen, out = set(), []
    for u in urls:
        u = u.split("?")[0]
        if any(p in u for p in IMAGE_NOISE_PATTERNS):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def fetch_body(url: str) -> tuple[str, str, list[str]]:
    """
    Fetch article body from HTML via window.__NUXT__ string extraction.
    Returns (body_text, method, image_urls).
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return f"(fetch error: {e})", "error", []

    images = extract_images(html)

    # Find the window.__NUXT__ script tag
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    nuxt_script = next((s for s in scripts if "window.__NUXT__" in s), "")

    if nuxt_script:
        all_strings = re.findall(r'"((?:[^"\\]|\\.)*)"', nuxt_script)
        candidates = [s for s in all_strings if r"\u003C" in s and len(s) > 200]
        if candidates:
            raw = max(candidates, key=len)
            try:
                decoded = json.loads('"' + raw + '"')
            except Exception:
                decoded = raw
            body = strip_html(decoded)
            if len(body) > 100:
                return body, "nuxt_body", images

    # Fallback: og:description
    og = re.search(r'property="og:description"\s+content="([^"]+)"', html)
    if not og:
        og = re.search(r'content="([^"]+)"\s+property="og:description"', html)
    jld = re.search(r'"description":\s*"([^"]{80,})"', html)
    best = ""
    if og:
        best = og.group(1)
    if jld and len(jld.group(1)) > len(best):
        best = jld.group(1)
    if best:
        return best, "og_description", images

    return "(本文を取得できませんでした)", "none", images


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log = load_log()
    articles = log["articles"]
    cutoff = week_ago()

    print(f"Log loaded: {len(articles)} existing entries")
    print(f"Week cutoff (JST): {cutoff.isoformat()}")
    print(f"Checking {len(TEAMS)} teams (top {ARTICLES_PER_TEAM} each)...\n")

    total_new = 0
    for i, username in enumerate(TEAMS, 1):
        print(f"[{i:02d}/{len(TEAMS)}] {username}", end=" ... ", flush=True)

        data = api_get(NOTE_API_CONTENTS.format(username=username), f"{username}/contents")
        if not data:
            print("API error")
            continue

        contents = data.get("data", {}).get("contents", [])
        new_count = 0

        for item in contents[:ARTICLES_PER_TEAM]:
            key      = item.get("key", "")
            url      = NOTE_ARTICLE_URL.format(username=username, key=key)
            pub_date = item.get("publishAt")

            if url in articles:
                continue  # already logged

            # New article — fetch body
            time.sleep(DELAY)
            body, method, images = fetch_body(url)

            published = parse_date(pub_date or "")
            this_week = bool(published and published >= cutoff)

            articles[url] = {
                "url":        url,
                "username":   username,
                "title":      item.get("name", ""),
                "post_date":  pub_date,
                "this_week":  this_week,
                "body":       body,
                "body_method": method,
                "images":     images,  # content screenshots/photos — view these when
                                       # the body text doesn't state an exact balance
                "fetched_at": now_iso(),
                "relevant":   None,   # null = not yet determined
                "analyzed":   False,
                "analysis":   None,
            }
            new_count += 1
            total_new += 1

        existing = sum(1 for url, a in articles.items() if a["username"] == username)
        print(f"+{new_count} new  ({existing} total in log)")
        time.sleep(DELAY)

    save_log(log)

    unanalyzed = sum(1 for a in articles.values() if not a["analyzed"])
    print(f"\nDone. {total_new} new articles added.")
    print(f"Unanalyzed entries: {unanalyzed}")
    print(f"Log saved -> {LOG}  ({len(articles)} total entries)")


if __name__ == "__main__":
    main()
