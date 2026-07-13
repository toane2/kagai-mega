"""
generate_report.py  —  Gaika Monitor HTML report
=================================================
Reads:
  data/article_log.json    — persistent article log (managed by fetch_articles.py + analysis)
  data/overrides.json      — manual corrections (edit_server.py writes the log directly;
                             this file remains for ad-hoc patches)
  data/team_profiles.json  — per-team tendency/thinking-process profiles

Writes:
  output/report.html

Design: the report is built for *reading opponents*, not archiving posts.
One leaderboard for standings, then one card per team carrying their
trading style, tendency (thinking process), what to watch for, current
holdings, and their latest move. Full article history lives in the log
and the edit server, not here.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import html as html_mod

import fx_rates

LOG       = Path("data/article_log.json")
OVERRIDES = Path("data/overrides.json")
PROFILES  = Path("data/team_profiles.json")
OUTPUT    = Path("output/report.html")

JST = timezone(timedelta(hours=9))
COMPETITION_START = datetime(2026, 6, 22, tzinfo=JST)
STARTING_CAPITAL = 100_000

TEAMS = [
    "cool_parrot6215", "gaikafuru", "kiajobhunting", "gakusei_kangae",
    "masashi_uclab", "keylink_by_kk", "atsuya_044", "joyful_turtle486",
    "kanno_wmori", "saku03081", "re_0oji", "yuyu10y", "mtk____",
    "mafty_navueerin", "kyoichi_osaka", "toshiki_naka", "tomoro_0726",
    "lovely_rue455", "ionub", "legal_wren2006", "nasgor", "fast_crocus9353",
    "suppera",
]

OWN_TEAM = "suppera"   # highlighted so our own position stands out

# Validated dark categorical palette (dataviz reference, ≥3:1 on #1a1a19).
# Fixed slot order by prominence in this competition; every chip also carries
# the currency code as text, so color never works alone.
CURRENCY_COLOR = {
    "USD": "#3987e5",   # blue
    "EUR": "#9085e9",   # violet
    "GBP": "#d55181",   # magenta
    "AUD": "#c98500",   # yellow
    "CHF": "#199e70",   # aqua
    "CAD": "#d95926",   # orange
    "NZD": "#008300",   # green
    "CNY": "#e66767",   # red
}
NEUTRAL_CURRENCY = "#898781"   # JPY cash + anything beyond the 8 slots

GOOD = "#0ca30c"
BAD  = "#d03b3b"


def cur_color(cur: str) -> str:
    return CURRENCY_COLOR.get((cur or "").upper(), NEUTRAL_CURRENCY)


def esc(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


def fmt_date(s) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).astimezone(JST).strftime("%m/%d")
    except Exception:
        return str(s)


def fmt_jpy(v) -> str:
    if v is None:
        return ""
    try:
        return f"{int(float(v)):,}"
    except Exception:
        return str(v)


# ── Balance history ────────────────────────────────────────────────────────────

def team_timeseries(articles: list) -> list[tuple[str, float]]:
    """Oldest->newest (post_date, total_jpy), one point per article that states
    a holdings breakdown."""
    pts = []
    for a in sorted(articles, key=lambda x: x.get("post_date") or ""):
        holdings = (a.get("analysis") or {}).get("holdings") or []
        total, seen = 0.0, False
        for h in holdings:
            v = h.get("amount_jpy")
            if v is not None:
                total += float(v)
                seen = True
        if seen:
            pts.append((a.get("post_date") or "", total))
    return pts


def latest_snapshot(articles: list) -> tuple[str | None, list | None]:
    for a in sorted(articles, key=lambda x: x.get("post_date") or "", reverse=True):
        holdings = (a.get("analysis") or {}).get("holdings") or []
        if any(h.get("amount_jpy") is not None for h in holdings):
            return a.get("post_date"), holdings
    return None, None


def mark_to_market(snapshot_date: str | None, holdings: list) -> float:
    """Re-value a self-reported snapshot at today's FX rates (a team's last
    article can be days old). Falls back per-currency to the reported figure
    when a rate is unavailable."""
    snap_date = (snapshot_date or "").split("T")[0] or None
    total = 0.0
    for h in holdings:
        amt = h.get("amount_jpy")
        if amt is None:
            continue
        amt = float(amt)
        cur = (h.get("currency") or "").upper()
        if cur in ("", "JPY"):
            total += amt
            continue
        r_then = fx_rates.get_rate(snap_date, cur)
        r_now = fx_rates.get_rate(None, cur)
        total += amt / r_then * r_now if (r_then and r_now) else amt
    return total


def sparkline_svg(values: list, w: int = 120, h: int = 32, good: bool = True) -> str:
    """2px muted line + status-colored endpoint dot and soft area fill."""
    pad = 4
    vals = values if len(values) > 1 else values * 2
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [h - pad - (v - lo) / span * (h - 2 * pad) for v in vals]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = line + f" L{xs[-1]:.1f},{h - pad:.1f} L{xs[0]:.1f},{h - pad:.1f} Z"
    color = GOOD if good else BAD
    return (
        f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="none" role="img" aria-label="残高推移">'
        f'<path d="{area}" fill="{color}" opacity="0.12" stroke="none"/>'
        f'<path d="{line}" fill="none" stroke="var(--muted)" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" fill="{color}" '
        f'stroke="var(--surface)" stroke-width="2"/></svg>'
    )


# ── Per-team state ─────────────────────────────────────────────────────────────

def team_state(uname: str, articles: list, profile: dict) -> dict:
    """Everything one card / leaderboard row needs."""
    pts = team_timeseries(articles)
    snap_date, snap_holdings = latest_snapshot(articles)
    reported = pts[-1][1] if pts else None
    current = mark_to_market(snap_date, snap_holdings) if snap_holdings else reported

    latest = None   # most recent article with an intent
    for a in sorted(articles, key=lambda x: x.get("post_date") or "", reverse=True):
        if (a.get("analysis") or {}).get("intent"):
            latest = a
            break

    last_trade = None
    last_trade_date = ""
    for a in articles:
        for t in (a.get("analysis") or {}).get("trades") or []:
            d = t.get("date") or (a.get("post_date") or "")[:10]
            if d >= last_trade_date:
                last_trade_date, last_trade = d, t

    n_trades = sum(len((a.get("analysis") or {}).get("trades") or []) for a in articles)

    now = datetime.now(JST)
    posted_this_week = any(
        a.get("post_date") and
        (now - datetime.fromisoformat(a["post_date"]).astimezone(JST)).days < 7
        for a in articles
    )

    return {
        "username": uname,
        "articles": articles,
        "profile": profile,
        "points": pts,
        # "current" is the article-stated figure — the number a reader can
        # verify against the team's own post. Today's-rate conversion is a
        # separate, clearly-labeled estimate so the report never appears to
        # contradict the source articles.
        "current": reported,
        "delta": (reported - STARTING_CAPITAL) if reported is not None else None,
        "mtm": current,
        "snap_date": snap_date,
        "reported": reported,
        "holdings": snap_holdings or [],
        "latest": latest,
        "last_trade": last_trade,
        "last_trade_date": last_trade_date,
        "n_trades": n_trades,
        "posted_this_week": posted_this_week,
    }


# ── HTML pieces ────────────────────────────────────────────────────────────────

def holdings_chips(holdings: list) -> str:
    if not holdings:
        return '<span class="muted">—</span>'
    order = sorted(holdings, key=lambda h: -(h.get("amount_jpy") or 0))
    chips = []
    for h in order:
        cur = (h.get("currency") or "?").upper()
        amt = h.get("amount_jpy")
        if not amt and cur != "JPY":
            continue
        c = cur_color(cur)
        amt_str = f'<span class="chip-amt">{fmt_jpy(amt)}</span>' if amt is not None else ""
        chips.append(
            f'<span class="chip" style="--c:{c}"><span class="chip-dot"></span>{esc(cur)} {amt_str}</span>'
        )
    return "".join(chips) or '<span class="muted">—</span>'


def alloc_bar(holdings: list) -> str:
    """One thin stacked bar showing the current allocation, 2px gaps between
    segments (spacer rule). Labels live in the chips right above it."""
    vals = [(h.get("currency", "?").upper(), float(h.get("amount_jpy") or 0))
            for h in holdings if h.get("amount_jpy")]
    total = sum(v for _, v in vals)
    if total <= 0:
        return ""
    vals.sort(key=lambda x: -x[1])
    segs = "".join(
        f'<div class="alloc-seg" style="flex:{v / total:.4f};background:{cur_color(c)}" title="{esc(c)} {fmt_jpy(v)}円"></div>'
        for c, v in vals
    )
    return f'<div class="alloc">{segs}</div>'


def leaderboard_rows(states: list) -> str:
    ranked = [s for s in states if s["current"] is not None]
    ranked.sort(key=lambda s: -s["current"])
    max_abs = max((abs(s["delta"]) for s in ranked), default=1) or 1
    rows = []
    for rank, s in enumerate(ranked, 1):
        gain = s["delta"] >= 0
        pct = min(abs(s["delta"]) / max_abs * 50, 50)
        delta_str = f"+{s['delta']:,.0f}" if gain else f"{s['delta']:,.0f}"
        spark = (sparkline_svg([v for _, v in s["points"]], good=gain)
                 if len(s["points"]) > 1 else '<span class="muted" style="font-size:10px">—</span>')
        hist = " → ".join(f"{fmt_date(d)}: {v:,.0f}円" for d, v in s["points"])
        if s["mtm"] is not None and abs(s["mtm"] - s["reported"]) >= 1:
            hist += f"（参考: 本日レート換算 ≈{s['mtm']:,.0f}円）"
        style_tag = esc((s["profile"] or {}).get("style", ""))
        own = " own" if s["username"] == OWN_TEAM else ""
        own_badge = '<span class="own-badge">自チーム</span>' if own else ""
        rows.append(
            f'<div class="lb-row{own}" title="{esc(hist)}" onclick="jumpTo(\'{esc(s["username"])}\')">'
            f'<div class="lb-rank">{rank}</div>'
            f'<div class="lb-team">@{esc(s["username"])}{own_badge}'
            f'{f"<span class=lb-style>{style_tag}</span>" if style_tag else ""}</div>'
            f'<div class="lb-spark">{spark}</div>'
            f'<div class="lb-total">{s["current"]:,.0f}<span class="unit">円</span>'
            f'<div class="lb-asof">{fmt_date(s["snap_date"])}時点</div></div>'
            f'<div class="lb-track"><div class="lb-zero"></div>'
            f'<div class="lb-bar {"pos" if gain else "neg"}" style="width:{pct:.1f}%"></div></div>'
            f'<div class="lb-delta {"pos" if gain else "neg"}">{delta_str}円</div>'
            f'</div>'
        )
    return "\n".join(rows)


def team_card(rank: int | None, s: dict) -> str:
    p = s["profile"] or {}
    uname = s["username"]
    gain = (s["delta"] or 0) >= 0
    if s["current"] is not None:
        balance = (
            f'<div class="bal"><span class="bal-num">{s["current"]:,.0f}</span><span class="unit">円</span>'
            f'<span class="bal-asof">({fmt_date(s["snap_date"])}時点)</span>'
            f'<span class="bal-delta {"pos" if gain else "neg"}">'
            f'{"+" if gain else ""}{s["delta"]:,.0f}円</span></div>'
        )
    else:
        balance = '<div class="bal muted">残高データなし</div>'

    # Foreign-currency holders keep gaining/losing after their last post;
    # surface that as a labeled estimate, never as the headline number.
    mtm_html = ""
    if s["mtm"] is not None and s["reported"] is not None and abs(s["mtm"] - s["reported"]) >= 1:
        drift = s["mtm"] - s["reported"]
        mtm_html = (
            f'<div class="mtm">記事後のレート変動込みの参考値: ≈{s["mtm"]:,.0f}円 '
            f'<span class="{"pos" if drift >= 0 else "neg"}">({"+" if drift >= 0 else ""}{drift:,.0f}円)</span></div>'
        )

    latest = s["latest"]
    if latest:
        move = (
            f'<div class="latest"><span class="latest-date">{fmt_date(latest.get("post_date"))}</span> '
            f'<a href="{esc(latest.get("url"))}" target="_blank" class="latest-link">'
            f'{esc((latest.get("analysis") or {}).get("intent") or "")}</a></div>'
        )
    else:
        move = '<div class="latest muted">投稿からの情報なし</div>'

    t = s["last_trade"]
    if t:
        fc, tc = (t.get("from_currency") or "?").upper(), (t.get("to_currency") or "?").upper()
        amt = t.get("amount_from_jpy")
        trade = (
            f'<span class="trade"><span style="color:{cur_color(fc)}">{esc(fc)}</span>'
            f'<span class="muted">→</span>'
            f'<span style="color:{cur_color(tc)}">{esc(tc)}</span>'
            f'{f" {fmt_jpy(amt)}円" if amt else ""}'
            f'<span class="muted"> ({esc(s["last_trade_date"][5:] if len(s["last_trade_date"]) > 5 else s["last_trade_date"])})</span></span>'
        )
    else:
        trade = '<span class="muted">取引実績なし</span>'

    rank_html = f'<span class="rank">#{rank}</span>' if rank else '<span class="rank muted">–</span>'
    week_dot = '<span class="fresh" title="今週投稿あり"></span>' if s["posted_this_week"] else ""
    tendency = esc(p.get("tendency", "")) or '<span class="muted">プロフィール未作成</span>'
    watch = p.get("watch", "")
    watch_html = (
        f'<div class="watch"><span class="watch-label">読み筋</span>{esc(watch)}</div>' if watch else ""
    )
    style_tag = esc(p.get("style", ""))

    own = " own" if uname == OWN_TEAM else ""
    own_badge = '<span class="own-badge">自チーム</span>' if own else ""
    return f'''
  <article class="card{own}" id="team-{esc(uname)}" data-name="{esc(uname)} {style_tag}">
    <header class="card-head">
      {rank_html}
      <a class="card-team" href="https://note.com/{esc(uname)}" target="_blank">@{esc(uname)}</a>{own_badge}
      {week_dot}
      {f'<span class="style-tag">{style_tag}</span>' if style_tag else ""}
      {balance}
    </header>
    {mtm_html}
    <div class="chips">{holdings_chips(s["holdings"])}</div>
    {alloc_bar(s["holdings"])}
    <p class="tendency">{tendency}</p>
    {watch_html}
    <footer class="card-foot">
      {move}
      <div class="foot-row">最終取引: {trade}<span class="sep">·</span>取引 {s["n_trades"]}回<span class="sep">·</span>記事 {len(s["articles"])}件</div>
    </footer>
  </article>'''


def build_html(states: list) -> str:
    now = datetime.now(JST)
    week_no = (now - COMPETITION_START).days // 7 + 1

    ranked = [s for s in states if s["current"] is not None]
    ranked.sort(key=lambda s: -s["current"])
    rank_of = {s["username"]: i for i, s in enumerate(ranked, 1)}
    ordered = ranked + [s for s in states if s["current"] is None]

    n_gain = sum(1 for s in ranked if s["delta"] > 0)
    n_loss = sum(1 for s in ranked if s["delta"] < 0)
    avg = sum(s["delta"] for s in ranked) / len(ranked) if ranked else 0
    leader = ranked[0] if ranked else None
    posted = sum(1 for s in states if s["posted_this_week"])

    leader_html = (
        f'@{esc(leader["username"])} <span class="kpi-sub {"pos" if leader["delta"] >= 0 else "neg"}">'
        f'{"+" if leader["delta"] >= 0 else ""}{leader["delta"]:,.0f}円</span>'
        if leader else "—"
    )

    cards = "\n".join(team_card(rank_of.get(s["username"]), s) for s in ordered)
    lb = leaderboard_rows(states)

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaika Monitor — 第{week_no}週</title>
<style>
  :root {{
    --page:    #0d0d0d;
    --surface: #1a1a19;
    --border:  rgba(255,255,255,0.10);
    --grid:    #2c2c2a;
    --text:    #ffffff;
    --text2:   #c3c2b7;
    --muted:   #898781;
    --good:    {GOOD};
    --bad:     {BAD};
    --accent:  #3987e5;
    --radius:  10px;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--page); color:var(--text);
    font-family:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;
    font-size:13.5px; line-height:1.65; padding-bottom:60px;
  }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .muted {{ color:var(--muted); }}
  .pos {{ color:var(--good); }}
  .neg {{ color:var(--bad); }}
  .unit {{ color:var(--muted); font-size:.75em; margin-left:1px; }}

  header.page {{
    padding:26px 32px 18px; display:flex; align-items:baseline; gap:16px; flex-wrap:wrap;
  }}
  header.page h1 {{ font-size:21px; letter-spacing:-.3px; }}
  header.page .meta {{ color:var(--muted); font-size:12px; }}

  .kpis {{
    display:grid; grid-template-columns:repeat(4,1fr); gap:12px; padding:0 32px;
  }}
  @media(max-width:860px) {{ .kpis {{ grid-template-columns:1fr 1fr; }} }}
  .kpi {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:12px 16px;
  }}
  .kpi-label {{ font-size:11px; color:var(--muted); letter-spacing:.05em; }}
  .kpi-value {{ font-size:22px; font-weight:700; letter-spacing:-.4px; }}
  .kpi-sub {{ font-size:13px; font-weight:600; margin-left:6px; }}

  /* Leaderboard */
  .lb {{
    margin:16px 32px; background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:14px 18px 4px;
  }}
  .lb h2 {{ font-size:11px; color:var(--muted); letter-spacing:.08em; margin-bottom:10px; }}
  .lb-scroll {{ overflow-x:auto; }}
  .lb-row {{
    display:grid; grid-template-columns:24px minmax(150px,220px) 128px 110px minmax(120px,1fr) 84px;
    gap:12px; align-items:center; min-width:640px;
    padding:6px 0; border-bottom:1px solid var(--grid); cursor:pointer;
  }}
  .lb-row:last-child {{ border-bottom:none; }}
  .lb-row:hover {{ background:rgba(255,255,255,0.03); }}
  .lb-row.own {{ background:rgba(57,135,229,0.10); box-shadow:inset 3px 0 0 var(--accent); }}
  .lb-row.own:hover {{ background:rgba(57,135,229,0.16); }}
  .own-badge {{
    font-size:9.5px; font-weight:700; color:var(--accent);
    border:1px solid var(--accent); border-radius:4px;
    padding:0 5px; margin-left:6px; vertical-align:middle; white-space:nowrap;
  }}
  .lb-rank {{ color:var(--muted); font-size:12px; text-align:right; font-variant-numeric:tabular-nums; }}
  .lb-team {{ font-weight:600; font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .lb-style {{ color:var(--muted); font-weight:400; font-size:10.5px; margin-left:6px; }}
  .lb-total {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; line-height:1.2; }}
  .lb-asof {{ color:var(--muted); font-size:9.5px; }}
  .lb-track {{ position:relative; height:10px; min-width:80px; }}
  .lb-zero {{ position:absolute; left:50%; top:-2px; bottom:-2px; width:1px; background:var(--grid); }}
  .lb-bar {{ position:absolute; top:1px; height:8px; }}
  .lb-bar.pos {{ left:50%; background:var(--good); border-radius:0 4px 4px 0; }}
  .lb-bar.neg {{ right:50%; background:var(--bad); border-radius:4px 0 0 4px; }}
  .lb-delta {{ font-variant-numeric:tabular-nums; font-size:12px; font-weight:600; text-align:right; white-space:nowrap; }}
  .spark {{ display:block; }}

  /* Filter */
  .controls {{ padding:4px 32px 0; }}
  .controls input {{
    background:var(--surface); border:1px solid var(--border); color:var(--text);
    border-radius:8px; padding:8px 14px; font-size:13px; width:280px; outline:none;
  }}
  .controls input:focus {{ border-color:var(--accent); }}

  /* Team cards */
  .cards {{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr));
    gap:14px; padding:14px 32px 0;
  }}
  .card {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:14px 16px 12px;
    display:flex; flex-direction:column; gap:8px;
  }}
  .card.own {{ border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }}
  .card-head {{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .rank {{ color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; min-width:22px; }}
  .card-team {{ font-weight:700; font-size:14.5px; color:var(--text); }}
  .card-team:hover {{ color:var(--accent); }}
  .fresh {{ width:7px; height:7px; border-radius:50%; background:var(--accent); display:inline-block; }}
  .style-tag {{
    font-size:10.5px; color:var(--text2); border:1px solid var(--border);
    border-radius:20px; padding:1px 9px; white-space:nowrap;
  }}
  .bal {{ margin-left:auto; white-space:nowrap; }}
  .bal-num {{ font-size:16px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .bal-asof {{ color:var(--muted); font-size:10px; margin-left:4px; }}
  .bal-delta {{ font-size:12px; font-weight:600; margin-left:7px; }}
  .mtm {{ font-size:11px; color:var(--muted); }}

  .chips {{ display:flex; flex-wrap:wrap; gap:5px; }}
  .chip {{
    display:inline-flex; align-items:center; gap:5px;
    border:1px solid var(--border); border-radius:6px; padding:1px 8px;
    font-size:11.5px; font-weight:600; color:var(--text2); white-space:nowrap;
  }}
  .chip-dot {{ width:8px; height:8px; border-radius:50%; background:var(--c); }}
  .chip-amt {{ font-weight:400; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .alloc {{ display:flex; gap:2px; height:6px; border-radius:3px; overflow:hidden; }}
  .alloc-seg {{ min-width:3px; }}

  .tendency {{ color:var(--text2); font-size:12.5px; }}
  .watch {{
    font-size:12px; color:var(--text2);
    background:rgba(57,135,229,0.08); border-left:2px solid var(--accent);
    padding:5px 10px; border-radius:0 6px 6px 0;
  }}
  .watch-label {{
    color:var(--accent); font-weight:700; font-size:10.5px; letter-spacing:.06em;
    margin-right:8px;
  }}

  .card-foot {{ margin-top:auto; padding-top:6px; border-top:1px solid var(--grid); }}
  .latest {{ font-size:12px; color:var(--text2); }}
  .latest-date {{ color:var(--muted); font-variant-numeric:tabular-nums; margin-right:2px; }}
  .latest-link {{ color:var(--text2); }}
  .latest-link:hover {{ color:var(--accent); }}
  .foot-row {{ font-size:11px; color:var(--muted); margin-top:3px; }}
  .trade {{ font-weight:600; font-size:11px; }}
  .sep {{ margin:0 6px; }}
  .hidden {{ display:none !important; }}
</style>
</head>
<body>

<header class="page">
  <h1>Gaika Monitor</h1>
  <span class="meta">第{week_no}週 · {now.strftime("%Y-%m-%d %H:%M JST")} 生成 · 元手100,000円 · {posted}/{len(states)}チームが今週投稿</span>
</header>

<div class="kpis">
  <div class="kpi"><div class="kpi-label">首位</div><div class="kpi-value">{leader_html}</div></div>
  <div class="kpi"><div class="kpi-label">プラス圏 / マイナス圏</div>
    <div class="kpi-value"><span class="pos">{n_gain}</span><span class="muted" style="font-size:15px"> / </span><span class="neg">{n_loss}</span></div></div>
  <div class="kpi"><div class="kpi-label">平均損益</div>
    <div class="kpi-value {"pos" if avg >= 0 else "neg"}">{"+" if avg >= 0 else ""}{avg:,.0f}<span class="unit">円</span></div></div>
  <div class="kpi"><div class="kpi-label">参加チーム</div><div class="kpi-value">{len(states)}</div></div>
</div>

<div class="lb">
  <h2>順位 — 記事に記載された総残高で順位付け（行クリックでカードへ）</h2>
  <div class="lb-scroll">
{lb}
  </div>
</div>

<div class="controls">
  <input id="q" type="text" placeholder="チーム名・スタイルで絞り込み...">
</div>

<div class="cards">
{cards}
</div>

<script>
document.getElementById('q').addEventListener('input', e => {{
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    c.classList.toggle('hidden', q && !c.dataset.name.toLowerCase().includes(q));
  }});
}});
function jumpTo(name) {{
  const el = document.getElementById('team-' + name);
  if (el) {{
    el.scrollIntoView({{behavior:'smooth', block:'center'}});
    el.style.outline = '2px solid var(--accent)';
    setTimeout(() => el.style.outline = '', 1600);
  }}
}}
</script>
</body>
</html>'''


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not LOG.exists():
        raise SystemExit(f"ERROR: {LOG} not found. Run fetch_articles.py first.")

    log_data = json.loads(LOG.read_text(encoding="utf-8"))
    all_arts = log_data.get("articles", {})

    overrides = {}
    if OVERRIDES.exists():
        raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        overrides = {k: v for k, v in raw.items() if not k.startswith("_")}

    profiles = {}
    if PROFILES.exists():
        raw = json.loads(PROFILES.read_text(encoding="utf-8"))
        profiles = {k: v for k, v in raw.items() if not k.startswith("_")}

    team_articles: dict[str, list] = {u: [] for u in TEAMS}
    for url, art in all_arts.items():
        entry = dict(art)
        if url in overrides:
            ov = overrides[url]
            if "relevant" in ov:
                entry["relevant"] = ov["relevant"]
            if "analysis" in ov:
                merged = dict(entry.get("analysis") or {})
                merged.update(ov["analysis"])
                entry["analysis"] = merged
        if entry.get("relevant") is not True:
            continue
        if entry.get("username") in team_articles:
            team_articles[entry["username"]].append(entry)

    states = [team_state(u, arts, profiles.get(u, {})) for u, arts in team_articles.items()]

    html = build_html(states)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    fx_rates.flush()

    n_rel = sum(len(a) for a in team_articles.values())
    print(f"Report written -> {OUTPUT}  ({len(TEAMS)} teams, {n_rel} relevant articles)")


if __name__ == "__main__":
    main()
