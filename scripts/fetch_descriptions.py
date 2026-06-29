"""Fetch og:description / meta description from note.com article pages."""
import urllib.request
import re
import time
import json
import sys

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ARTICLES = [
    ("cool_parrot6215",   "https://note.com/cool_parrot6215/n/n819109fa618b"),
    ("gaikafuru_1",       "https://note.com/gaikafuru/n/n892344d64461"),
    ("gaikafuru_2",       "https://note.com/gaikafuru/n/n84461d67b9fe"),
    ("kiajobhunting",     "https://note.com/kiajobhunting/n/n4772194a757d"),
    ("masashi_uclab_1",   "https://note.com/masashi_uclab/n/nbe2021745360"),
    ("masashi_uclab_2",   "https://note.com/masashi_uclab/n/ncf3f47e13d67"),
    ("atsuya_044",        "https://note.com/atsuya_044/n/nfeb87c5015bd"),
    ("joyful_turtle_1",   "https://note.com/joyful_turtle486/n/n66c7d4875384"),
    ("joyful_turtle_2",   "https://note.com/joyful_turtle486/n/n1dd91c13f7c4"),
    ("kanno_wmori_1",     "https://note.com/kanno_wmori/n/n3675f54aad22"),
    ("kanno_wmori_2",     "https://note.com/kanno_wmori/n/n5df7a9640f96"),
    ("re_0oji_1",         "https://note.com/re_0oji/n/n09cc155fe101"),
    ("re_0oji_2",         "https://note.com/re_0oji/n/ne8d14caf0390"),
    ("yuyu10y",           "https://note.com/yuyu10y/n/n040af6bd17ec"),
    ("mtk____",           "https://note.com/mtk____/n/n819eae9e4cbd"),
    ("mafty_navueerin",   "https://note.com/mafty_navueerin/n/nf157d34cfc67"),
    ("kyoichi_osaka_1",   "https://note.com/kyoichi_osaka/n/naed59c44e295"),
    ("kyoichi_osaka_2",   "https://note.com/kyoichi_osaka/n/nb316712c110c"),
    ("toshiki_naka",      "https://note.com/toshiki_naka/n/nbe269fbb7a93"),
    ("tomoro_0726",       "https://note.com/tomoro_0726/n/ncf94df4fe6b2"),
    ("lovely_rue455_1",   "https://note.com/lovely_rue455/n/n04e2d881beef"),
    ("ionub",             "https://note.com/ionub/n/n52a319c67395"),
    ("legal_wren2006",    "https://note.com/legal_wren2006/n/n3eda89e7ff08"),
    ("nasgor",            "https://note.com/nasgor/n/ne24d4ad0c6be"),
    ("fast_crocus9353",   "https://note.com/fast_crocus9353/n/n80215388ee61"),
    ("gakusei_kangae",    "https://note.com/gakusei_kangae/n/n207b725e211f"),
    ("keylink_week1",     "https://note.com/keylink_by_kk/n/n5fd14945faae"),
    ("keylink_week2",     "https://note.com/keylink_by_kk/n/n9d43021367e4"),
]


def fetch_desc(label, url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")

        og = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
        )
        jld = re.search(r'"description":\s*"([^"]{30,})"', html)

        parts = []
        if og:
            parts.append("OG: " + og.group(1)[:600])
        if jld:
            parts.append("JLD: " + jld.group(1)[:800])
        result = " | ".join(parts) if parts else "(no description found)"
        return {"label": label, "url": url, "text": result}
    except Exception as e:
        return {"label": label, "url": url, "text": f"ERROR: {e}"}


results = []
for label, url in ARTICLES:
    r = fetch_desc(label, url)
    print(f"[{label}] {r['text'][:120]}", flush=True)
    results.append(r)
    time.sleep(0.8)

with open("output/descriptions.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nSaved to output/descriptions.json")
