import json
import os
import sys
import time
from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

from portfolio.portfolio import TZ_TAIPEI, compute_summary
from portfolio.telegram import send_telegram_messages
from portfolio.watchlist import load_watchlist

from researcher.memory.io import append_entry, last_n_entries, read_file

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")
_WATCHLIST_PATH = os.environ.get("WATCHLIST_CSV_PATH", "./watchlist.csv")
_PORTFOLIO_CSV = os.environ.get("PORTFOLIO_CSV_PATH", "./portfolio.csv")


class _PremarketSummary(BaseModel):
    macro_rows: list[str]
    catalyst_rows: list[str]
    alert_tickers: list[str]
    action_rows: list[str]


_PREMARKET_PROMPT_TW = """\
你是一位專業的買方研究員，負責台股盤前情蒐。今天是 {today}。

投資策略：
{strategy}

近三日研究紀錄摘要：
{recent_log}

目前持倉與觀察名單（台股相關）：
{portfolio_json}

請依序搜尋以下主題：
- "台股 加權指數 盤前 外資 {date}"
- "台積電 外資 法人 {date}" (以及其他台股持倉)
- "美國期貨 亞洲市場 今日 {date}"
- 觀察名單各標的 + "股價 消息 {date}"

搜尋完畢後填寫：
- macro_rows：3-5 條今日台股盤前重點
- catalyst_rows：各持倉/觀察標的今日催化劑（每條含 ticker）
- alert_tickers：今日需特別注意的標的（有重大消息或盤前大跌）
- action_rows：2-3 條今日操作建議

語言：台灣繁體中文。"""

_PREMARKET_PROMPT_US = """\
你是一位專業的買方研究員，負責美股盤前情蒐。今天是 {today}（台灣時間）。

投資策略：
{strategy}

近三日研究紀錄摘要：
{recent_log}

目前持倉與觀察名單（美股相關）：
{portfolio_json}

請依序搜尋以下主題：
- "S&P 500 futures VIX premarket {date}"
- "Fed interest rate economic calendar {date}"
- 各美股持倉 ticker + "premarket news earnings {date}"
- 觀察名單各標的 + "stock news catalyst {date}"

搜尋完畢後填寫：
- macro_rows：3-5 條今日美股盤前總體重點
- catalyst_rows：各持倉/觀察標的今日催化劑（每條含 ticker）
- alert_tickers：今日需特別注意的標的
- action_rows：2-3 條今日操作建議

語言：台灣繁體中文。"""


def run(market: str) -> None:
    """Run pre-market research for 'TW' or 'US'."""
    now = datetime.now(TZ_TAIPEI)
    today_str = now.strftime("%Y-%m-%d")
    print(f"[{now.isoformat()}] premarket.run({market})")

    strategy = read_file(f"{_MEMORY_PATH}/INVESTMENT-STRATEGY.md")
    recent_log = last_n_entries(f"{_MEMORY_PATH}/RESEARCH-LOG.md", 3)
    watchlist = load_watchlist(_WATCHLIST_PATH)

    summary = compute_summary(_PORTFOLIO_CSV)
    positions = summary.get("positions", [])

    if market == "TW":
        relevant = [p for p in positions if p["currency"] == "TWD" and not p.get("is_cash")]
        watch_relevant = [w for w in watchlist if w.ticker.endswith(".TW")]
        prompt_template = _PREMARKET_PROMPT_TW
    else:
        relevant = [p for p in positions if p["currency"] == "USD" and not p.get("is_cash")]
        watch_relevant = [w for w in watchlist if not w.ticker.endswith(".TW")]
        prompt_template = _PREMARKET_PROMPT_US

    portfolio_json = json.dumps(
        [{"ticker": p["ticker"], "gain_loss_pct": p["gain_loss_pct"]} for p in relevant]
        + [{"ticker": w.ticker, "watchlist": True} for w in watch_relevant],
        ensure_ascii=False,
    )

    prompt = prompt_template.format(
        today=today_str,
        date=today_str,
        strategy=strategy or "(策略文件尚未設定)",
        recent_log=recent_log or "(無近期紀錄)",
        portfolio_json=portfolio_json,
    )

    agent = Agent(
        "google-gla:gemini-3-flash-preview",
        tools=[tavily_search_tool(os.environ["TAVILY_API_KEY"])],
        output_type=_PremarketSummary,
        system_prompt=f"今天日期是 {today_str}。所有搜尋必須使用今日日期。",
    )

    result_data: _PremarketSummary | None = None
    for attempt in range(5):
        try:
            result = agent.run_sync(prompt)
            result_data = result.output
            break
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
                print(f"[warn] premarket agent failed attempt {attempt + 1}: {e}", file=sys.stderr)
            else:
                print(f"[warn] premarket agent failed after 5 attempts: {e}", file=sys.stderr)

    if result_data is None:
        return

    log_lines = [f"## {today_str} {market} Pre-market"]
    log_lines += [f"• {row}" for row in result_data.macro_rows]
    log_lines += [f"• {row}" for row in result_data.catalyst_rows]
    if result_data.action_rows:
        log_lines.append("### Actions")
        log_lines += [f"{i+1}. {row}" for i, row in enumerate(result_data.action_rows)]
    append_entry(f"{_MEMORY_PATH}/RESEARCH-LOG.md", "\n".join(log_lines))

    if result_data.alert_tickers:
        alert_msg = f"⚠️ *盤前預警 {market}*\n" + "\n".join(
            f"• {t}" for t in result_data.alert_tickers
        )
        action_msg = "\n".join(f"{i+1}\\. {row}" for i, row in enumerate(result_data.action_rows))
        send_telegram_messages([alert_msg + "\n\n" + action_msg])
