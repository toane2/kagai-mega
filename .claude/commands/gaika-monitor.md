# Gaika Trading Position Monitor

Monitor this week's trading positions from all 22 Gaika game participants via their note.com articles.

## Steps

### 1. Fetch the latest articles
```bash
python scripts/fetch_articles.py
```
This writes `output/articles.json` — one entry per team with their raw article text (or a "no post" flag).

### 2. Analyze each article
For each team that has posted this week, carefully extract:
- **Assets/currencies held**: name every instrument mentioned (e.g. USD/JPY, gold, BTC)
- **Entry price** and **exit price or target** if stated
- **Position size or leverage** (%, lot size, or any leverage ratio)
- **Strategy summary**: one sentence describing their stated approach
- **Notable changes** from previous weeks if the author mentions any

For teams with no post, set `has_post: false`.

### 3. Flag anomalies — mark any team where:
- Leverage is explicitly 10× or higher → flag `high_leverage`
- A single position is described as >50% of portfolio → flag `large_position`
- Their current trade contradicts their stated strategy (e.g. "long-term holder" with a same-day reversal) → flag `strategy_mismatch`

### 4. Generate the visual report
```bash
python scripts/generate_report.py
```
This writes `output/report.html`. Open it in a browser.

### 5. Present a concise summary
After the report is generated, respond with:
- A markdown table (team | assets | entry→target | flags)
- A 2–3 sentence paragraph on the most notable patterns across the whole group

## Teams
| Handle | note.com URL |
|--------|-------------|
| cool_parrot6215 | https://note.com/cool_parrot6215 |
| gaikafuru | https://note.com/gaikafuru |
| kiajobhunting | https://note.com/kiajobhunting |
| gakusei_kangae | https://note.com/gakusei_kangae |
| masashi_uclab | https://note.com/masashi_uclab |
| keylink_by_kk | https://note.com/keylink_by_kk |
| atsuya_044 | https://note.com/atsuya_044 |
| joyful_turtle486 | https://note.com/joyful_turtle486 |
| kanno_wmori | https://note.com/kanno_wmori |
| saku03081 | https://note.com/saku03081 |
| re_0oji | https://note.com/re_0oji |
| yuyu10y | https://note.com/yuyu10y |
| mtk____ | https://note.com/mtk____ |
| mafty_navueerin | https://note.com/mafty_navueerin |
| kyoichi_osaka | https://note.com/kyoichi_osaka |
| toshiki_naka | https://note.com/toshiki_naka |
| tomoro_0726 | https://note.com/tomoro_0726 |
| lovely_rue455 | https://note.com/lovely_rue455 |
| ionub | https://note.com/ionub |
| legal_wren2006 | https://note.com/legal_wren2006 |
| nasgor | https://note.com/nasgor |
| fast_crocus9353 | https://note.com/fast_crocus9353 |
