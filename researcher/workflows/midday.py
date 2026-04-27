from datetime import datetime

from pydantic import BaseModel

import yfinance as yf

from portfolio.portfolio import TZ_TAIPEI
from portfolio.alerts import load_alerts, check_positions

from researcher.config import settings
from researcher.services.agent_runner import make_search_agent, run_agent_sync
from researcher.services.workflow_deps import WorkflowDeps


class _ThesisCheck(BaseModel):
    ticker: str
    thesis_intact: bool
    reason: str
    recommendation: str


def run(deps: WorkflowDeps) -> None:
    """US midday scan: check price alerts and verify thesis for volatile positions."""
    now = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")
    print(f"[{now.isoformat()}] midday.run()")

    assert deps.portfolio is not None, "midday requires a PortfolioReader"

    summary = deps.portfolio.fetch_summary()
    positions = [p for p in summary["positions"] if not p.get("is_cash")]
    us_positions = [p for p in positions if p["currency"] == "USD"]

    rules = load_alerts(settings.price_alerts_path)
    price_alerts = check_positions(us_positions, rules)

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
    recent_log = deps.memory.last_n_entries(deps.memory.resolve("RESEARCH-LOG.md"), 2)

    checks: list[_ThesisCheck] = []
    for ticker in flagged:
        prompt = (
            f"今天是 {date_str}。{ticker} 今日出現異常波動或觸及價格警示。\n"
            f"近期研究紀錄：\n{recent_log}\n\n"
            f"請搜尋 '{ticker} news today {date_str}' 並判斷：\n"
            f"1. 看多論點是否被破壞？\n2. 建議操作方向？\n"
            f"請用繁體中文回答。"
        )
        agent = make_search_agent(
            _ThesisCheck,
            system_prompt=f"ticker={ticker}, date={date_str}",
        )
        check = run_agent_sync(agent, prompt, max_attempts=3, label=f"thesis/{ticker}")
        if check is not None:
            check.ticker = ticker
            checks.append(check)

    log_lines = [f"## {date_str} US Midday Scan"]
    if price_alerts:
        log_lines.append("### Price Alerts")
        for a in price_alerts:
            log_lines.append(f"• {a.ticker}: {a.kind} threshold {a.threshold_price:.2f} (current {a.current_price:.2f})")
    for check in checks:
        status = "✅ 論點完整" if check.thesis_intact else "❌ 論點受損"
        log_lines.append(f"• {check.ticker}: {status} — {check.reason}")
    deps.memory.append_entry(deps.memory.resolve("RESEARCH-LOG.md"), "\n".join(log_lines))

    if price_alerts or any(not c.thesis_intact for c in checks):
        lines = ["⚠️ *盤中警示*"]
        for a in price_alerts:
            lines.append(f"• {a.ticker} 觸及 {a.kind} 警示 @ {a.current_price:.2f}")
        for c in checks:
            if not c.thesis_intact:
                lines.append(f"• {c.ticker}: 論點受損 — {c.recommendation}")
        deps.notifier.send_messages(["\n".join(lines)])
