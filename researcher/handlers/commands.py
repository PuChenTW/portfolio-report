import csv
import yaml
from pathlib import Path

from portfolio.watchlist import WatchlistEntry, add_ticker, load_watchlist, remove_ticker
from portfolio.alerts import load_alerts
from researcher.config import settings
from researcher.pipeline.data import fetch_portfolio, _fmt_usd, _fmt_twd


def handle_watchlist(args: list[str], watchlist_path: str = settings.watchlist_csv_path) -> str:
    if not args:
        return "Usage: /watchlist [add TICKER [note] | remove TICKER | list]"
    sub = args[0]
    if sub == "list":
        entries = load_watchlist(watchlist_path)
        if not entries:
            return "Watchlist is empty."
        lines = [f"• {e.ticker}  {e.name}" + (f"  — {e.note}" if e.note else "") for e in entries]
        return "Watchlist:\n" + "\n".join(lines)
    if sub == "add" and len(args) >= 2:
        ticker = args[1].upper()
        name = args[2] if len(args) > 2 else ticker
        note = " ".join(args[3:]) if len(args) > 3 else ""
        add_ticker(watchlist_path, WatchlistEntry(ticker=ticker, name=name, note=note))
        return f"Added {ticker} to watchlist."
    if sub == "remove" and len(args) >= 2:
        ticker = args[1].upper()
        remove_ticker(watchlist_path, ticker)
        return f"Removed {ticker} from watchlist."
    return "Usage: /watchlist [add TICKER [note] | remove TICKER | list]"


def handle_alert(args: list[str], alerts_path: str = settings.price_alerts_path) -> str:
    if not args:
        return "Usage: /alert [set TICKER above=X | set TICKER below=X | show [TICKER]]"
    sub = args[0]
    if sub == "show":
        rules = load_alerts(alerts_path)
        ticker = args[1].upper() if len(args) > 1 else None
        if ticker:
            override = rules.overrides.get(ticker, {})
            if not override:
                return f"No overrides for {ticker}. Defaults: {rules.defaults}"
            return f"{ticker} alerts: {override}"
        return f"Defaults: {rules.defaults}\nOverrides: {rules.overrides}"
    if sub == "set" and len(args) >= 3:
        ticker = args[1].upper()
        kv = args[2]
        if "=" not in kv:
            return "Usage: /alert set TICKER above=X or below=X"
        key, val = kv.split("=", 1)
        try:
            value = float(val)
        except ValueError:
            return f"Invalid value: {val}"
        p = Path(alerts_path)
        data: dict = {}
        if p.exists():
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        data.setdefault("overrides", {}).setdefault(ticker, {})[key] = value
        with p.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
        return f"Alert set: {ticker} {key} = {value}"
    return "Usage: /alert [set TICKER above=X | set TICKER below=X | show [TICKER]]"


def handle_holdings(args: list[str] = []) -> str:
    data = fetch_portfolio()
    positions = data["summary"]["positions"]
    prev_closes = data["prev_closes"]

    sections: dict[str, list[str]] = {"台股": [], "美股 / ETF": [], "加密貨幣": [], "現金": []}
    section_value: dict[str, float] = {"台股": 0.0, "美股 / ETF": 0.0, "加密貨幣": 0.0, "現金": 0.0}

    for p in positions:
        ticker = p["ticker"]
        current = p["current_price"]

        if p.get("is_cash"):
            val_str = _fmt_twd(p["current_value"]) if p["currency"] == "TWD" else _fmt_usd(p["current_value"])
            sections["現金"].append(
                f"<b>{p['name']}</b>  <code>{val_str}</code>"
            )
            continue

        prev = prev_closes.get(ticker)
        if prev and prev > 0:
            day_pct = (current - prev) / prev * 100
            day_arrow = "▲" if day_pct >= 0 else "▼"
            day_str = f"{day_arrow}{abs(day_pct):.2f}%"
        else:
            day_str = "—"

        gl_pct = p["gain_loss_pct"]
        gl_arrow = "▲" if gl_pct >= 0 else "▼"
        gl_str = f"{gl_arrow}{abs(gl_pct):.2f}%"

        display_ticker = ticker.replace("-USD", "").replace(".TW", "")

        if p["currency"] == "TWD":
            section = "台股"
            price_str = f"NT${current:,.0f}"
            section_value[section] += p["current_value"]
        elif p["category"] == "加密貨幣":
            section = "加密貨幣"
            price_str = f"${current:,.2f}"
            section_value[section] += p["current_value"]
        else:
            section = "美股 / ETF"
            price_str = f"${current:.2f}"
            section_value[section] += p["current_value"]

        sections[section].append(
            f"<b>{display_ticker}</b>  <code>{price_str}</code>  持倉 {gl_str}  今日 {day_str}"
        )

    fx_rate: float | None = data["summary"].get("fx_rate")

    lines: list[str] = []
    for section, rows in sections.items():
        if not rows:
            continue
        lines.append(f"<b>📊 {section}</b>")
        lines.extend(rows)
        val = section_value[section]
        if section == "台股":
            twd_str = _fmt_twd(val)
            usd_str = _fmt_usd(val / fx_rate) if fx_rate else "—"
            lines.append(f"<i>合計 {twd_str}  /  {usd_str}</i>")
        elif section in ("美股 / ETF", "加密貨幣"):
            usd_str = _fmt_usd(val)
            twd_str = _fmt_twd(val * fx_rate) if fx_rate else "—"
            lines.append(f"<i>合計 {usd_str}  /  {twd_str}</i>")
        lines.append("")

    return "\n".join(lines).strip()


def handle_update_holding(
    args: list[str],
    portfolio_path: str = settings.portfolio_csv_path,
) -> str:
    if len(args) < 3:
        return "Usage: /update TICKER SHARES COST"
    ticker = args[0].upper()
    try:
        shares = float(args[1])
        cost = float(args[2])
    except ValueError:
        return "SHARES and COST must be numbers."
    p = Path(portfolio_path)
    if not p.exists():
        return f"Portfolio file not found: {portfolio_path}"
    rows = []
    updated = False
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            if row["ticker"] == ticker:
                row["shares"] = str(shares)
                row["cost_price"] = str(cost)
                updated = True
            rows.append(row)
    if not updated:
        return f"Ticker {ticker} not found in portfolio."
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return f"Updated {ticker}: {shares} shares @ {cost}."


def handle_status() -> str:
    return "Researcher agent is running.\nUse /watchlist list or /alert show to check state."
