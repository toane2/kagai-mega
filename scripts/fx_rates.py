"""
fx_rates.py — historical/current FX rate lookup (JPY per 1 unit of currency)
=============================================================================
Used by generate_report.py to mark self-reported holdings to market: a
team's last article may be days old, but the leaderboard needs today's
value. Rates come from the Frankfurter API (ECB daily reference rates,
free, no key) and are cached to data/fx_rates.json — historical dates
never change so they're cached forever; "latest" is refetched once per
process run.
"""

import json
import urllib.request
from pathlib import Path

FX_CACHE = Path("data/fx_rates.json")
FX_SYMBOLS = ["USD", "EUR", "GBP", "AUD", "CNY", "CHF", "SEK", "NZD", "CAD", "HKD", "ZAR"]

_cache: dict = {}
_loaded = False
_dirty = False
_latest_fetched = False


def _load():
    global _cache, _loaded
    if _loaded:
        return
    if FX_CACHE.exists():
        try:
            _cache = json.loads(FX_CACHE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    _loaded = True


def _fetch(date_key: str) -> dict:
    url = f"https://api.frankfurter.dev/v1/{date_key}?base=JPY&symbols={','.join(FX_SYMBOLS)}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode())
    # base=JPY gives "units of X per 1 JPY" — invert to "JPY per 1 unit of X"
    return {cur: (1.0 / rate) for cur, rate in data.get("rates", {}).items() if rate}


def get_rate(date_str: str | None, currency: str) -> float | None:
    """JPY value of 1 unit of `currency` on `date_str` (YYYY-MM-DD), or the
    latest available rate if date_str is None. Returns None if the rate
    can't be determined (offline, unknown currency, etc.) so callers can
    fall back to the self-reported figure."""
    global _dirty, _latest_fetched
    _load()
    currency = currency.upper()
    if currency == "JPY":
        return 1.0

    key = date_str or "latest"
    if key == "latest":
        if not _latest_fetched:
            try:
                _cache["latest"] = _fetch("latest")
                _dirty = True
            except Exception:
                pass
            _latest_fetched = True
    elif key not in _cache:
        try:
            _cache[key] = _fetch(key)
            _dirty = True
        except Exception:
            return None

    return _cache.get(key, {}).get(currency)


def flush():
    """Persist any newly-fetched rates to disk."""
    global _dirty
    if _dirty:
        FX_CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        _dirty = False
