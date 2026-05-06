import sys
from datetime import datetime

from portfolio.report import format_telegram_messages

from researcher.pipeline.data import TZ_TAIPEI, fmt_today
from researcher.pipeline.news import _NEWS_DEFAULTS, generate_close_insight, search_news
from researcher.services.workflow_deps import WorkflowDeps


def run(market: str, deps: WorkflowDeps) -> None:
    """Run daily portfolio summary for 'TW' or 'US' market close."""
    print(f"[{datetime.now(TZ_TAIPEI).isoformat()}] daily_summary.run({market})")

    assert deps.portfolio is not None, "daily_summary requires a PortfolioReader"

    data = deps.portfolio.fetch()
    us_holdings, tw_holdings, crypto_holdings = deps.portfolio.build_holdings(data)
    totals = deps.portfolio.build_totals(data)
    errors = data["summary"].get("errors", [])
    if errors:
        print(f"[warn] Price fetch errors: {errors}", file=sys.stderr)

    from datetime import date as _date

    research_path = deps.memory.resolve("RESEARCH-LOG.md")
    research_entries = deps.memory.last_n_entries(research_path, 6)
    transaction_log = deps.transaction_log.entries_since(_date.today())
    date_str = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")
    has_today_research = bool(research_entries and date_str in research_entries and market in research_entries and ("Pre-market" in research_entries or "Midday Scan" in research_entries))

    if has_today_research:
        news = generate_close_insight(
            us_holdings,
            tw_holdings,
            crypto_holdings,
            summary=data["summary"],
            research_entries=research_entries,
            market=market,
            transaction_log=transaction_log,
        )
    else:
        print(
            f"[warn] No today's research for {market} in RESEARCH-LOG.md; falling back to search_news()",
            file=sys.stderr,
        )
        news = search_news(us_holdings, tw_holdings, crypto_holdings, summary=data["summary"])

    tw_notes: dict = news.get("tw_notes", {})
    for h in tw_holdings:
        h["note"] = tw_notes.get(h["ticker"], "—") or "—"

    tw_change_str, tw_change_up = totals["tw_change"]
    us_change_str, us_change_up = totals["us_change"]
    crypto_change_str, crypto_change_up = totals["crypto_change"]

    today = fmt_today()
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

    deps.notifier.send_messages(messages)

    snapshot_lines = [f"## {today} {market} Close"]
    snapshot_lines.append(f"TWD: {totals['tw_total']} {tw_change_str} | USD: {totals['us_total']} {us_change_str} | Crypto: {totals['crypto_total']} {crypto_change_str}")
    deps.memory.append_entry(deps.memory.resolve("PORTFOLIO-LOG.md"), "\n".join(snapshot_lines))

    close_lines = [f"## {date_str} {market} Close Insight"]
    for row in news.get("macro_rows", []):
        close_lines.append(f"• {row}")
    close_lines.append(f"US Event: {news.get('us_event', '')}")
    for row in news.get("tip_rows", []):
        close_lines.append(f"→ {row}")
    tw_notes_out = news.get("tw_notes", {})
    if tw_notes_out:
        close_lines.append("TW Notes:")
        for ticker, note in tw_notes_out.items():
            close_lines.append(f"  {ticker}: {note}")
    deps.memory.append_entry(research_path, "\n".join(close_lines))
