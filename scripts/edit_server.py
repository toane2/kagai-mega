"""
edit_server.py  —  Local manual-correction editor for Gaika Monitor
====================================================================
Serves an editable view of data/article_log.json so figures can be
corrected by hand while looking at the original article + its screenshots
side by side. Saves go straight to article_log.json (the source of truth).

Usage:
    python scripts/edit_server.py [port]
    then open http://localhost:8765/  (default port 8765)

Each article can be expanded to show its body text and screenshot images,
with editable holdings/trades/intent fields and a Save button that writes
back to data/article_log.json immediately. A "Regenerate report" button
reruns generate_report.py after edits.
"""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = Path("data/article_log.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

_lock = threading.Lock()


def load_log() -> dict:
    return json.loads(LOG.read_text(encoding="utf-8"))


def save_log(log: dict) -> None:
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def render_page() -> str:
    log = load_log()
    articles = log["articles"]

    by_team = {}
    for url, a in articles.items():
        if not a.get("relevant"):
            continue
        by_team.setdefault(a["username"], []).append(a)
    for team in by_team:
        by_team[team].sort(key=lambda a: a.get("post_date") or "")

    data_json = json.dumps(articles, ensure_ascii=False)

    team_sections = []
    for team in sorted(by_team):
        arts = by_team[team]
        cards = []
        for a in arts:
            url = a["url"]
            uid = url.replace("https://note.com/", "").replace("/", "_")
            imgs = a.get("images", [])
            img_html = "".join(
                f'<a href="{im}" target="_blank"><img src="{im}" loading="lazy" class="thumb"></a>'
                for im in imgs
            )
            cards.append(f'''
      <div class="card" data-url="{esc(url)}">
        <div class="card-head">
          <a href="{esc(url)}" target="_blank" class="title">{esc(a.get("title") or url)}</a>
          <span class="date">{esc(a.get("post_date") or "")}</span>
        </div>
        <details>
          <summary>本文 / 画像 ({len(imgs)})</summary>
          <div class="body-text">{esc(a.get("body") or "")}</div>
          <div class="imgs">{img_html or '<span class="muted">(no images)</span>'}</div>
        </details>
        <div class="editor" id="editor-{uid}"></div>
        <div class="save-row">
          <button onclick="saveArticle('{esc(url)}')">Save</button>
          <span class="save-status" id="status-{uid}"></span>
        </div>
      </div>''')
        team_sections.append(f'''
    <section class="team">
      <h2 class="team-toggle" onclick="toggleTeam(this)" data-team="{esc(team)}">
        <span class="chevron">▸</span> @{esc(team)} <span class="count">({len(arts)})</span>
      </h2>
      <div class="team-body" style="display:none">
        {"".join(cards)}
      </div>
    </section>''')

    return HTML_TEMPLATE.replace("__DATA__", data_json).replace("__TEAMS__", "".join(team_sections))


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


HTML_TEMPLATE = '''<!doctype html>
<html><head><meta charset="utf-8">
<title>Gaika Monitor — Manual Editor</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; background:#0f1115; color:#e5e7eb; margin:0; padding:20px 24px 80px; }
  h1 { font-size:20px; }
  h2 { font-size:16px; border-bottom:1px solid #2a2e37; padding-bottom:6px; margin-top:20px; color:#93c5fd; }
  .team-toggle { cursor:pointer; user-select:none; display:flex; align-items:center; gap:6px; }
  .team-toggle:hover { color:#bfdbfe; }
  .team-toggle .chevron { display:inline-block; transition:transform .15s; font-size:12px; }
  .team-toggle.open .chevron { transform:rotate(90deg); }
  .team-toggle .count { color:#6b7280; font-size:12px; font-weight:normal; }
  .toolbar { position:sticky; top:0; background:#0f1115; padding:10px 0; z-index:10; display:flex; gap:10px; align-items:center; border-bottom:1px solid #2a2e37;}
  .card { background:#181b21; border:1px solid #2a2e37; border-radius:8px; padding:12px 14px; margin:10px 0; }
  .card-head { display:flex; justify-content:space-between; gap:10px; margin-bottom:6px; }
  .title { color:#e5e7eb; text-decoration:none; font-weight:600; }
  .title:hover { text-decoration:underline; }
  .date { color:#9ca3af; font-size:12px; white-space:nowrap; }
  details { margin:6px 0 10px; }
  summary { cursor:pointer; color:#9ca3af; font-size:13px; }
  .body-text { white-space:pre-wrap; font-size:13px; color:#c7cad1; background:#0f1115; padding:8px 10px; border-radius:6px; margin:8px 0; max-height:240px; overflow:auto; }
  .imgs { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }
  .thumb { max-height:220px; max-width:320px; border-radius:6px; border:1px solid #2a2e37; }
  .muted { color:#6b7280; font-size:12px; }
  table.hold { border-collapse:collapse; margin:6px 0; }
  table.hold td { padding:3px 6px; }
  input[type=text], input[type=number], input[type=date] {
    background:#0f1115; border:1px solid #374151; color:#e5e7eb; border-radius:4px; padding:4px 6px; font-size:13px;
  }
  input.currency { width:70px; }
  input.amount { width:110px; }
  .row-btn { background:none; border:none; color:#9ca3af; cursor:pointer; font-size:14px; }
  .row-btn:hover { color:#f87171; }
  .add-btn { background:#1f2937; border:1px solid #374151; color:#93c5fd; border-radius:4px; padding:3px 10px; font-size:12px; cursor:pointer; margin-top:4px; }
  label.f { display:block; font-size:11px; color:#9ca3af; margin:8px 0 2px; }
  .intent-input, .changes-input { width:100%; box-sizing:border-box; }
  .trades-block { margin-top:10px; padding-top:8px; border-top:1px dashed #2a2e37; }
  .trade-row { display:flex; gap:6px; align-items:center; margin:3px 0; flex-wrap:wrap; }
  .save-row { display:flex; gap:10px; align-items:center; margin-top:10px; }
  button { background:#2563eb; border:none; color:white; border-radius:6px; padding:6px 14px; font-size:13px; cursor:pointer; }
  button:hover { background:#1d4ed8; }
  .save-status { font-size:12px; color:#34d399; }
  .save-status.err { color:#f87171; }
</style>
</head>
<body>
  <div class="toolbar">
    <h1 style="margin:0">Gaika Monitor — Manual Editor</h1>
    <button onclick="regenerate()">Regenerate report.html</button>
    <span id="regen-status" class="save-status"></span>
    <span style="flex:1"></span>
    <button onclick="setAllTeams(true)">Expand all</button>
    <button onclick="setAllTeams(false)">Collapse all</button>
  </div>
  <p class="muted">Edits save straight to data/article_log.json. Expand an article to see its body + screenshots, correct the fields below, then Save. Click "Regenerate report.html" when done with a batch.</p>
  __TEAMS__

<script>
const ARTICLES = __DATA__;

function currentSet() { return ["JPY","USD","EUR","GBP","AUD","NZD","CAD","CHF","CNY","SEK"]; }

function mkHoldingsTable(uid, holdings) {
  let rows = holdings.map((h,i) => holdingRow(uid, i, h.currency, h.amount_jpy)).join("");
  return `<label class="f">Holdings (currency / amount in JPY)</label>
    <table class="hold" id="hold-${uid}">${rows}</table>
    <button type="button" class="add-btn" onclick="addHoldingRow('${uid}')">+ add currency</button>`;
}
function holdingRow(uid, i, cur, amt) {
  return `<tr data-i="${i}">
    <td><input type="text" class="currency" value="${cur||''}"></td>
    <td><input type="number" class="amount" value="${amt==null?'':amt}"></td>
    <td><button type="button" class="row-btn" onclick="this.closest('tr').remove()">✕</button></td>
  </tr>`;
}
function addHoldingRow(uid) {
  const tbl = document.getElementById('hold-'+uid);
  const i = tbl.rows.length;
  tbl.insertAdjacentHTML('beforeend', holdingRow(uid, i, '', ''));
}

function mkTradesBlock(uid, trades) {
  let rows = trades.map((t,i) => tradeRow(uid, i, t)).join("");
  return `<div class="trades-block" id="trades-${uid}">
    <label class="f">Trades</label>
    ${rows}
    <button type="button" class="add-btn" onclick="addTradeRow('${uid}')">+ add trade</button>
  </div>`;
}
function tradeRow(uid, i, t) {
  t = t || {};
  return `<div class="trade-row" data-i="${i}">
    <input type="text" class="currency from" placeholder="from" value="${t.from_currency||''}" style="width:60px">
    →
    <input type="text" class="currency to" placeholder="to" value="${t.to_currency||''}" style="width:60px">
    <input type="number" class="amount amt" placeholder="amount_from_jpy" value="${t.amount_from_jpy==null?'':t.amount_from_jpy}" style="width:110px">
    <input type="number" class="rate" placeholder="rate" step="0.01" value="${t.rate==null?'':t.rate}" style="width:80px">
    <input type="text" class="tdate" placeholder="YYYY-MM-DD" value="${t.date||''}" style="width:100px">
    <button type="button" class="row-btn" onclick="this.closest('.trade-row').remove()">✕</button>
  </div>`;
}
function addTradeRow(uid) {
  const block = document.getElementById('trades-'+uid);
  const i = block.querySelectorAll('.trade-row').length;
  const frag = document.createRange().createContextualFragment(tradeRow(uid, i, {}));
  block.insertBefore(frag, block.querySelector('.add-btn'));
}

function buildEditor(url) {
  const a = ARTICLES[url];
  const uid = url.replace('https://note.com/','').replace(/\\//g,'_');
  const an = a.analysis || {trades:[], holdings:[], intent:'', changes_since_prev:''};
  const el = document.getElementById('editor-'+uid);
  el.innerHTML = `
    ${mkHoldingsTable(uid, an.holdings||[])}
    ${mkTradesBlock(uid, an.trades||[])}
    <label class="f">Intent</label>
    <input type="text" class="intent-input" id="intent-${uid}" value="${(an.intent||'').replace(/"/g,'&quot;')}">
    <label class="f">Changes since prev</label>
    <input type="text" class="changes-input" id="changes-${uid}" value="${(an.changes_since_prev||'').replace(/"/g,'&quot;')}">
  `;
}

document.querySelectorAll('.card').forEach(card => buildEditor(card.dataset.url));

const OPEN_KEY = 'gaika-editor-open-teams';
function getOpenTeams() {
  try { return new Set(JSON.parse(localStorage.getItem(OPEN_KEY) || '[]')); }
  catch(e) { return new Set(); }
}
function setOpenTeams(set) {
  localStorage.setItem(OPEN_KEY, JSON.stringify([...set]));
}
function applyTeamState(h2, open) {
  const body = h2.nextElementSibling;
  body.style.display = open ? '' : 'none';
  h2.classList.toggle('open', open);
}
function toggleTeam(h2) {
  const team = h2.dataset.team;
  const opened = getOpenTeams();
  const nowOpen = !h2.classList.contains('open');
  if (nowOpen) opened.add(team); else opened.delete(team);
  setOpenTeams(opened);
  applyTeamState(h2, nowOpen);
}
function setAllTeams(open) {
  const opened = getOpenTeams();
  document.querySelectorAll('.team-toggle').forEach(h2 => {
    applyTeamState(h2, open);
    if (open) opened.add(h2.dataset.team); else opened.delete(h2.dataset.team);
  });
  setOpenTeams(opened);
}
(function restoreTeamState() {
  const opened = getOpenTeams();
  document.querySelectorAll('.team-toggle').forEach(h2 => {
    applyTeamState(h2, opened.has(h2.dataset.team));
  });
})();

function readHoldings(uid) {
  const tbl = document.getElementById('hold-'+uid);
  const out = [];
  for (const tr of tbl.rows) {
    const cur = tr.querySelector('.currency').value.trim().toUpperCase();
    const amtVal = tr.querySelector('.amount').value;
    if (!cur) continue;
    out.push({currency: cur, amount_jpy: amtVal === '' ? null : Number(amtVal)});
  }
  return out;
}
function readTrades(uid) {
  const block = document.getElementById('trades-'+uid);
  const out = [];
  for (const row of block.querySelectorAll('.trade-row')) {
    const from_c = row.querySelector('.from').value.trim().toUpperCase();
    const to_c = row.querySelector('.to').value.trim().toUpperCase();
    if (!from_c && !to_c) continue;
    const amt = row.querySelector('.amt').value;
    const rate = row.querySelector('.rate').value;
    const date = row.querySelector('.tdate').value.trim();
    out.push({
      from_currency: from_c, to_currency: to_c,
      amount_from_jpy: amt === '' ? null : Number(amt),
      rate: rate === '' ? null : Number(rate),
      date: date || null,
    });
  }
  return out;
}

async function saveArticle(url) {
  const uid = url.replace('https://note.com/','').replace(/\\//g,'_');
  const analysis = {
    holdings: readHoldings(uid),
    trades: readTrades(uid),
    intent: document.getElementById('intent-'+uid).value,
    changes_since_prev: document.getElementById('changes-'+uid).value || null,
  };
  const statusEl = document.getElementById('status-'+uid);
  statusEl.textContent = 'saving...';
  statusEl.className = 'save-status';
  try {
    const res = await fetch('/save', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url, analysis}),
    });
    const j = await res.json();
    if (j.ok) {
      statusEl.textContent = 'saved ' + new Date().toLocaleTimeString();
      ARTICLES[url].analysis = analysis;
    } else {
      statusEl.textContent = 'error: ' + j.error;
      statusEl.className = 'save-status err';
    }
  } catch (e) {
    statusEl.textContent = 'error: ' + e;
    statusEl.className = 'save-status err';
  }
}

async function regenerate() {
  const el = document.getElementById('regen-status');
  el.textContent = 'running...';
  el.className = 'save-status';
  try {
    const res = await fetch('/regenerate', {method:'POST'});
    const j = await res.json();
    el.textContent = j.ok ? 'report regenerated ✓' : ('error: ' + j.error);
    el.className = j.ok ? 'save-status' : 'save-status err';
  } catch(e) {
    el.textContent = 'error: ' + e;
    el.className = 'save-status err';
  }
}
</script>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "":
            body = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if self.path == "/save":
            try:
                payload = json.loads(raw)
                url = payload["url"]
                analysis = payload["analysis"]
                with _lock:
                    log = load_log()
                    if url not in log["articles"]:
                        raise KeyError(f"unknown url {url}")
                    log["articles"][url]["analysis"] = analysis
                    log["articles"][url]["analyzed"] = True
                    save_log(log)
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(200, {"ok": False, "error": str(e)})
        elif self.path == "/regenerate":
            try:
                result = subprocess.run(
                    [sys.executable, "scripts/generate_report.py"],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    self._json(200, {"ok": True, "output": result.stdout})
                else:
                    self._json(200, {"ok": False, "error": result.stderr or result.stdout})
            except Exception as e:
                self._json(200, {"ok": False, "error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"Gaika Monitor editor running at http://localhost:{PORT}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
