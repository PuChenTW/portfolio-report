import pytest
from pathlib import Path
from researcher.handlers.commands import handle_watchlist, handle_alert, handle_holdings, handle_status


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


def test_status_returns_string():
    reply = handle_status()
    assert isinstance(reply, str)
    assert len(reply) > 0
