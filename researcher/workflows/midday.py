from datetime import datetime

from pydantic import BaseModel

import yfinance as yf

from portfolio.portfolio import TZ_TAIPEI
from portfolio.alerts import load_alerts, check_positions

from researcher.config import settings
from researcher.services.agent_runner import make_search_agent, run_agent_sync
from researcher.services.workflow_deps import WorkflowDeps

_CURRENCY: dict[str, str] = {"TW": "TWD", "US": "USD"}


class _ThesisCheck(BaseModel):
    ticker: str
    thesis_intact: bool
    reason: str
    recommendation: str


def run(market: str, deps: WorkflowDeps) -> None:
    """Midday scan: check price alerts and verify thesis for volatile positions."""
    now = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")
    print(f"[{now.isoformat()}] midday.run({market})")

    assert deps.portfolio is not None, "midday requires a PortfolioReader"

    currency = _CURRENCY.get(market)
    if currency is None:
        raise ValueError(f"midday.run: unknown market {market!r}. Expected one of {list(_CURRENCY)}")
    summary = deps.portfolio.fetch_summary()
    positions = [p for p in summary["positions"] if not p.get("is_cash")]
    market_positions = [p for p in positions if p["currency"] == currency]

    rules = load_alerts(settings.price_alerts_path)
    price_alerts = check_positions(market_positions, rules)

    tickers = [p["ticker"] for p in market_positions]
    volatile_by_ticker: dict[str, dict] = {}
    if tickers:
        data = yf.Tickers(" ".join(tickers))
        for p in market_positions:
            try:
                open_price = float(data.tickers[p["ticker"]].fast_info["open"])
                current = p["current_price"]
                if open_price > 0 and abs((current - open_price) / open_price) > 0.02:
                    pct = (current - open_price) / open_price * 100
                    volatile_by_ticker[p["ticker"]] = {
                        "open": round(open_price, 2),
                        "current": round(current, 2),
                        "from_open_pct": round(pct, 2),
                    }
            except (KeyError, TypeError, ValueError):
                pass

    if not price_alerts and not volatile_by_ticker:
        print(f"[midday/{market}] No alerts triggered.")
        return

    flagged = list({a.ticker for a in price_alerts} | set(volatile_by_ticker))
    recent_log = deps.memory.last_n_entries(deps.memory.resolve("RESEARCH-LOG.md"), 2)

    checks: list[_ThesisCheck] = []
    for ticker in flagged:
        ctx = volatile_by_ticker.get(ticker)
        if ctx:
            direction = "上漲" if ctx["from_open_pct"] > 0 else "下跌"
            price_fact = (
                f"今日開盤 {ctx['open']}，現價 {ctx['current']}，"
                f"較開盤{direction} {abs(ctx['from_open_pct']):.1f}%。"
            )
        else:
            price_fact = ""
        prompt = (
            f"今天是 {date_str}。{ticker} 今日出現異常波動或觸及價格警示。{price_fact}\n"
            f"近期研究紀錄：\n{recent_log}\n\n"
            f"請搜尋 '{ticker} stock news {date_str}' 並判斷：\n"
            f"1. 看多論點是否被破壞？\n2. 建議操作方向？\n"
            f"請根據上方的實際價格方向作為判斷基準，搜尋新聞補充原因。"
            f"請用繁體中文回答。"
        )
        agent = make_search_agent(
            _ThesisCheck,
            system_prompt=(
                f"今天是 {date_str}。你的任務是分析 {ticker} 今日（{date_str}）的表現。"
                f"請根據使用者提供的實際價格方向作為事實基準，用新聞補充解釋原因。"
            ),
        )
        check = run_agent_sync(agent, prompt, max_attempts=3, label=f"thesis/{ticker}")
        if check is not None:
            check.ticker = ticker
            checks.append(check)

    log_lines = [f"## {date_str} {market} Midday Scan"]
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
