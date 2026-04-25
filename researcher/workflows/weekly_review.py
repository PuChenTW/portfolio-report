import os
import sys
import time
from datetime import datetime

import yfinance as yf
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

from portfolio.portfolio import TZ_TAIPEI
from portfolio.report import _esc
from portfolio.telegram import send_telegram_messages

from researcher.memory.io import append_entry, last_n_entries

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")
_BENCHMARKS = ["SPY", "0050.TW"]


class _WeeklyReview(BaseModel):
    what_worked: list[str]
    what_didnt: list[str]
    key_lessons: list[str]
    outlook: str


def _fetch_benchmark_returns() -> dict[str, float]:
    result: dict[str, float] = {}
    try:
        data = yf.Tickers(" ".join(_BENCHMARKS))
        for ticker in _BENCHMARKS:
            try:
                info = data.tickers[ticker].fast_info
                prev = float(info["previousClose"])
                current = float(info["lastPrice"])
                result[ticker] = round((current - prev) / prev * 100, 2) if prev else 0.0
            except (KeyError, TypeError, ValueError):
                pass
    except Exception as e:
        print(f"[warn] benchmark fetch failed: {e}", file=sys.stderr)
    return result


def run() -> None:
    """Saturday weekly review: synthesize the week and send summary."""
    now = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")
    print(f"[{now.isoformat()}] weekly_review.run()")

    portfolio_log = last_n_entries(f"{_MEMORY_PATH}/PORTFOLIO-LOG.md", 10)
    research_log = last_n_entries(f"{_MEMORY_PATH}/RESEARCH-LOG.md", 10)
    benchmarks = _fetch_benchmark_returns()
    benchmark_str = "  ".join(f"{t}: {v:+.2f}%" for t, v in benchmarks.items())

    prompt = (
        f"今天是 {date_str}（週末）。請回顧本週投資組合表現並撰寫覆盤報告。\n\n"
        f"本週持倉快照：\n{portfolio_log}\n\n"
        f"本週研究紀錄：\n{research_log}\n\n"
        f"本週指數表現：{benchmark_str}\n\n"
        f"請填寫：\n"
        f"- what_worked：本週做對的事（3-5 條）\n"
        f"- what_didnt：本週做錯或失誤的地方（3-5 條）\n"
        f"- key_lessons：關鍵學習點（2-3 條）\n"
        f"- outlook：下週市場展望（2-3 句）\n"
        f"語言：台灣繁體中文。"
    )

    agent = Agent(
        "google-gla:gemini-3-flash-preview",
        tools=[tavily_search_tool(os.environ["TAVILY_API_KEY"])],
        output_type=_WeeklyReview,
        system_prompt=f"週末覆盤日期：{date_str}",
    )

    review: _WeeklyReview | None = None
    for attempt in range(5):
        try:
            result = agent.run_sync(prompt)
            review = result.output
            break
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
            else:
                print(f"[warn] weekly review agent failed: {e}", file=sys.stderr)

    if review is None:
        return

    lines = [f"## {date_str} Weekly Review"]
    lines.append(f"Benchmarks: {benchmark_str}")
    lines.append("### What Worked")
    lines += [f"• {row}" for row in review.what_worked]
    lines.append("### What Didn't Work")
    lines += [f"• {row}" for row in review.what_didnt]
    lines.append("### Key Lessons")
    lines += [f"• {row}" for row in review.key_lessons]
    lines.append(f"### Outlook\n{review.outlook}")
    append_entry(f"{_MEMORY_PATH}/WEEKLY-REVIEW.md", "\n".join(lines))

    msg_lines = [f"📅 *週末覆盤 {_esc(date_str)}*", f"指數: {_esc(benchmark_str)}", ""]
    msg_lines.append("✅ *做對的事*")
    msg_lines += [f"• {_esc(row)}" for row in review.what_worked]
    msg_lines.append("")
    msg_lines.append("❌ *做錯的地方*")
    msg_lines += [f"• {_esc(row)}" for row in review.what_didnt]
    msg_lines.append("")
    msg_lines.append("💡 *關鍵學習*")
    msg_lines += [f"• {_esc(row)}" for row in review.key_lessons]
    msg_lines.append(f"\n📈 *下週展望*\n{_esc(review.outlook)}")
    send_telegram_messages(["\n".join(msg_lines)])
