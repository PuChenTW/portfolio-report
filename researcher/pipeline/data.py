from datetime import datetime

from portfolio.portfolio import compute_summary, fetch_prev_closes, TZ_TAIPEI
from portfolio.report import USHolding, TWHolding, CryptoHolding
from researcher.config import settings

WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _fmt_today() -> str:
    now = datetime.now(TZ_TAIPEI)
    return f"{now.year} 年 {now.month:02d} 月 {now.day:02d} 日（{WEEKDAY_ZH[now.weekday()]}）"


def _fmt_change(pct: float) -> tuple[str, bool]:
    up = pct >= 0
    arrow = "▲ +" if up else "▼ "
    return f"{arrow}{abs(pct):.2f}% 今日", up


def _fmt_usd(value: float) -> str:
    return f"${value:,.0f}"


def _fmt_twd(value: float) -> str:
    return f"NT${value:,.0f}"


def fetch_portfolio() -> dict:
    """Fetch summary + previous closes in two batch calls."""
    summary = compute_summary(settings.portfolio_csv_path)
    tickers = [p["ticker"] for p in summary["positions"] if not p.get("is_cash")]
    prev_closes = fetch_prev_closes(tickers)
    return {"summary": summary, "prev_closes": prev_closes}


def build_holdings(
    data: dict,
) -> tuple[list[USHolding], list[TWHolding], list[CryptoHolding]]:
    positions = data["summary"]["positions"]
    prev_closes = data["prev_closes"]

    us_holdings: list[USHolding] = []
    tw_holdings: list[TWHolding] = []
    crypto_holdings: list[CryptoHolding] = []
    cash_tw: list[TWHolding] = []
    cash_us: list[USHolding] = []

    for p in positions:
        ticker = p["ticker"]
        current = p["current_price"]
        pct = p.get("pct_of_currency_total", 0.0)

        if p.get("is_cash"):
            if p["currency"] == "TWD":
                cash_tw.append(
                    TWHolding(
                        ticker=ticker,
                        name=p["name"],
                        price=_fmt_twd(p["current_value"]),
                        day_change="—",
                        day_change_up=False,
                        note="現金",
                        pct_of_currency=pct,
                    )
                )
            else:
                cash_us.append(
                    USHolding(
                        ticker=ticker,
                        name=p["name"],
                        category="CASH",
                        price=_fmt_usd(p["current_value"]),
                        day_change="—",
                        day_change_up=False,
                        gain_loss="—",
                        gain_loss_up=False,
                        pct_of_currency=pct,
                    )
                )
            continue

        prev = prev_closes.get(ticker)
        if prev and prev > 0:
            day_pct = (current - prev) / prev * 100
            day_change, day_change_up = _fmt_change(day_pct)
        else:
            day_change, day_change_up = "暫無數據", False

        gl_pct = p["gain_loss_pct"]
        gain_loss_up = gl_pct >= 0
        gl_sign = "+" if gain_loss_up else ""
        gain_loss = f"{gl_sign}{gl_pct:.2f}%"

        if p["currency"] == "TWD":
            tw_holdings.append(
                TWHolding(
                    ticker=ticker,
                    name=p["name"],
                    price=f"NT${current:,.0f}",
                    day_change=day_change,
                    day_change_up=day_change_up,
                    note="—",
                    pct_of_currency=pct,
                )
            )
        elif p["category"] == "加密貨幣":
            crypto_holdings.append(
                CryptoHolding(
                    ticker=ticker.replace("-USD", ""),
                    name=p["name"],
                    price=f"${current:,.2f}",
                    day_change=day_change,
                    day_change_up=day_change_up,
                    quantity=f"{p['shares']:.4f} 顆",
                    pct_of_currency=pct,
                )
            )
        else:
            tag_map = {"美股": "TECH", "美國ETF": "ETF"}
            category_tag = tag_map.get(p["category"], "ETF")
            us_holdings.append(
                USHolding(
                    ticker=ticker,
                    name=p["name"],
                    category=category_tag,
                    price=f"${current:.2f}",
                    day_change=day_change,
                    day_change_up=day_change_up,
                    gain_loss=gain_loss,
                    gain_loss_up=gain_loss_up,
                    pct_of_currency=pct,
                )
            )

    # Cash positions appear at the end of their respective sections
    tw_holdings.extend(cash_tw)
    us_holdings.extend(cash_us)

    return us_holdings, tw_holdings, crypto_holdings


def build_totals(data: dict) -> dict:
    by_currency = data["summary"]["by_currency"]
    twd = by_currency.get("TWD", {})
    usd = by_currency.get("USD", {})

    usd_categories = usd.get("by_category", {})
    crypto_value = usd_categories.get("加密貨幣", {}).get("value", 0.0)
    crypto_cost = usd_categories.get("加密貨幣", {}).get("cost", 0.0)
    us_value = usd.get("total_value", 0.0) - crypto_value
    us_cost = usd.get("total_cost", 0.0) - crypto_cost

    us_gl_pct = (us_value - us_cost) / us_cost * 100 if us_cost else 0.0
    crypto_gl_pct = (crypto_value - crypto_cost) / crypto_cost * 100 if crypto_cost else 0.0

    return {
        "tw_total": _fmt_twd(twd.get("total_value", 0.0)),
        "tw_change": _fmt_change(twd.get("total_gain_loss_pct", 0.0)),
        "us_total": _fmt_usd(us_value),
        "us_change": _fmt_change(us_gl_pct),
        "crypto_total": _fmt_usd(crypto_value),
        "crypto_change": _fmt_change(crypto_gl_pct),
    }
