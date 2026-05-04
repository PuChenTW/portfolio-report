import pytest
from unittest.mock import patch
from researcher.handlers.commands import (
    handle_watchlist,
    handle_alert,
    handle_holdings,
    handle_update_holding,
    handle_status,
)


@pytest.fixture
def watchlist_path(tmp_path):
    p = tmp_path / "watchlist.csv"
    p.write_text("ticker,name,note\nAAPL,Apple,\n")
    return str(p)


@pytest.fixture
def alerts_path(tmp_path):
    p = tmp_path / "price-alerts.yml"
    p.write_text("defaults:\n  stop_loss_pct: -0.15\n  take_profit_pct: 0.50\noverrides: {}\n")
    return str(p)


def test_watchlist_list(watchlist_path):
    reply = handle_watchlist(["list"], watchlist_path=watchlist_path)
    assert "AAPL" in reply


def test_watchlist_add(watchlist_path):
    reply = handle_watchlist(["add", "NVDA", "Nvidia"], watchlist_path=watchlist_path)
    assert "NVDA" in reply


def test_watchlist_remove(watchlist_path):
    reply = handle_watchlist(["remove", "AAPL"], watchlist_path=watchlist_path)
    assert "removed" in reply.lower() or "AAPL" in reply


def test_watchlist_unknown_subcommand(watchlist_path):
    reply = handle_watchlist(["bogus"], watchlist_path=watchlist_path)
    assert "Usage" in reply or "usage" in reply


def test_alert_set_below(alerts_path):
    reply = handle_alert(["set", "TSLA", "below=150.0"], alerts_path=alerts_path)
    assert "TSLA" in reply


def test_alert_show(alerts_path):
    reply = handle_alert(["show"], alerts_path=alerts_path)
    assert "stop_loss_pct" in reply or "-15" in reply or "0.15" in reply


def test_update_holding_updates_csv(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,name,shares,cost_price,currency,category\nAAPL,Apple,10,150.0,USD,美股\n")
    reply = handle_update_holding(["AAPL", "20", "160.0"], portfolio_path=str(p))
    assert "AAPL" in reply
    assert "20" in reply
    content = p.read_text()
    assert "20.0" in content
    assert "160.0" in content


def test_update_holding_ticker_not_found(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,name,shares,cost_price,currency,category\nAAPL,Apple,10,150.0,USD,美股\n")
    reply = handle_update_holding(["NVDA", "5", "100.0"], portfolio_path=str(p))
    assert "not found" in reply.lower()


def test_update_holding_usage_when_no_args(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text("ticker,name,shares,cost_price,currency,category\nAAPL,Apple,10,150.0,USD,美股\n")
    reply = handle_update_holding([], portfolio_path=str(p))
    assert "Usage" in reply


_FAKE_PORTFOLIO_DATA = {
    "summary": {
        "fx_rate": 32.0,
        "positions": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "currency": "USD",
                "category": "美股",
                "shares": 10,
                "cost_price": 180.0,
                "current_price": 213.45,
                "current_value": 2134.5,
                "gain_loss": 334.5,
                "gain_loss_pct": 18.5,
                "is_cash": False,
                "pct_of_currency_total": 60.0,
            },
            {
                "ticker": "2330.TW",
                "name": "台積電",
                "currency": "TWD",
                "category": "台股",
                "shares": 54,
                "cost_price": 935.0,
                "current_price": 1050.0,
                "current_value": 56700.0,
                "gain_loss": 6210.0,
                "gain_loss_pct": 12.3,
                "is_cash": False,
                "pct_of_currency_total": 100.0,
            },
            {
                "ticker": "CASH_TWD",
                "name": "新台幣現金",
                "currency": "TWD",
                "category": "現金",
                "current_price": 100000.0,
                "current_value": 100000.0,
                "gain_loss_pct": 0.0,
                "is_cash": True,
                "pct_of_currency_total": 0.0,
                "shares": 1,
            },
        ],
        "by_currency": {
            "TWD": {"total_value": 156700.0},
            "USD": {"total_value": 2134.5},
        },
    },
    "prev_closes": {"AAPL": 210.0, "2330.TW": 1040.0},
}


def test_holdings_display_contains_tickers():
    with patch("researcher.handlers.commands.fetch_portfolio", return_value=_FAKE_PORTFOLIO_DATA):
        reply = handle_holdings()
    assert "AAPL" in reply
    assert "2330" in reply


def test_holdings_display_contains_price_and_pnl():
    with patch("researcher.handlers.commands.fetch_portfolio", return_value=_FAKE_PORTFOLIO_DATA):
        reply = handle_holdings()
    assert "$213" in reply or "213" in reply
    assert "18" in reply  # gain_loss_pct


def test_holdings_display_groups_by_section():
    with patch("researcher.handlers.commands.fetch_portfolio", return_value=_FAKE_PORTFOLIO_DATA):
        reply = handle_holdings()
    assert "台股" in reply
    assert "美股" in reply


def test_holdings_display_shows_cash():
    with patch("researcher.handlers.commands.fetch_portfolio", return_value=_FAKE_PORTFOLIO_DATA):
        reply = handle_holdings()
    assert "現金" in reply or "CASH" in reply or "新台幣" in reply


def test_status_returns_string():
    reply = handle_status()
    assert isinstance(reply, str)
    assert len(reply) > 0
