import csv
from datetime import datetime, timezone, timedelta
from typing import Any

import yfinance as yf

TZ_TAIPEI = timezone(timedelta(hours=8))


def now_taipei() -> str:
    return datetime.now(TZ_TAIPEI).isoformat()


def _load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fetch_field(tickers: list[str], field: str) -> dict[str, float]:
    data = yf.Tickers(" ".join(tickers))
    result: dict[str, float] = {}
    for ticker in tickers:
        try:
            result[ticker] = float(data.tickers[ticker].fast_info[field])
        except (KeyError, TypeError, ValueError):
            pass
    return result


def _fetch_prices(tickers: list[str]) -> dict[str, float]:
    """Batch-fetch last prices for all tickers. Returns {ticker: price}."""
    return _fetch_field(tickers, "lastPrice")


def fetch_prev_closes(tickers: list[str]) -> dict[str, float]:
    """Batch-fetch previous close prices. Returns {ticker: prev_close}."""
    return _fetch_field(tickers, "previousClose")


def fetch_intraday_context(tickers: list[str]) -> dict[str, dict]:
    """Batch-fetch intraday price context from fast_info. Returns {ticker: {open, day_high, day_low, year_high, year_low, last_volume, avg_volume_10d}}."""
    if not tickers:
        return {}
    data = yf.Tickers(" ".join(tickers))
    result: dict[str, dict] = {}
    for ticker in tickers:
        try:
            fi = data.tickers[ticker].fast_info
            result[ticker] = {
                "open": float(fi["open"]),
                "day_high": float(fi["day_high"]),
                "day_low": float(fi["day_low"]),
                "year_high": float(fi["year_high"]),
                "year_low": float(fi["year_low"]),
                "last_volume": int(fi["last_volume"]),
                "avg_volume_10d": int(fi["ten_day_average_volume"]),
            }
        except (KeyError, TypeError, ValueError):
            pass
    return result


def compute_summary(csv_path: str) -> dict[str, Any]:
    rows = _load_csv(csv_path)
    market_rows = [r for r in rows if not r["ticker"].startswith("CASH_")]
    cash_rows = [r for r in rows if r["ticker"].startswith("CASH_")]

    market_tickers = [r["ticker"] for r in market_rows]
    prices = _fetch_prices(market_tickers + ["TWD=X"])
    fx_rate: float | None = prices.pop("TWD=X", None)
    intraday = fetch_intraday_context(market_tickers)

    positions = []
    errors = []

    for row in cash_rows:
        ticker = row["ticker"]
        shares = float(row["shares"])
        cost_price = float(row["cost_price"])
        face_value = round(shares * cost_price, 2)
        positions.append(
            {
                "ticker": ticker,
                "name": row["name"],
                "category": row["category"],
                "shares": shares,
                "cost_price": cost_price,
                "current_price": cost_price,
                "currency": row["currency"],
                "cost_value": face_value,
                "current_value": face_value,
                "gain_loss": 0.0,
                "gain_loss_pct": 0.0,
                "is_cash": True,
                "pct_of_currency_total": 0.0,
                "pct_of_global_usd": None,
            }
        )

    for row in market_rows:
        ticker = row["ticker"]
        shares = float(row["shares"])
        cost_price = float(row["cost_price"])
        currency = row["currency"]

        if ticker not in prices:
            errors.append({"ticker": ticker, "reason": "Failed to fetch price"})
            continue

        current_price = prices[ticker]
        cost_value = shares * cost_price
        current_value = shares * current_price
        gain_loss = current_value - cost_value
        gain_loss_pct = (gain_loss / cost_value * 100) if cost_value else 0.0

        ctx = intraday.get(ticker, {})
        open_price = ctx.get("open")
        year_high = ctx.get("year_high")
        year_low = ctx.get("year_low")
        avg_vol = ctx.get("avg_volume_10d")
        last_vol = ctx.get("last_volume")

        from_open_pct: float | None = None
        if open_price and open_price > 0:
            from_open_pct = round((current_price - open_price) / open_price * 100, 2)

        at_52w_high: bool | None = None
        if year_high and year_high > 0:
            at_52w_high = current_price >= year_high * 0.98

        volume_ratio: float | None = None
        if avg_vol and avg_vol > 0 and last_vol is not None:
            volume_ratio = round(last_vol / avg_vol, 2)

        positions.append(
            {
                "ticker": ticker,
                "name": row["name"],
                "category": row["category"],
                "shares": shares,
                "cost_price": cost_price,
                "current_price": current_price,
                "open": open_price,
                "day_high": ctx.get("day_high"),
                "day_low": ctx.get("day_low"),
                "from_open_pct": from_open_pct,
                "year_high": year_high,
                "year_low": year_low,
                "at_52w_high": at_52w_high,
                "volume_ratio": volume_ratio,
                "currency": currency,
                "cost_value": round(cost_value, 2),
                "current_value": round(current_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_pct": round(gain_loss_pct, 2),
                "is_cash": False,
                # allocation fields filled in after totals are known
                "pct_of_currency_total": 0.0,
                "pct_of_global_usd": None,
            }
        )

    # Group by currency -> category
    by_currency: dict[str, dict[str, Any]] = {}
    for p in positions:
        cur = p["currency"]
        cat = p["category"]
        if cur not in by_currency:
            by_currency[cur] = {
                "by_category": {},
                "total_cost": 0.0,
                "total_value": 0.0,
            }
        bc = by_currency[cur]
        if cat not in bc["by_category"]:
            bc["by_category"][cat] = {"cost": 0.0, "value": 0.0}
        bc["by_category"][cat]["cost"] += p["cost_value"]
        bc["by_category"][cat]["value"] += p["current_value"]
        bc["total_cost"] += p["cost_value"]
        bc["total_value"] += p["current_value"]

    for cur, bc in by_currency.items():
        for cat, v in bc["by_category"].items():
            gl = v["value"] - v["cost"]
            v["gain_loss"] = round(gl, 2)
            v["gain_loss_pct"] = round(gl / v["cost"] * 100, 2) if v["cost"] else 0.0
            v["cost"] = round(v["cost"], 2)
            v["value"] = round(v["value"], 2)
            # category allocation within currency
            v["pct_of_currency_total"] = round(v["value"] / bc["total_value"] * 100, 2) if bc["total_value"] else 0.0
        total_gl = bc["total_value"] - bc["total_cost"]
        bc["total_gain_loss"] = round(total_gl, 2)
        bc["total_gain_loss_pct"] = round(total_gl / bc["total_cost"] * 100, 2) if bc["total_cost"] else 0.0
        bc["total_cost"] = round(bc["total_cost"], 2)
        bc["total_value"] = round(bc["total_value"], 2)

    # Global USD allocation (requires fx_rate for TWD -> USD conversion)
    global_total_usd: float | None = None
    currency_pct: dict[str, float] | None = None

    if fx_rate and fx_rate > 0:
        usd_totals: dict[str, float] = {}
        for cur, bc in by_currency.items():
            val = bc["total_value"]
            usd_totals[cur] = val / fx_rate if cur == "TWD" else val
        global_total_usd = sum(usd_totals.values())

        if global_total_usd > 0:
            currency_pct = {cur: round(usd_val / global_total_usd * 100, 2) for cur, usd_val in usd_totals.items()}
            # Per-position global pct
            for p in positions:
                val_usd = p["current_value"] / fx_rate if p["currency"] == "TWD" else p["current_value"]
                p["pct_of_global_usd"] = round(val_usd / global_total_usd * 100, 2)

    # Per-position currency pct
    for p in positions:
        cur_total = by_currency.get(p["currency"], {}).get("total_value", 0.0)
        p["pct_of_currency_total"] = round(p["current_value"] / cur_total * 100, 2) if cur_total else 0.0

    return {
        "positions": positions,
        "by_currency": by_currency,
        "fx_rate": fx_rate,
        "global_total_usd": round(global_total_usd, 2) if global_total_usd is not None else None,
        "currency_pct": currency_pct,
        "fetched_at": now_taipei(),
        "errors": errors,
    }
