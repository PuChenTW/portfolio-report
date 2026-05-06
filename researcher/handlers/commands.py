import csv
import yaml
from pathlib import Path

from portfolio.watchlist import WatchlistEntry, add_ticker, load_watchlist, remove_ticker
from portfolio.alerts import load_alerts
from researcher.config import settings
from researcher.interfaces.ports import TransactionLog
from researcher.pipeline.data import fetch_portfolio, fmt_usd, fmt_twd


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


def _holdings_table(rows: list[tuple[str, str, str, str, str, str]]) -> str:
    """Render a fixed-width monospace table for Telegram <pre> blocks.

    Each row is (ticker, shares, price, cost, total, pnl).
    """
    header = ("Ticker", "股數", "現價", "成本", "市值", "損益")
    col_widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(header)]

    def fmt_row(cells: tuple[str, ...]) -> str:
        return "  ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells))

    sep = "  ".join("-" * w for w in col_widths)
    table_rows = [fmt_row(header), sep] + [fmt_row(r) for r in rows]
    return "\n".join(table_rows)


def handle_holdings() -> str:
    data = fetch_portfolio()
    positions = data["summary"]["positions"]
    fx_rate: float | None = data["summary"].get("fx_rate")

    sections: dict[str, list[tuple[str, str, str, str, str, str]]] = {"台股": [], "美股 / ETF": [], "加密貨幣": [], "現金": []}
    section_value: dict[str, float] = {"台股": 0.0, "美股 / ETF": 0.0, "加密貨幣": 0.0, "現金": 0.0}

    for p in positions:
        ticker = p["ticker"]
        display_ticker = ticker.replace("-USD", "").replace(".TW", "")

        if p.get("is_cash"):
            val_str = fmt_twd(p["current_value"]) if p["currency"] == "TWD" else fmt_usd(p["current_value"])
            sections["現金"].append((p["name"], "—", val_str, "—", "—", "—"))
            continue

        current = p["current_price"]
        shares = p["shares"]
        cost = p["cost_price"]
        total_value = p["current_value"]
        gl = p["gain_loss"]
        gl_pct = p["gain_loss_pct"]
        gl_arrow = "▲" if gl_pct >= 0 else "▼"
        gl_sign = "+" if gl >= 0 else ""

        if p["currency"] == "TWD":
            section = "台股"
            section_value[section] += total_value
            shares_str = f"{shares:,.0f}"
            price_str = f"NT${current:,.0f}"
            cost_str = f"NT${cost:,.0f}"
            total_str = fmt_twd(total_value)
            gl_str = f"NT${gl_sign}{gl:,.0f} ({gl_arrow}{abs(gl_pct):.1f}%)"
        elif p["category"] == "加密貨幣":
            section = "加密貨幣"
            section_value[section] += total_value
            shares_str = f"{shares:.4f}"
            price_str = f"${current:,.2f}"
            cost_str = f"${cost:,.2f}"
            total_str = fmt_usd(total_value)
            gl_str = f"${gl_sign}{gl:,.2f} ({gl_arrow}{abs(gl_pct):.1f}%)"
        else:
            section = "美股 / ETF"
            section_value[section] += total_value
            shares_str = f"{shares:,.2f}"
            price_str = f"${current:.2f}"
            cost_str = f"${cost:.2f}"
            total_str = fmt_usd(total_value)
            gl_str = f"${gl_sign}{gl:,.2f} ({gl_arrow}{abs(gl_pct):.1f}%)"

        sections[section].append((display_ticker, shares_str, price_str, cost_str, total_str, gl_str))

    lines: list[str] = []
    for section, rows in sections.items():
        if not rows:
            continue
        lines.append(f"<b>📊 {section}</b>")
        lines.append(f"<pre>{_holdings_table(rows)}</pre>")
        val = section_value[section]
        if section == "台股":
            twd_str = fmt_twd(val)
            usd_str = fmt_usd(val / fx_rate) if fx_rate else "—"
            lines.append(f"<i>合計 {twd_str}  /  {usd_str}</i>")
        elif section in ("美股 / ETF", "加密貨幣"):
            usd_str = fmt_usd(val)
            twd_str = fmt_twd(val * fx_rate) if fx_rate else "—"
            lines.append(f"<i>合計 {usd_str}  /  {twd_str}</i>")
        lines.append("")

    return "\n".join(lines).strip()


def handle_update_holding(
    args: list[str],
    portfolio_path: str = settings.portfolio_csv_path,
    reason: str = "",
    transaction_log: TransactionLog | None = None,
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
    if transaction_log is not None:
        transaction_log.append(ticker, "UPDATE", f"shares={shares} cost={cost}", reason)
    return f"Updated {ticker}: {shares} shares @ {cost}."


def handle_add_holding(
    args: list[str],
    portfolio_path: str = settings.portfolio_csv_path,
    reason: str = "",
    transaction_log: TransactionLog | None = None,
) -> str:
    # args: TICKER NAME SHARES COST CURRENCY CATEGORY
    if len(args) < 6:
        return "Usage: add TICKER NAME SHARES COST CURRENCY CATEGORY"
    ticker = args[0].upper()
    name = args[1]
    try:
        shares = float(args[2])
        cost = float(args[3])
    except ValueError:
        return "SHARES and COST must be numbers."
    currency = args[4].upper()
    category = args[5]
    p = Path(portfolio_path)
    if not p.exists():
        return f"Portfolio file not found: {portfolio_path}"
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if any(r["ticker"] == ticker for r in rows):
        return f"{ticker} already exists in portfolio. Use Edit to update it."
    rows.append(
        {
            "ticker": ticker,
            "name": name,
            "shares": str(shares),
            "cost_price": str(cost),
            "currency": currency,
            "category": category,
        }
    )
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if transaction_log is not None:
        transaction_log.append(ticker, "ADD", f"name={name} shares={shares} cost={cost} currency={currency} category={category}", reason)
    return f"Added {ticker} ({name}): {shares} shares @ {cost} [{currency} / {category}]."


def handle_remove_holding(
    args: list[str],
    portfolio_path: str = settings.portfolio_csv_path,
    reason: str = "",
    transaction_log: TransactionLog | None = None,
) -> str:
    if len(args) < 1:
        return "Usage: remove TICKER"
    ticker = args[0].upper()
    p = Path(portfolio_path)
    if not p.exists():
        return f"Portfolio file not found: {portfolio_path}"
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    new_rows = [r for r in rows if r["ticker"] != ticker]
    if len(new_rows) == len(rows):
        return f"Ticker {ticker} not found in portfolio."
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    if transaction_log is not None:
        transaction_log.append(ticker, "REMOVE", "", reason)
    return f"Removed {ticker} from portfolio."


def handle_status() -> str:
    return "Researcher agent is running.\nUse /watchlist list or /alert show to check state."
