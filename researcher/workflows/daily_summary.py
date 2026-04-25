import os
import sys
from datetime import datetime

from portfolio.portfolio import TZ_TAIPEI
from portfolio.telegram import send_telegram_messages
from portfolio.report import format_telegram_messages

# daily-report package exposes its modules as `pipeline.*`
from pipeline.data import (  # type: ignore[import]
    _fmt_today, fetch_portfolio, build_holdings, build_totals,
)
from pipeline.news import _NEWS_DEFAULTS, run_claude_news  # type: ignore[import]

from researcher.memory.io import append_entry

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")


def run(market: str) -> None:
    """Run daily portfolio summary for 'TW' or 'US' market close."""
    print(f"[{datetime.now(TZ_TAIPEI).isoformat()}] daily_summary.run({market})")

    data = fetch_portfolio()
    us_holdings, tw_holdings, crypto_holdings = build_holdings(data)
    totals = build_totals(data)
    errors = data["summary"].get("errors", [])
    if errors:
        print(f"[warn] Price fetch errors: {errors}", file=sys.stderr)

    news = run_claude_news(
        us_holdings, tw_holdings, crypto_holdings, totals, summary=data["summary"]
    )

    tw_notes: dict = news.get("tw_notes", {})
    for h in tw_holdings:
        h["note"] = tw_notes.get(h["ticker"], "—") or "—"

    tw_change_str, tw_change_up = totals["tw_change"]
    us_change_str, us_change_up = totals["us_change"]
    crypto_change_str, crypto_change_up = totals["crypto_change"]

    today = _fmt_today()
    messages = format_telegram_messages(
        today_date=today,
        tw_total=totals["tw_total"],
        tw_change=tw_change_str,
        tw_change_up=tw_change_up,
        us_total=totals["us_total"],
        us_change=us_change_str,
        us_change_up=us_change_up,
        crypto_total=totals["crypto_total"],
        crypto_change=crypto_change_str,
        crypto_change_up=crypto_change_up,
        us_holdings=us_holdings,
        us_event=news.get("us_event", _NEWS_DEFAULTS["us_event"]),
        tw_holdings=tw_holdings,
        crypto_holdings=crypto_holdings,
        macro_rows=news.get("macro_rows", _NEWS_DEFAULTS["macro_rows"]),
        tip_rows=news.get("tip_rows", _NEWS_DEFAULTS["tip_rows"]),
    )

    result = send_telegram_messages(messages)
    print(result)

    # Persist snapshot to PORTFOLIO-LOG.md
    snapshot_lines = [f"## {today} {market} Close"]
    snapshot_lines.append(
        f"TWD: {totals['tw_total']} {tw_change_str} | "
        f"USD: {totals['us_total']} {us_change_str} | "
        f"Crypto: {totals['crypto_total']} {crypto_change_str}"
    )
    append_entry(f"{_MEMORY_PATH}/PORTFOLIO-LOG.md", "\n".join(snapshot_lines))
