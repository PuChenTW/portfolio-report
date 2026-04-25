import pytest
from portfolio.watchlist import WatchlistEntry, load_watchlist, add_ticker, remove_ticker


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "watchlist.csv"
    p.write_text("ticker,name,note\nAAPL,Apple,\nTSLA,Tesla,momentum play\n")
    return str(p)


def test_load_watchlist(csv_path):
    entries = load_watchlist(csv_path)
    assert len(entries) == 2
    assert entries[0].ticker == "AAPL"
    assert entries[1].note == "momentum play"


def test_load_watchlist_missing_file(tmp_path):
    entries = load_watchlist(str(tmp_path / "nope.csv"))
    assert entries == []


def test_add_ticker(csv_path):
    add_ticker(csv_path, WatchlistEntry(ticker="NVDA", name="Nvidia", note=""))
    entries = load_watchlist(csv_path)
    assert any(e.ticker == "NVDA" for e in entries)


def test_add_ticker_deduplicates(csv_path):
    add_ticker(csv_path, WatchlistEntry(ticker="AAPL", name="Apple", note="already here"))
    entries = load_watchlist(csv_path)
    assert sum(e.ticker == "AAPL" for e in entries) == 1


def test_remove_ticker(csv_path):
    remove_ticker(csv_path, "AAPL")
    entries = load_watchlist(csv_path)
    assert not any(e.ticker == "AAPL" for e in entries)


def test_remove_ticker_nonexistent_is_noop(csv_path):
    remove_ticker(csv_path, "ZZZZ")
    entries = load_watchlist(csv_path)
    assert len(entries) == 2
