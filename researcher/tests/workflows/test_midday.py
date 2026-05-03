from typing import cast
from unittest.mock import MagicMock, patch
from researcher.workflows.midday import run
from researcher.services.workflow_deps import WorkflowDeps


def _make_deps(positions):
    portfolio = MagicMock()
    portfolio.fetch_summary.return_value = {
        "positions": positions,
    }
    memory = MagicMock()
    memory.last_n_entries.return_value = ""
    memory.resolve.return_value = "RESEARCH-LOG.md"
    notifier = MagicMock()
    return WorkflowDeps(notifier=notifier, memory=memory, portfolio=portfolio)


def test_tw_market_filters_twd_positions():
    positions = [
        {"ticker": "2330.TW", "currency": "TWD", "is_cash": False, "current_price": 100.0},
        {"ticker": "AAPL", "currency": "USD", "is_cash": False, "current_price": 200.0},
    ]
    deps = _make_deps(positions)
    with patch("researcher.workflows.midday.yf.Tickers") as mock_tickers, \
         patch("researcher.workflows.midday.load_alerts", return_value=[]), \
         patch("researcher.workflows.midday.check_positions", return_value=[]):
        mock_tickers.return_value.tickers = {}
        run("TW", deps)
    # Should only pass TWD tickers to yf.Tickers
    call_args = mock_tickers.call_args[0][0]
    assert "2330.TW" in call_args
    assert "AAPL" not in call_args


def test_us_market_filters_usd_positions():
    positions = [
        {"ticker": "2330.TW", "currency": "TWD", "is_cash": False, "current_price": 100.0},
        {"ticker": "AAPL", "currency": "USD", "is_cash": False, "current_price": 200.0},
    ]
    deps = _make_deps(positions)
    with patch("researcher.workflows.midday.yf.Tickers") as mock_tickers, \
         patch("researcher.workflows.midday.load_alerts", return_value=[]), \
         patch("researcher.workflows.midday.check_positions", return_value=[]):
        mock_tickers.return_value.tickers = {}
        run("US", deps)
    call_args = mock_tickers.call_args[0][0]
    assert "AAPL" in call_args
    assert "2330.TW" not in call_args


def test_log_header_uses_market_name():
    positions = [
        {"ticker": "2330.TW", "currency": "TWD", "is_cash": False, "current_price": 100.0},
    ]
    deps = _make_deps(positions)
    with patch("researcher.workflows.midday.yf.Tickers") as mock_tickers, \
         patch("researcher.workflows.midday.load_alerts", return_value=[]), \
         patch("researcher.workflows.midday.check_positions", return_value=[]):
        mock_tickers.return_value.tickers = {}
        run("TW", deps)
    memory_mock = cast(MagicMock, deps.memory)
    appended = memory_mock.append_entry.call_args
    if appended:
        log_text = appended[0][1]
        assert "TW Midday Scan" in log_text
