"""
generate_report.py
Reads output/analyzed_positions.json and writes output/report.html.

JSON schema  (output/analyzed_positions.json):
[
  {
    "username":  str,
    "has_post":  bool,
    "articles": [                  // up to 2 entries, newest first
      {
        "post_date":   str | null,   // ISO 8601
        "article_url": str | null,
        "title":       str | null,
        "assets": [
          {
            "name":      str,          // e.g. "USD/JPY"
            "direction": "long"|"short"|"neutral"|"unknown",
            "entry":     float | null, // entry price in JPY per 1 unit of foreign currency
            "target":    float | null,
            "stop_loss": float | null,
            "size_pct":  float | null  // % of 100k portfolio
          }
        ],
        "strategy":  str | null,
        "changes":   str | null,
        "flags": []                    // "large_position", "strategy_mismatch"
      }
    ]
  }
]
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import html as html_mod

INPUT  = Path("output/analyzed_positions.json")
OUTPUT = Path("output/report.html")

JST = timezone(timedelta(hours=9))

DIRECTION_COLOR = {
    "long":    "#22c55e",
    "short":   "#ef4444",
    "neutral": "#94a3b8",
    "unknown": "#64748b",
}

FLAG_LABEL = {
    "large_position":    "⚠ Large Position",
    "strategy_mismatch": "⚠ Strategy Mismatch",
}


def esc(s) -> str:
    return html_mod.escape(str(s)) if s is not None else "—"


def fmt_date(s) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s).astimezone(JST)
        return dt.strftime("%m/%d %H:%M JST")
    except Exception:
        return s


def direction_badge(d: str) -> str:
    color = DIRECTION_COLOR.get(d, "#64748b")
    label = d.upper() if d else "?"
    return f'<span class="badge" style="background:{color}">{label}</span>'


def flag_chips(flags: list) -> str:
    if not flags:
        return ""
    chips = " ".join(
        f'<span class="flag-chip">{FLAG_LABEL.get(f, f)}</span>'
        for f in flags
    )
    return f'<div class="flag-row">{chips}</div>'


def fmt_price(p) -> str:
    if p is None:
        return "—"
    try:
        f = float(p)
        # Show up to 4 significant digits
        if f >= 100:
            return f"{f:.2f}"
        elif f >= 10:
            return f"{f:.4f}"
        else:
            return f"{f:.5f}"
    except Exception:
        return str(p)


def assets_cell(assets: list) -> str:
    """Render the currency pairs + direction as stacked pills."""
    if not assets:
        return '<span class="muted">—</span>'
    parts = []
    for a in assets:
        name      = esc(a.get("name", "?"))
        d         = a.get("direction", "unknown")
        size      = a.get("size_pct")
        badge     = direction_badge(d)
        size_str  = f' <span class="size-tag">{size:.0f}%</span>' if size is not None else ""
        parts.append(f'<div class="asset-pill">{badge} <strong>{name}</strong>{size_str}</div>')
    return "".join(parts)


def price_cell(assets: list, field: str) -> str:
    """Render entry / target / stop_loss column for all assets in an article."""
    if not assets:
        return '<span class="muted">—</span>'
    rows = []
    for a in assets:
        val = a.get(field)
        pair = esc(a.get("name", ""))
        if val is not None:
            rows.append(f'<div class="price-row"><span class="pair-hint">{pair}</span> {fmt_price(val)}</div>')
        else:
            rows.append(f'<div class="price-row muted">—</div>')
    return "".join(rows) if rows else '<span class="muted">—</span>'


def all_flags(team: dict) -> list:
    seen, out = set(), []
    for art in team.get("articles", []):
        for f in art.get("flags", []):
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def build_chart_data(teams: list) -> str:
    labels, posted = [], []
    direction_counts = {"long": 0, "short": 0, "neutral": 0, "unknown": 0}
    currency_counts: dict[str, int] = {}

    for t in teams:
        labels.append(t.get("username", "?"))
        posted.append(1 if t.get("has_post") else 0)
        for art in t.get("articles", []):
            for a in art.get("assets", []):
                d = a.get("direction", "unknown")
                direction_counts[d] = direction_counts.get(d, 0) + 1
                name = a.get("name", "other")
                currency_counts[name] = currency_counts.get(name, 0) + 1

    # top 6 currencies
    top_currencies = sorted(currency_counts.items(), key=lambda x: -x[1])[:6]
    cur_labels = [c[0] for c in top_currencies]
    cur_data   = [c[1] for c in top_currencies]

    return json.dumps({
        "labels":       labels,
        "posted":       posted,
        "directions":   direction_counts,
        "cur_labels":   cur_labels,
        "cur_data":     cur_data,
    })


def article_row_cells(article: dict, is_second: bool = False) -> str:
    post_date   = fmt_date(article.get("post_date"))
    article_url = article.get("article_url")
    title       = esc(article.get("title"))
    assets      = article.get("assets", [])
    strategy    = esc(article.get("strategy"))
    changes     = esc(article.get("changes"))

    title_cell = (
        f'<a href="{esc(article_url)}" target="_blank">{title}</a>'
        if article_url else title
    )

    dim = ' class="cell-older"' if is_second else ""
    return (
        f'<td{dim}>{post_date}</td>'
        f'<td{dim}>{title_cell}</td>'
        f'<td{dim}>{assets_cell(assets)}</td>'
        f'<td{dim}>{price_cell(assets, "entry")}</td>'
        f'<td{dim}>{price_cell(assets, "target")}</td>'
        f'<td{dim}>{price_cell(assets, "stop_loss")}</td>'
        f'<td{dim} class="td-strategy">{strategy}</td>'
        f'<td{dim} class="td-changes">{changes}</td>'
    )


def build_html(teams: list) -> str:
    now           = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    posted_count  = sum(1 for t in teams if t.get("has_post"))
    flagged_count = sum(1 for t in teams if all_flags(t))
    active_count  = sum(
        1 for t in teams
        if any(a.get("assets") for a in t.get("articles", []))
    )
    chart_data = build_chart_data(teams)

    rows = []
    for i, t in enumerate(teams):
        username = esc(t.get("username", "?"))
        profile  = t.get("profile_url", "#")
        articles = t.get("articles", [])
        flags    = all_flags(t)
        has_post = t.get("has_post", False)

        row_class_first = "row-flagged" if flags else ("row-nopost" if not has_post else "")

        team_cell = (
            f'<td class="td-team" rowspan="{max(len(articles), 1)}">'
            f'<a href="{esc(profile)}" target="_blank" class="team-link">@{username}</a>'
            f'{flag_chips(flags)}'
            f'</td>'
        )

        if not articles:
            rows.append(
                f'<tr class="{row_class_first}" data-team="{i}">'
                f'{team_cell}'
                f'<td colspan="8"><span class="no-post">— 未投稿 —</span></td>'
                f'</tr>'
            )
            continue

        for art_idx, article in enumerate(articles):
            is_second = art_idx > 0
            row_class = "row-article2" if is_second else row_class_first
            team_part = team_cell if art_idx == 0 else ""
            cells     = article_row_cells(article, is_second=is_second)
            rows.append(
                f'<tr class="{row_class}" data-team="{i}">'
                f'{team_part}{cells}'
                f'</tr>'
            )

    rows_html = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaika Monitor — {now}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:        #0d1117;
    --surface:   #161b22;
    --border:    #21262d;
    --text:      #e6edf3;
    --muted:     #8b949e;
    --accent:    #58a6ff;
    --green:     #22c55e;
    --red:       #ef4444;
    --yellow:    #f59e0b;
    --radius:    8px;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--text);
    font-family: "SF Mono","Fira Code",ui-monospace,monospace;
    font-size: 13px; line-height:1.6;
  }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}

  header {{
    padding: 28px 32px 20px;
    border-bottom: 1px solid var(--border);
    display:flex; align-items:baseline; gap:20px; flex-wrap:wrap;
  }}
  header h1 {{ font-size:22px; font-weight:700; letter-spacing:-.5px; }}
  header .meta {{ color:var(--muted); font-size:12px; }}
  .pill-row {{ display:flex; gap:12px; margin-top:8px; flex-wrap:wrap; }}
  .stat-pill {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:20px; padding:4px 14px;
    font-size:12px; display:flex; gap:6px; align-items:center;
  }}
  .stat-pill .num {{ color:var(--accent); font-weight:700; font-size:15px; }}

  .charts {{
    display:grid; grid-template-columns:1fr 1fr 1fr;
    gap:16px; padding:24px 32px;
  }}
  @media(max-width:900px) {{ .charts {{ grid-template-columns:1fr; }} }}
  .chart-card {{
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:16px;
  }}
  .chart-card h2 {{ font-size:11px; color:var(--muted); text-transform:uppercase;
                    letter-spacing:.08em; margin-bottom:12px; }}
  .chart-card canvas {{ max-height:200px; }}

  .table-wrap {{ padding:0 32px 40px; overflow-x:auto; }}
  .controls {{ display:flex; gap:12px; margin-bottom:14px; flex-wrap:wrap; }}
  .controls input[type=text] {{
    background:var(--surface); border:1px solid var(--border);
    color:var(--text); border-radius:6px; padding:7px 12px; font-size:12px;
    font-family:inherit; outline:none; width:220px;
  }}
  .controls input[type=text]:focus {{ border-color:var(--accent); }}
  .controls label {{ display:flex; align-items:center; gap:6px;
                     color:var(--muted); font-size:12px; cursor:pointer; }}

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

  .row-article2 {{ border-top: 1px dashed var(--border) !important; }}
  .row-article2 .cell-older {{ opacity:0.65; }}
  .row-flagged  {{ background:rgba(239,68,68,.06); }}
  .row-nopost   {{ opacity:.55; }}
  .no-post      {{ color:var(--muted); font-style:italic; }}
  .muted        {{ color:var(--muted); }}
  .td-team      {{ min-width:140px; }}
  .td-strategy  {{ max-width:200px; color:var(--muted); font-size:12px; }}
  .td-changes   {{ max-width:160px; color:var(--muted); font-size:12px; }}

  .team-link    {{ font-weight:600; color:var(--text); }}
  .team-link:hover {{ color:var(--accent); }}

  .badge {{
    display:inline-block; border-radius:4px;
    padding:1px 6px; font-size:10px; font-weight:700;
    color:#fff; vertical-align:middle; margin-right:3px;
  }}
  .asset-pill   {{ margin-bottom:3px; }}
  .size-tag     {{ color:var(--muted); font-size:11px; }}
  .price-row    {{ margin-bottom:2px; white-space:nowrap; }}
  .pair-hint    {{ color:var(--muted); font-size:10px; margin-right:4px; }}
  .flag-row     {{ margin-top:4px; display:flex; flex-wrap:wrap; gap:4px; }}
  .flag-chip {{
    background:rgba(245,158,11,.15); border:1px solid rgba(245,158,11,.35);
    color:var(--yellow); border-radius:4px;
    padding:1px 7px; font-size:10px; font-weight:600;
  }}
  .hidden {{ display:none !important; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>📊 Gaika Monitor</h1>
    <div class="meta">Generated {now} · 直近2記事を表示 · ノーレバレッジ外貨取引大会</div>
    <div class="pill-row">
      <div class="stat-pill"><span class="num">{posted_count}</span> posted this week</div>
      <div class="stat-pill"><span class="num">{active_count}</span> active positions</div>
      <div class="stat-pill"><span class="num">{flagged_count}</span> flagged</div>
    </div>
  </div>
</header>

<div class="charts">
  <div class="chart-card">
    <h2>Market Bias (Long vs Short)</h2>
    <canvas id="dirChart"></canvas>
  </div>
  <div class="chart-card">
    <h2>Top Currencies Held</h2>
    <canvas id="curChart"></canvas>
  </div>
  <div class="chart-card">
    <h2>Post Status</h2>
    <canvas id="postChart"></canvas>
  </div>
</div>

<div class="table-wrap">
  <div class="controls">
    <input id="search" type="text" placeholder="チーム名 / 通貨ペアで検索…">
    <label><input type="checkbox" id="filterFlagged"> フラグのみ</label>
    <label><input type="checkbox" id="filterPosted"> 今週投稿のみ</label>
    <label><input type="checkbox" id="filterActive"> ポジションありのみ</label>
  </div>

  <table id="posTable">
    <thead>
      <tr>
        <th>チーム</th>
        <th>投稿日時</th>
        <th>タイトル</th>
        <th>通貨 / 方向</th>
        <th>エントリー</th>
        <th>ターゲット</th>
        <th>損切り</th>
        <th>戦略</th>
        <th>前週比の変化</th>
      </tr>
    </thead>
    <tbody id="tbody">
      {rows_html}
    </tbody>
  </table>
</div>

<script>
const RAW = {chart_data};

new Chart(document.getElementById('dirChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Long', 'Short', 'Neutral', 'Unknown'],
    datasets: [{{
      data: [RAW.directions.long, RAW.directions.short,
             RAW.directions.neutral, RAW.directions.unknown],
      backgroundColor: ['#22c55e','#ef4444','#94a3b8','#475569'],
      borderWidth: 0,
    }}]
  }},
  options: {{ plugins: {{ legend: {{ labels: {{ color:'#e6edf3', font:{{ size:11 }} }} }} }} }}
}});

new Chart(document.getElementById('curChart'), {{
  type: 'bar',
  data: {{
    labels: RAW.cur_labels,
    datasets: [{{
      label: 'Teams',
      data: RAW.cur_data,
      backgroundColor: '#58a6ff',
      borderWidth: 0,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    plugins: {{ legend: {{ display:false }} }},
    scales: {{
      x: {{ ticks:{{ color:'#8b949e' }}, grid:{{ color:'#21262d' }} }},
      y: {{ ticks:{{ color:'#e6edf3', font:{{ size:11 }} }}, grid:{{ display:false }} }}
    }}
  }}
}});

const postedSum = RAW.posted.reduce((a,b) => a+b, 0);
new Chart(document.getElementById('postChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['投稿あり', '未投稿'],
    datasets: [{{
      data: [postedSum, RAW.labels.length - postedSum],
      backgroundColor: ['#22c55e','#374151'],
      borderWidth: 0,
    }}]
  }},
  options: {{ plugins: {{ legend: {{ labels: {{ color:'#e6edf3', font:{{ size:11 }} }} }} }} }}
}});

const tbody   = document.getElementById('tbody');
const search  = document.getElementById('search');
const chkFlag = document.getElementById('filterFlagged');
const chkPost = document.getElementById('filterPosted');
const chkActive = document.getElementById('filterActive');

function buildGroups() {{
  const groups = {{}};
  for (const row of tbody.querySelectorAll('tr')) {{
    const tid = row.dataset.team;
    if (!groups[tid]) groups[tid] = [];
    groups[tid].push(row);
  }}
  return groups;
}}
const GROUPS = buildGroups();

function filter() {{
  const q      = search.value.toLowerCase();
  const flag   = chkFlag.checked;
  const post   = chkPost.checked;
  const active = chkActive.checked;
  for (const [, rows] of Object.entries(GROUPS)) {{
    const first    = rows[0];
    const text     = rows.map(r => r.textContent).join(' ').toLowerCase();
    const isFlagged = first.classList.contains('row-flagged');
    const isNoPost  = first.classList.contains('row-nopost');
    // "active" = has a non-"—" entry price somewhere
    const hasEntry  = text.includes('jpy') || text.includes('/');
    const matchQ      = !q      || text.includes(q);
    const matchFlag   = !flag   || isFlagged;
    const matchPost   = !post   || !isNoPost;
    const matchActive = !active || hasEntry;
    const hide = !(matchQ && matchFlag && matchPost && matchActive);
    rows.forEach(r => r.classList.toggle('hidden', hide));
  }}
}}

search.addEventListener('input', filter);
chkFlag.addEventListener('change', filter);
chkPost.addEventListener('change', filter);
chkActive.addEventListener('change', filter);
</script>
</body>
</html>"""


def main():
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found.", flush=True)
        raise SystemExit(1)
    teams = json.loads(INPUT.read_text(encoding="utf-8"))
    html = build_html(teams)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Report written → {OUTPUT}  ({len(teams)} teams)")


if __name__ == "__main__":
    main()
