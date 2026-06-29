# Gaika Trading Position Monitor

Monitor the 22 Gaika game participants via their note.com articles.
No-leverage foreign exchange competition (ソニー銀行). 10 weeks, 100,000 JPY starting capital.

## Workflow

### 1. Fetch new articles
```bash
PYTHONIOENCODING=utf-8 python scripts/fetch_articles.py
```
Adds only NEW articles (not already in `data/article_log.json`) to the log. Existing entries preserved.

### 2. Analyze unanalyzed articles

Read `data/article_log.json`. Find all entries where `"analyzed": false`.

For each such entry, fill the `analysis` field. Then set `"analyzed": true`.

**Relevance check first:**
- If the article is clearly NOT about the competition (e.g. travel blog, paid investment guide, corporate analysis, unrelated topics), set `"relevant": false` and `"analyzed": true`. Leave `analysis` as null. Skip further analysis.
- If the article is about the competition, an intro post stating their stance, or any mention of holdings/trades: set `"relevant": true`.

**For relevant articles, extract:**

```json
"analysis": {
  "trades": [
    {
      "from_currency": "JPY",
      "to_currency": "EUR",
      "rate": 184.94,
      "amount_from_jpy": 100000,
      "date": "2026-06-23"
    }
  ],
  "holdings": [
    {"currency": "EUR", "amount_jpy": 99788},
    {"currency": "JPY", "amount_jpy": 0}
  ],
  "intent": "円安継続を見込みEURにオールイン、目標186円",
  "changes_since_prev": null
}
```

**Rules:**
- `rate`: exact number stated in the article. Null if not explicitly given.
- `amount_from_jpy`: exact JPY amount spent. If they say "1万円分 USD を購入" → 10000. If they say "全額ユーロに" → 100000.
- Infer remaining holdings from context: if "1万円分だけ買った" and no prior trades → JPY: 90000, target currency: 10000.
- `holdings` should reflect state at end of article. If they sold everything and returned to JPY, show JPY only.
- `intent`: 1-2 brief phrases in Japanese. Just their stated reason and position. No background, no story.
  Examples: "USD/JPY押し目待ち、介入後エントリー狙い" / "AIの指示に全従、EUR全額保有" / "様子見、キャッシュ保持"
- `changes_since_prev`: for this team's articles, if this article is NOT the team's oldest in the log, briefly note what changed since the previous article. Otherwise null.

**Do NOT:**
- Quote the article text
- Explain their background or story
- Add context beyond what they explicitly stated
- Guess rates not written as numbers

### 3. Write updated log
Save the modified `data/article_log.json` with all analyzed entries filled.

### 4. Generate report
```bash
PYTHONIOENCODING=utf-8 python scripts/generate_report.py
```

### 5. Summarize
After the report, give a brief markdown table:

| チーム | 保有 | 直近取引 | 意図 |
|--------|------|----------|------|

Then 2-3 sentences on notable patterns.

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
