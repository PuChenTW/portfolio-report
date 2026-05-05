from typing import cast
from unittest.mock import MagicMock, patch

from researcher.pipeline.news import _extract_today_research
from researcher.services.workflow_deps import WorkflowDeps
from researcher.workflows.daily_summary import run

_TODAY = "2026-05-03"
_FAKE_NEWS = {
    "macro_rows": ["市場回升"],
    "us_event": "Fed 維持利率",
    "tw_notes": {"2330.TW": "外資買超"},
    "tip_rows": ["持有台積電"],
}


def _make_deps(research_entries: str = "") -> WorkflowDeps:
    portfolio = MagicMock()
    portfolio.fetch.return_value = {
        "summary": {
            "errors": [],
            "positions": [],
            "by_currency": {},
            "global_total_usd": 0,
            "currency_pct": {},
            "fx_rate": None,
        },
    }
    portfolio.build_holdings.return_value = ([], [], [])
    portfolio.build_totals.return_value = {
        "tw_total": "NT$0",
        "tw_change": ("0.00%", True),
        "us_total": "$0",
        "us_change": ("0.00%", True),
        "crypto_total": "$0",
        "crypto_change": ("0.00%", True),
    }
    memory = MagicMock()
    memory.last_n_entries.return_value = research_entries
    memory.resolve.side_effect = lambda f: f
    notifier = MagicMock()
    transaction_log = MagicMock()
    transaction_log.entries_since.return_value = ""
    return WorkflowDeps(notifier=notifier, memory=memory, transaction_log=transaction_log, portfolio=portfolio)


def _today_research(market: str) -> str:
    return f"## {_TODAY} {market} Pre-market\n• 外資看好\n## {_TODAY} {market} Midday Scan\n• 盤中平穩"


def test_run_uses_close_insight_when_today_entries_present():
    deps = _make_deps(_today_research("US"))
    with (
        patch("researcher.workflows.daily_summary.generate_close_insight", return_value=_FAKE_NEWS) as mock_ci,
        patch("researcher.workflows.daily_summary.search_news") as mock_sn,
        patch("researcher.workflows.daily_summary.datetime") as mock_dt,
        patch("researcher.workflows.daily_summary.format_telegram_messages", return_value=[]),
    ):
        mock_dt.now.return_value.isoformat.return_value = ""
        mock_dt.now.return_value.strftime.return_value = _TODAY
        run("US", deps)

    mock_ci.assert_called_once()
    mock_sn.assert_not_called()


def test_run_falls_back_to_search_news_when_no_entries():
    deps = _make_deps("")
    with (
        patch("researcher.workflows.daily_summary.generate_close_insight") as mock_ci,
        patch("researcher.workflows.daily_summary.search_news", return_value=_FAKE_NEWS) as mock_sn,
        patch("researcher.workflows.daily_summary.datetime") as mock_dt,
        patch("researcher.workflows.daily_summary.format_telegram_messages", return_value=[]),
    ):
        mock_dt.now.return_value.isoformat.return_value = ""
        mock_dt.now.return_value.strftime.return_value = _TODAY
        run("US", deps)

    mock_sn.assert_called_once()
    mock_ci.assert_not_called()


def test_run_appends_close_insight_to_research_log():
    deps = _make_deps(_today_research("TW"))
    with (
        patch("researcher.workflows.daily_summary.generate_close_insight", return_value=_FAKE_NEWS),
        patch("researcher.workflows.daily_summary.datetime") as mock_dt,
        patch("researcher.workflows.daily_summary.format_telegram_messages", return_value=[]),
    ):
        mock_dt.now.return_value.isoformat.return_value = ""
        mock_dt.now.return_value.strftime.return_value = _TODAY
        run("TW", deps)

    memory_mock = cast(MagicMock, deps.memory)
    calls = memory_mock.append_entry.call_args_list
    assert len(calls) == 2
    research_call = next(c for c in calls if "RESEARCH-LOG.md" in str(c))
    log_text = research_call[0][1]
    assert "Close Insight" in log_text
    assert "TW" in log_text


def test_run_appends_snapshot_to_portfolio_log():
    deps = _make_deps(_today_research("US"))
    with (
        patch("researcher.workflows.daily_summary.generate_close_insight", return_value=_FAKE_NEWS),
        patch("researcher.workflows.daily_summary.datetime") as mock_dt,
        patch("researcher.workflows.daily_summary.format_telegram_messages", return_value=[]),
    ):
        mock_dt.now.return_value.isoformat.return_value = ""
        mock_dt.now.return_value.strftime.return_value = _TODAY
        run("US", deps)

    memory_mock = cast(MagicMock, deps.memory)
    calls = memory_mock.append_entry.call_args_list
    portfolio_call = next(c for c in calls if "PORTFOLIO-LOG.md" in str(c))
    log_text = portfolio_call[0][1]
    assert "Close" in log_text


# --- _extract_today_research unit tests ---


def test_extract_today_research_returns_matching_sections():
    entries = f"## 2026-05-02 US Pre-market\n• 昨日\n## {_TODAY} US Pre-market\n• 今日盤前\n## {_TODAY} TW Pre-market\n• 台股盤前\n## {_TODAY} US Midday Scan\n• 今日盤中\n"
    result = _extract_today_research(entries, "US", _TODAY)
    assert "今日盤前" in result
    assert "今日盤中" in result
    assert "昨日" not in result
    assert "台股盤前" not in result


def test_extract_today_research_empty_input():
    assert _extract_today_research("", "US", _TODAY) == ""


def test_extract_today_research_no_match():
    entries = "## 2026-05-02 US Pre-market\n• 昨日\n"
    assert _extract_today_research(entries, "US", _TODAY) == ""


def test_extract_today_research_excludes_close_insight():
    entries = f"## {_TODAY} US Close Insight\n• 收盤覆盤\n## {_TODAY} US Pre-market\n• 盤前\n"
    result = _extract_today_research(entries, "US", _TODAY)
    assert "盤前" in result
    assert "收盤覆盤" not in result
