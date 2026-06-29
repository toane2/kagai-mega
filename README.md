# Gaika Trading Monitor

Monitors all 22 Gaika game participants weekly by reading their latest note.com articles,
extracting positions, and producing a visual HTML dashboard.

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Open the folder in Claude Code
cd gaika-monitor
claude .
```

Then type the slash command in Claude Code:

```
/gaika-monitor
```

Claude will:
1. Run `scripts/fetch_articles.py` → scrapes note.com and saves `output/articles.json`
2. Analyze each article for positions, leverage, strategy, and flags
3. Write `output/analyzed_positions.json` with the structured data
4. Run `scripts/generate_report.py` → builds `output/report.html`
5. Print a markdown summary table in chat

Open `output/report.html` in a browser for the full visual dashboard.

---

## Output files

| File | Description |
|------|-------------|
| `output/articles.json` | Raw scraped articles (title, body, date) per team |
| `output/analyzed_positions.json` | Structured positions extracted by Claude |
| `output/report.html` | Self-contained visual dashboard |

## Flags

| Flag | Condition |
|------|-----------|
| `high_leverage` | Leverage ≥ 10× explicitly mentioned |
| `large_position` | Single asset > 50 % of portfolio |
| `strategy_mismatch` | Current trade contradicts stated strategy |

## Running on a schedule (optional)

Add to crontab to run every Monday morning at 9 AM JST (00:00 UTC):

```cron
0 0 * * 1  cd /path/to/gaika-monitor && python scripts/fetch_articles.py
```

After fetching, open Claude Code and run `/gaika-monitor` to complete the analysis.

---

## Teams monitored

| # | Handle |
|---|--------|
| 1 | cool_parrot6215 |
| 2 | gaikafuru |
| 3 | kiajobhunting |
| 4 | gakusei_kangae |
| 5 | masashi_uclab |
| 6 | keylink_by_kk |
| 7 | atsuya_044 |
| 8 | joyful_turtle486 |
| 9 | kanno_wmori |
| 10 | saku03081 |
| 11 | re_0oji |
| 12 | yuyu10y |
| 13 | mtk____ |
| 14 | mafty_navueerin |
| 15 | kyoichi_osaka |
| 16 | toshiki_naka |
| 17 | tomoro_0726 |
| 18 | lovely_rue455 |
| 19 | ionub |
| 20 | legal_wren2006 |
| 21 | nasgor |
| 22 | fast_crocus9353 |
