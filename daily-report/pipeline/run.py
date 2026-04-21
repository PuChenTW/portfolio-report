import sys
from datetime import datetime

from portfolio.report import format_telegram_messages
from portfolio.telegram import send_telegram_messages

from pipeline.data import (
    TZ_TAIPEI,
    _fmt_today,
    fetch_portfolio,
    build_holdings,
    build_totals,
)
from pipeline.news import _NEWS_DEFAULTS, run_claude_news


def main():
    print(f"[{datetime.now(TZ_TAIPEI).isoformat()}] Starting daily report pipeline")

    # Phase 1
    print("Phase 1: Fetching portfolio data...")
    data = fetch_portfolio()
    us_holdings, tw_holdings, crypto_holdings = build_holdings(data)
    totals = build_totals(data)
    errors = data["summary"].get("errors", [])
    if errors:
        print(f"[warn] Price fetch errors: {errors}", file=sys.stderr)

    # Phase 2
    print("Phase 2: Fetching news via Claude...")
    news = run_claude_news(us_holdings, tw_holdings, crypto_holdings, totals, summary=data["summary"])

    tw_notes: dict = news.get("tw_notes", {})
    for h in tw_holdings:
        note = tw_notes.get(h["ticker"], "—")
        h["note"] = note if note else "—"

    tw_change_str, tw_change_up = totals["tw_change"]
    us_change_str, us_change_up = totals["us_change"]
    crypto_change_str, crypto_change_up = totals["crypto_change"]

    # Phase 3
    print("Phase 3: Formatting Telegram messages...")
    messages = format_telegram_messages(
        today_date=_fmt_today(),
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

    print("Phase 3: Sending via Telegram...")
    result = send_telegram_messages(messages)
    print(result)

    if not result.startswith("✅"):
        sys.exit(1)
