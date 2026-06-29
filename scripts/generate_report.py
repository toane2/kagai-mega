"""
generate_report.py  —  Gaika Monitor HTML report
=================================================
Reads:
  data/article_log.json   — persistent article log (managed by fetch_articles.py + analysis)
  data/overrides.json     — manual corrections / image-based additions

Writes:
  output/report.html

Article log entry schema:
{
  "url":         str,
  "username":    str,
  "title":       str,
  "post_date":   str (ISO 8601),
  "this_week":   bool,
  "body":        str,
  "body_method": str,
  "fetched_at":  str,
  "relevant":    bool | null,   # null = unanalyzed; false = discard from report
  "analyzed":    bool,
  "analysis": {
    "trades": [
      {
        "from_currency": str,
        "to_currency":   str,
        "rate":          float | null,  # exact rate stated in article
        "amount_from_jpy": float | null,
        "date":          str | null
      }
    ],
    "holdings": [
      {
        "currency":   str,
        "amount_jpy": float | null   # null if not stated
      }
    ],
    "intent":              str | null,   # 1-2 phrase summary
    "changes_since_prev":  str | null    # set on articles after the first for a team
  }
}
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import html as html_mod

LOG       = Path("data/article_log.json")
OVERRIDES = Path("data/overrides.json")
OUTPUT    = Path("output/report.html")

JST = timezone(timedelta(hours=9))

CURRENCY_COLOR = {
    "USD": "#3b82f6",
    "EUR": "#8b5cf6",
    "GBP": "#ec4899",
    "AUD": "#f59e0b",
    "CNY": "#ef4444",
    "CHF": "#10b981",
    "SEK": "#6366f1",
    "NZD": "#14b8a6",
    "CAD": "#f97316",
    "HKD": "#84cc16",
    "ZAR": "#a78bfa",
    "JPY": "#64748b",
}


def esc(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


def fmt_date(s) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s).astimezone(JST)
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return str(s)


def fmt_jpy(v) -> str:
    if v is None:
        return ""
    try:
        return f"{int(float(v)):,}円"
    except Exception:
        return str(v)


def fmt_rate(r) -> str:
    if r is None:
        return ""
    try:
        f = float(r)
        if f >= 100:
            return f"{f:.2f}"
        elif f >= 10:
            return f"{f:.4f}"
        else:
            return f"{f:.5f}"
    except Exception:
        return str(r)


def currency_chip(cur: str, amount_jpy=None) -> str:
    color = CURRENCY_COLOR.get(cur.upper(), "#94a3b8")
    amount_str = f" <span class='chip-amt'>{fmt_jpy(amount_jpy)}</span>" if amount_jpy else ""
    return f'<span class="cur-chip" style="border-color:{color};color:{color}">{esc(cur)}{amount_str}</span>'


def trade_summary(trades: list) -> str:
    if not trades:
        return '<span class="muted">—</span>'
    parts = []
    for t in trades:
        fc   = esc(t.get("from_currency", "?"))
        tc   = esc(t.get("to_currency", "?"))
        rate = fmt_rate(t.get("rate"))
        amt  = t.get("amount_from_jpy")
        date = esc(t.get("date") or "")

        rate_str = f" @ <span class='trade-rate'>{rate}</span>" if rate else ""
        amt_str  = f" ({fmt_jpy(amt)})" if amt else ""
        date_str = f"<span class='trade-date'>{date}</span> " if date else ""
        fc_color = CURRENCY_COLOR.get(fc.upper(), "#94a3b8")
        tc_color = CURRENCY_COLOR.get(tc.upper(), "#94a3b8")
        parts.append(
            f'<div class="trade-row">'
            f'{date_str}'
            f'<span style="color:{fc_color}">{fc}</span>'
            f' → '
            f'<span style="color:{tc_color}">{tc}</span>'
            f'{rate_str}{amt_str}'
            f'</div>'
        )
    return "\n".join(parts)


def holdings_display(holdings: list) -> str:
    if not holdings:
        return '<span class="muted">—</span>'
    chips = " ".join(currency_chip(h.get("currency", "?"), h.get("amount_jpy")) for h in holdings)
    return f'<div class="holdings-row">{chips}</div>'


def build_chart_data(team_articles: dict) -> str:
    """team_articles: {username: [article_entry, ...]}"""
    currency_counts: dict[str, int] = {}
    trade_counts: dict[str, int] = {}

    for username, articles in team_articles.items():
        seen_currencies: set = set()
        team_trades = 0
        for art in articles:
            analysis = art.get("analysis") or {}
            for h in analysis.get("holdings", []):
                cur = h.get("currency", "")
                if cur and cur.upper() != "JPY":
                    seen_currencies.add(cur.upper())
            team_trades += len(analysis.get("trades", []))
        for cur in seen_currencies:
            currency_counts[cur] = currency_counts.get(cur, 0) + 1
        trade_counts[username] = team_trades

    top_currencies = sorted(currency_counts.items(), key=lambda x: -x[1])[:8]
    cur_labels = [c[0] for c in top_currencies]
    cur_data   = [c[1] for c in top_currencies]
    cur_colors = [CURRENCY_COLOR.get(c, "#94a3b8") for c in cur_labels]

    team_labels  = list(trade_counts.keys())
    team_trades  = [trade_counts[u] for u in team_labels]

    return json.dumps({
        "cur_labels":  cur_labels,
        "cur_data":    cur_data,
        "cur_colors":  cur_colors,
        "team_labels": team_labels,
        "team_trades": team_trades,
    })


def article_override_json(entry: dict) -> str:
    """Return a JSON snippet for the override file for this article."""
    payload = {
        entry["url"]: {
            "relevant": entry.get("relevant"),
            "analysis": entry.get("analysis") or {
                "trades": [],
                "holdings": [],
                "intent": None,
                "changes_since_prev": None
            }
        }
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_team_row(i: int, username: str, articles: list) -> str:
    """Build all <tr> rows for one team."""
    if not articles:
        return (
            f'<tr data-team="{i}" class="row-nopost">'
            f'<td class="td-team"><a href="https://note.com/{esc(username)}" target="_blank" class="team-link">@{esc(username)}</a></td>'
            f'<td colspan="6"><span class="muted">— ログなし —</span></td>'
            f'</tr>'
        )

    has_post = any(a.get("this_week") for a in articles)
    unanalyzed = any(not a.get("analyzed") for a in articles)
    row_base_class = "" if has_post else "row-nopost"

    rows = []
    for art_idx, art in enumerate(articles):
        analysis = art.get("analysis") or {}
        trades   = analysis.get("trades", [])
        holdings = analysis.get("holdings", [])
        intent   = analysis.get("intent", "")
        changes  = analysis.get("changes_since_prev", "")
        is_older = art_idx > 0

        post_date   = fmt_date(art.get("post_date"))
        url         = art.get("url", "")
        title       = esc(art.get("title") or "—")
        title_cell  = f'<a href="{esc(url)}" target="_blank">{title}</a>' if url else title

        dim        = ' class="cell-older"' if is_older else ""
        row_class  = ("row-older " if is_older else row_base_class)

        pending_badge = ' <span class="badge-pending">未分析</span>' if not art.get("analyzed") else ""
        changes_html  = f'<span class="changes-text">{esc(changes)}</span>' if changes else '<span class="muted">—</span>'
        intent_html   = esc(intent) if intent else '<span class="muted">—</span>'

        team_part = ""
        if art_idx == 0:
            unanalyzed_note = ' <span class="badge-pending">要分析あり</span>' if unanalyzed else ""
            override_json   = article_override_json(art)
            team_part = (
                f'<td class="td-team" rowspan="{len(articles)}">'
                f'<a href="https://note.com/{esc(username)}" target="_blank" class="team-link">@{esc(username)}</a>'
                f'{unanalyzed_note}'
                f'<div class="edit-toggle" onclick="toggleEdit(this)">'
                f'<span class="edit-btn">✏ override</span>'
                f'<div class="edit-panel" style="display:none">'
                f'<div class="edit-hint">Edit <code>data/overrides.json</code> with this key, then re-run <code>generate_report.py</code>.</div>'
                f'<textarea class="edit-json" rows="10">{esc(override_json)}</textarea>'
                f'<button onclick="copyEdit(this)">Copy JSON</button>'
                f'</div>'
                f'</div>'
                f'</td>'
            )

        rows.append(
            f'<tr class="{row_class.strip()}" data-team="{i}" data-week="{1 if any(a.get("this_week") for a in articles) else 0}">'
            f'{team_part}'
            f'<td{dim}>{post_date}{pending_badge}</td>'
            f'<td{dim}>{title_cell}</td>'
            f'<td{dim}>{trade_summary(trades)}</td>'
            f'<td{dim}>{holdings_display(holdings)}</td>'
            f'<td{dim} class="td-intent">{intent_html}</td>'
            f'<td{dim} class="td-changes">{changes_html}</td>'
            f'</tr>'
        )

    return "\n".join(rows)


def build_html(team_articles: dict, stats: dict) -> str:
    now        = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    chart_data = build_chart_data(team_articles)

    rows = []
    for i, (username, articles) in enumerate(team_articles.items()):
        rows.append(build_team_row(i, username, articles))
    rows_html = "\n".join(rows)

    posted   = stats["posted"]
    active   = stats["active"]
    analyzed = stats["analyzed"]
    total    = stats["total_articles"]

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaika Monitor — {now}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #21262d;
    --text:    #e6edf3;
    --muted:   #8b949e;
    --accent:  #58a6ff;
    --yellow:  #f59e0b;
    --radius:  8px;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--text);
    font-family:"SF Mono","Fira Code",ui-monospace,monospace;
    font-size:13px; line-height:1.6;
  }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}

  header {{
    padding:28px 32px 20px; border-bottom:1px solid var(--border);
    display:flex; align-items:flex-start; gap:20px; flex-wrap:wrap;
  }}
  header h1 {{ font-size:22px; font-weight:700; letter-spacing:-.5px; }}
  header .meta {{ color:var(--muted); font-size:12px; margin-top:2px; }}
  .pill-row {{ display:flex; gap:10px; margin-top:10px; flex-wrap:wrap; }}
  .stat-pill {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:20px; padding:4px 14px;
    font-size:12px; display:flex; gap:6px; align-items:center;
  }}
  .stat-pill .num {{ color:var(--accent); font-weight:700; font-size:15px; }}

  .charts {{
    display:grid; grid-template-columns:1fr 1fr;
    gap:16px; padding:24px 32px;
  }}
  @media(max-width:800px) {{ .charts {{ grid-template-columns:1fr; }} }}
  .chart-card {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:16px;
  }}
  .chart-card h2 {{
    font-size:11px; color:var(--muted); text-transform:uppercase;
    letter-spacing:.08em; margin-bottom:12px;
  }}
  .chart-card canvas {{ max-height:220px; }}

  .table-wrap {{ padding:0 32px 40px; overflow-x:auto; }}
  .controls {{ display:flex; gap:12px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }}
  .controls input[type=text] {{
    background:var(--surface); border:1px solid var(--border);
    color:var(--text); border-radius:6px; padding:7px 12px;
    font-size:12px; font-family:inherit; outline:none; width:240px;
  }}
  .controls input[type=text]:focus {{ border-color:var(--accent); }}
  .controls label {{
    display:flex; align-items:center; gap:6px;
    color:var(--muted); font-size:12px; cursor:pointer;
  }}

  table {{
    width:100%; border-collapse:collapse;
    background:var(--surface); border-radius:var(--radius);
    overflow:hidden; border:1px solid var(--border);
  }}
  thead th {{
    background:#1c2128; color:var(--muted);
    font-size:11px; text-transform:uppercase; letter-spacing:.06em;
    padding:10px 14px; text-align:left; border-bottom:1px solid var(--border);
    white-space:nowrap;
  }}
  tbody tr {{ border-bottom:1px solid var(--border); transition:background .1s; }}
  tbody tr:last-child {{ border-bottom:none; }}
  tbody tr:hover {{ background:#1c2128; }}
  tbody td {{ padding:10px 14px; vertical-align:top; }}

  .row-older {{ border-top:1px dashed #2d333b !important; }}
  .row-older .cell-older {{ opacity:.6; }}
  .row-nopost {{ opacity:.45; }}

  .td-team {{ min-width:140px; max-width:180px; }}
  .td-intent {{ max-width:200px; color:var(--muted); font-size:12px; }}
  .td-changes {{ max-width:180px; color:var(--yellow); font-size:12px; }}

  .team-link {{ font-weight:600; color:var(--text); }}
  .team-link:hover {{ color:var(--accent); }}

  /* Trades */
  .trade-row {{ margin-bottom:3px; white-space:nowrap; }}
  .trade-date {{ color:var(--muted); font-size:11px; margin-right:4px; }}
  .trade-rate {{ color:#22c55e; font-weight:600; }}

  /* Currency chips */
  .holdings-row {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .cur-chip {{
    display:inline-block; border:1px solid; border-radius:4px;
    padding:1px 7px; font-size:11px; font-weight:600; white-space:nowrap;
  }}
  .chip-amt {{ font-weight:400; opacity:.8; margin-left:3px; }}

  /* Override panel */
  .edit-toggle {{ margin-top:6px; }}
  .edit-btn {{
    font-size:10px; color:var(--muted); cursor:pointer;
    padding:2px 6px; border:1px solid var(--border); border-radius:4px;
    display:inline-block;
  }}
  .edit-btn:hover {{ color:var(--accent); border-color:var(--accent); }}
  .edit-panel {{ margin-top:6px; }}
  .edit-hint {{ font-size:10px; color:var(--muted); margin-bottom:4px; line-height:1.5; }}
  .edit-hint code {{ color:var(--accent); background:#1c2128; padding:0 3px; border-radius:3px; }}
  .edit-json {{
    width:100%; background:#0d1117; border:1px solid var(--border);
    color:var(--text); font-family:inherit; font-size:10px;
    padding:6px; border-radius:4px; resize:vertical; min-height:120px;
  }}
  .edit-panel button {{
    margin-top:4px; padding:3px 10px; font-size:10px;
    background:var(--surface); border:1px solid var(--border);
    color:var(--text); border-radius:4px; cursor:pointer;
    font-family:inherit;
  }}
  .edit-panel button:hover {{ border-color:var(--accent); color:var(--accent); }}

  /* Badges */
  .badge-pending {{
    display:inline-block; font-size:9px; font-weight:700;
    background:rgba(245,158,11,.2); border:1px solid rgba(245,158,11,.4);
    color:var(--yellow); border-radius:3px; padding:1px 5px;
    margin-left:4px; vertical-align:middle;
  }}
  .changes-text {{ white-space:normal; }}
  .muted {{ color:var(--muted); }}
  .hidden {{ display:none !important; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>Gaika Monitor</h1>
    <div class="meta">Generated {now} · ノーレバレッジ外貨取引大会 · {analyzed}/{total} 記事分析済</div>
    <div class="pill-row">
      <div class="stat-pill"><span class="num">{posted}</span> 今週投稿</div>
      <div class="stat-pill"><span class="num">{active}</span> ポジションあり</div>
    </div>
  </div>
</header>

<div class="charts">
  <div class="chart-card">
    <h2>Currency Distribution (# Teams Holding)</h2>
    <canvas id="curChart"></canvas>
  </div>
  <div class="chart-card">
    <h2>Trade Count per Team</h2>
    <canvas id="tradeChart"></canvas>
  </div>
</div>

<div class="table-wrap">
  <div class="controls">
    <input id="search" type="text" placeholder="チーム名 / 通貨で検索...">
    <label><input type="checkbox" id="filterPosted"> 今週投稿のみ</label>
    <label><input type="checkbox" id="filterActive"> ポジションありのみ</label>
  </div>

  <table id="posTable">
    <thead>
      <tr>
        <th>チーム</th>
        <th>投稿日時</th>
        <th>タイトル</th>
        <th>取引</th>
        <th>保有通貨</th>
        <th>意図・戦略</th>
        <th>前回との変化</th>
      </tr>
    </thead>
    <tbody id="tbody">
      {rows_html}
    </tbody>
  </table>
</div>

<script>
const RAW = {chart_data};

new Chart(document.getElementById('curChart'), {{
  type: 'bar',
  data: {{
    labels: RAW.cur_labels,
    datasets: [{{ data: RAW.cur_data, backgroundColor: RAW.cur_colors, borderWidth: 0 }}]
  }},
  options: {{
    indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color:'#8b949e', stepSize:1 }}, grid: {{ color:'#21262d' }} }},
      y: {{ ticks: {{ color:'#e6edf3', font:{{ size:11 }} }}, grid: {{ display:false }} }}
    }}
  }}
}});

new Chart(document.getElementById('tradeChart'), {{
  type: 'bar',
  data: {{
    labels: RAW.team_labels,
    datasets: [{{ data: RAW.team_trades, backgroundColor: '#58a6ff', borderWidth:0 }}]
  }},
  options: {{
    plugins: {{ legend: {{ display:false }} }},
    scales: {{
      x: {{ ticks: {{ color:'#8b949e', font:{{ size:10 }}, maxRotation:45 }}, grid:{{ display:false }} }},
      y: {{ ticks: {{ color:'#8b949e', stepSize:1 }}, grid:{{ color:'#21262d' }} }}
    }}
  }}
}});

function buildGroups() {{
  const g = {{}};
  document.querySelectorAll('#tbody tr').forEach(r => {{
    const t = r.dataset.team;
    if (!g[t]) g[t] = [];
    g[t].push(r);
  }});
  return g;
}}
const GROUPS = buildGroups();

function filter() {{
  const q      = document.getElementById('search').value.toLowerCase();
  const post   = document.getElementById('filterPosted').checked;
  const active = document.getElementById('filterActive').checked;
  for (const rows of Object.values(GROUPS)) {{
    const text     = rows.map(r => r.textContent).join(' ').toLowerCase();
    const thisWeek = rows[0].dataset.week === '1';
    const hasCur   = rows[0].querySelector('.cur-chip') !== null;
    const hide = (q && !text.includes(q)) || (post && !thisWeek) || (active && !hasCur);
    rows.forEach(r => r.classList.toggle('hidden', hide));
  }}
}}

document.getElementById('search').addEventListener('input', filter);
document.getElementById('filterPosted').addEventListener('change', filter);
document.getElementById('filterActive').addEventListener('change', filter);

function toggleEdit(el) {{
  const panel = el.querySelector('.edit-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}}

function copyEdit(btn) {{
  const ta = btn.previousElementSibling;
  navigator.clipboard.writeText(ta.value).then(() => {{
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy JSON', 1500);
  }});
}}
</script>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not LOG.exists():
        print(f"ERROR: {LOG} not found. Run fetch_articles.py first.")
        raise SystemExit(1)

    log_data  = json.loads(LOG.read_text(encoding="utf-8"))
    all_arts  = log_data.get("articles", {})

    # Load overrides
    overrides = {}
    if OVERRIDES.exists():
        raw_ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        overrides = {k: v for k, v in raw_ov.items() if not k.startswith("_")}

    # Apply overrides into article entries (non-destructively for this run)
    entries: dict = {}
    for url, art in all_arts.items():
        entry = dict(art)
        if url in overrides:
            ov = overrides[url]
            if "relevant" in ov:
                entry["relevant"] = ov["relevant"]
            if "analysis" in ov:
                if entry.get("analysis"):
                    merged = dict(entry["analysis"])
                    merged.update(ov["analysis"])
                    entry["analysis"] = merged
                else:
                    entry["analysis"] = ov["analysis"]
                entry["analyzed"] = True
        entries[url] = entry

    # Group by team, filter out irrelevant, sort by date desc
    teams_list = [
        "cool_parrot6215", "gaikafuru", "kiajobhunting", "gakusei_kangae",
        "masashi_uclab", "keylink_by_kk", "atsuya_044", "joyful_turtle486",
        "kanno_wmori", "saku03081", "re_0oji", "yuyu10y", "mtk____",
        "mafty_navueerin", "kyoichi_osaka", "toshiki_naka", "tomoro_0726",
        "lovely_rue455", "ionub", "legal_wren2006", "nasgor", "fast_crocus9353",
    ]
    team_articles = {u: [] for u in teams_list}

    for url, art in entries.items():
        uname = art.get("username", "")
        if art.get("relevant") is False:
            continue  # explicitly marked irrelevant
        if uname in team_articles:
            team_articles[uname].append(art)

    # Sort each team's articles newest-first
    for uname in team_articles:
        team_articles[uname].sort(
            key=lambda a: a.get("post_date") or "", reverse=True
        )
        # Show at most 3 per team in the report (most recent)
        team_articles[uname] = team_articles[uname][:3]

    # Stats — only count relevant articles (irrelevant ones are discarded from report)
    all_entries     = list(entries.values())
    relevant_entries = [a for a in all_entries if a.get("relevant") is not False]
    analyzed_count  = sum(1 for a in relevant_entries if a.get("analyzed"))
    total_articles  = len(relevant_entries)
    posted_count    = sum(
        1 for arts in team_articles.values()
        if any(a.get("this_week") for a in arts)
    )
    active_count    = sum(
        1 for arts in team_articles.values()
        if any(
            a.get("analysis") and a["analysis"].get("holdings") and
            any(h.get("currency", "").upper() != "JPY" for h in a["analysis"]["holdings"])
            for a in arts
        )
    )

    stats = {
        "posted":          posted_count,
        "active":          active_count,
        "analyzed":        analyzed_count,
        "total_articles":  total_articles,
    }

    html = build_html(team_articles, stats)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Report written -> {OUTPUT}  ({len(teams_list)} teams, {analyzed_count}/{total_articles} analyzed)")


if __name__ == "__main__":
    main()
