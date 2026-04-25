import os
import sys
import time
from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

import yfinance as yf

from portfolio.portfolio import TZ_TAIPEI, compute_summary
from portfolio.alerts import load_alerts, check_positions
from portfolio.telegram import send_telegram_messages

from researcher.memory.io import append_entry, last_n_entries

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")
_ALERTS_PATH = os.environ.get("PRICE_ALERTS_PATH", "./price-alerts.yml")
_PORTFOLIO_CSV = os.environ.get("PORTFOLIO_CSV_PATH", "./portfolio.csv")


class _ThesisCheck(BaseModel):
    ticker: str
    thesis_intact: bool
    reason: str
    recommendation: str


def run() -> None:
    """US midday scan: check price alerts and verify thesis for volatile positions."""
    now = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")
    print(f"[{now.isoformat()}] midday.run()")

    summary = compute_summary(_PORTFOLIO_CSV)
    positions = [p for p in summary["positions"] if not p.get("is_cash")]
    us_positions = [p for p in positions if p["currency"] == "USD"]

    rules = load_alerts(_ALERTS_PATH)
    price_alerts = check_positions(us_positions, rules)

    # Flag positions with >2% move from today's open
    tickers = [p["ticker"] for p in us_positions]
    volatile: list[dict] = []
    if tickers:
        data = yf.Tickers(" ".join(tickers))
        for p in us_positions:
            try:
                open_price = float(data.tickers[p["ticker"]].fast_info["open"])
                current = p["current_price"]
                if open_price > 0 and abs((current - open_price) / open_price) > 0.02:
                    volatile.append({"ticker": p["ticker"], "open": open_price, "current": current})
            except (KeyError, TypeError, ValueError):
                pass

    if not price_alerts and not volatile:
        print("[midday] No alerts triggered.")
        return

    flagged = list({a.ticker for a in price_alerts} | {v["ticker"] for v in volatile})
    recent_log = last_n_entries(f"{_MEMORY_PATH}/RESEARCH-LOG.md", 2)

    checks: list[_ThesisCheck] = []
    for ticker in flagged:
        prompt = (
            f"今天是 {date_str}。{ticker} 今日出現異常波動或觸及價格警示。\n"
            f"近期研究紀錄：\n{recent_log}\n\n"
            f"請搜尋 '{ticker} news today {date_str}' 並判斷：\n"
            f"1. 看多論點是否被破壞？\n2. 建議操作方向？\n"
            f"請用繁體中文回答。"
        )
        agent = Agent(
            "google-gla:gemini-3-flash-preview",
            tools=[tavily_search_tool(os.environ["TAVILY_API_KEY"])],
            output_type=_ThesisCheck,
            system_prompt=f"ticker={ticker}, date={date_str}",
        )
        for attempt in range(3):
            try:
                result = agent.run_sync(prompt)
                check = result.output
                check.ticker = ticker
                checks.append(check)
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"[warn] thesis check failed for {ticker}: {e}", file=sys.stderr)

    log_lines = [f"## {date_str} US Midday Scan"]
    if price_alerts:
        log_lines.append("### Price Alerts")
        for a in price_alerts:
            log_lines.append(
                f"• {a.ticker}: {a.kind} threshold {a.threshold_price:.2f} (current {a.current_price:.2f})"
            )
    for check in checks:
        status = "✅ 論點完整" if check.thesis_intact else "❌ 論點受損"
        log_lines.append(f"• {check.ticker}: {status} — {check.reason}")
    append_entry(f"{_MEMORY_PATH}/RESEARCH-LOG.md", "\n".join(log_lines))

    if price_alerts or any(not c.thesis_intact for c in checks):
        lines = ["⚠️ *盤中警示*"]
        for a in price_alerts:
            lines.append(f"• {a.ticker} 觸及 {a.kind} 警示 @ {a.current_price:.2f}")
        for c in checks:
            if not c.thesis_intact:
                lines.append(f"• {c.ticker}: 論點受損 — {c.recommendation}")
        send_telegram_messages(["\n".join(lines)])
