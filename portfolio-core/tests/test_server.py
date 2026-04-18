import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from portfolio.portfolio import compute_summary, _fetch_prices
from portfolio.report import (
    USHolding, TWHolding, CryptoHolding,
    generate_daily_report_html,
    _render_us_row, _render_tw_row, _render_crypto_row,
    _render_macro_rows, _render_tip_rows,
)
from portfolio.telegram import send_telegram_file

MOCK_PRICES = {
    "2330.TW": 920.0,
    "VOO": 480.0,
    "BTC-USD": 65000.0,
}


def make_mock_ticker(price):
    mock = MagicMock()
    mock.fast_info = {"lastPrice": price}
    return mock


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "portfolio.csv"
    p.write_text(
        "ticker,name,shares,cost_price,currency,category\n"
        "2330.TW,台積電,100,580,TWD,台股\n"
        "VOO,Vanguard S&P500,5,420,USD,美國ETF\n"
        "BTC-USD,Bitcoin,0.05,60000,USD,加密貨幣\n"
    )
    return str(p)


@patch("yfinance.Tickers")
def test_fetch_prices(mock_tickers_cls):
    tickers_obj = MagicMock()
    tickers_obj.tickers = {"2330.TW": make_mock_ticker(920.0)}
    mock_tickers_cls.return_value = tickers_obj

    result = _fetch_prices(["2330.TW"])
    assert result["2330.TW"] == 920.0


@patch("yfinance.Tickers")
def test_summary_calculates_pnl_per_currency(mock_tickers_cls, csv_path):
    tickers_obj = MagicMock()
    tickers_obj.tickers = {k: make_mock_ticker(v) for k, v in MOCK_PRICES.items()}
    mock_tickers_cls.return_value = tickers_obj

    result = compute_summary(csv_path)

    # TWD position: 100 * 920 = 92000, cost 100 * 580 = 58000
    tsmc = next(p for p in result["positions"] if p["ticker"] == "2330.TW")
    assert tsmc["current_value"] == pytest.approx(92000.0)
    assert tsmc["cost_value"] == pytest.approx(58000.0)
    assert tsmc["gain_loss"] == pytest.approx(34000.0)
    assert tsmc["gain_loss_pct"] == pytest.approx(58.62, rel=0.01)

    # USD position: 5 * 480 = 2400, cost 5 * 420 = 2100
    voo = next(p for p in result["positions"] if p["ticker"] == "VOO")
    assert voo["current_value"] == pytest.approx(2400.0)
    assert voo["cost_value"] == pytest.approx(2100.0)

    # by_currency grouping
    assert "TWD" in result["by_currency"]
    assert "USD" in result["by_currency"]
    assert result["by_currency"]["TWD"]["total_value"] == pytest.approx(92000.0)


@patch("yfinance.Tickers")
def test_failed_ticker_goes_to_errors(mock_tickers_cls, csv_path):
    tickers_obj = MagicMock()
    bad = MagicMock()
    bad.fast_info = {}
    tickers_obj.tickers = {
        "2330.TW": bad,
        "VOO": make_mock_ticker(480.0),
        "BTC-USD": make_mock_ticker(65000.0),
    }
    mock_tickers_cls.return_value = tickers_obj

    result = compute_summary(csv_path)
    assert any(e["ticker"] == "2330.TW" for e in result["errors"])
    assert any(p["ticker"] == "VOO" for p in result["positions"])


def test_render_us_row_contains_ticker_and_tag():
    h: USHolding = {
        "ticker": "NVDA", "name": "Nvidia Corp", "category": "TECH",
        "price": "$134.25", "day_change": "+2.34%", "day_change_up": True,
        "gain_loss": "+18.5%", "gain_loss_up": True,
    }
    html = _render_us_row(h, is_last=False)
    assert "NVDA" in html
    assert "Nvidia Corp" in html
    assert "TECH" in html
    assert "$134.25" in html
    assert "+2.34%" in html
    assert "+18.5%" in html
    assert "#48bb78" in html
    assert "border-bottom:1px solid" in html


def test_render_us_row_last_has_no_border():
    h: USHolding = {
        "ticker": "VT", "name": "Vanguard Total World", "category": "ETF",
        "price": "$100", "day_change": "-1%", "day_change_up": False,
        "gain_loss": "-5%", "gain_loss_up": False,
    }
    html = _render_us_row(h, is_last=True)
    assert "border-bottom" not in html
    assert "#fc8181" in html


def test_render_tw_row_contains_note():
    h: TWHolding = {
        "ticker": "2330", "name": "台積電",
        "price": "NT$980", "day_change": "-0.51%", "day_change_up": False,
        "note": "外資買超 12億",
    }
    html = _render_tw_row(h, is_last=False)
    assert "台積電" in html
    assert "NT$980" in html
    assert "外資買超 12億" in html
    assert "#fc8181" in html


def test_render_crypto_row_shows_quantity():
    h: CryptoHolding = {
        "ticker": "BTC", "name": "Bitcoin",
        "price": "$84,230", "day_change": "+1.2%", "day_change_up": True,
        "quantity": "0.2286 顆",
    }
    html = _render_crypto_row(h, is_last=True)
    assert "Bitcoin" in html
    assert "0.2286 顆" in html
    assert "border-bottom" not in html


def test_render_macro_rows_wraps_each_item():
    items = ["Fed 維持利率不變", "通膨數據略低於預期"]
    html = _render_macro_rows(items)
    assert "Fed 維持利率不變" in html
    assert "通膨數據略低於預期" in html
    assert html.count("<tr>") == 2


def test_render_macro_rows_empty():
    assert _render_macro_rows([]) == ""


def test_render_tip_rows_numbers_items():
    items = ["持續持有 VT", "注意 BTC 波動"]
    html = _render_tip_rows(items)
    assert ">1<" in html
    assert ">2<" in html
    assert "持續持有 VT" in html
    assert "注意 BTC 波動" in html


def test_render_tip_rows_last_item_no_padding():
    items = ["第一條提示", "最後一條提示"]
    html = _render_tip_rows(items)
    rows = html.split("</tr>")
    last_row = rows[-2]  # last non-empty split
    assert "padding-bottom:14px" not in last_row


def test_generate_daily_report_html_returns_complete_html():
    html = generate_daily_report_html(
        today_date="2026 年 04 月 16 日（星期四）",
        tw_total="NT$2,605,040",
        tw_change="▲ +1.40% 今日",
        tw_change_up=True,
        us_total="$171,149",
        us_change="▲ +1.34% 今日",
        us_change_up=True,
        crypto_total="$18,545",
        crypto_change="▼ -1.23% 今日",
        crypto_change_up=False,
        us_holdings=[
            {
                "ticker": "VT", "name": "Vanguard Total World", "category": "ETF",
                "price": "$100.50", "day_change": "+1.34%", "day_change_up": True,
                "gain_loss": "+5.2%", "gain_loss_up": True,
            }
        ],
        us_event="FOMC 會議紀要顯示聯準會偏向維持利率不變。",
        tw_holdings=[
            {
                "ticker": "加權指數", "name": "台股加權指數",
                "price": "21,500", "day_change": "+0.8%", "day_change_up": True,
                "note": "外資買超 45億",
            }
        ],
        crypto_holdings=[
            {
                "ticker": "BTC", "name": "Bitcoin",
                "price": "$84,230", "day_change": "-1.23%", "day_change_up": False,
                "quantity": "0.2286 顆",
            }
        ],
        macro_rows=["Fed 維持利率，通膨略低於預期。"],
        tip_rows=["持續持有 VT，分散風險。"],
    )

    assert html.startswith("<!DOCTYPE html>")
    assert "2026 年 04 月 16 日（星期四）" in html
    assert "NT$2,605,040" in html
    assert "$171,149" in html
    assert "$18,545" in html
    assert "VT" in html
    assert "加權指數" in html
    assert "Bitcoin" in html
    assert "0.2286 顆" in html
    assert "Fed 維持利率" in html
    assert "持續持有 VT" in html
    assert "[" not in html  # no unfilled placeholders


# --- send_telegram_file tests ---

class _FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return b'{"ok":true}'

    def decode(self):
        return '{"ok":true}'


def test_send_telegram_file_success(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    with patch("urllib.request.urlopen", return_value=_FakeResponse(200)):
        result = send_telegram_file(
            html_content="<h1>test</h1>",
            filename="test.html",
        )

    assert "✅" in result
    assert "123456" in result


def test_send_telegram_file_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    result = send_telegram_file(html_content="<h1>test</h1>")

    assert result == "Error: TELEGRAM_BOT_TOKEN not set"


def test_send_telegram_file_missing_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = send_telegram_file(html_content="<h1>test</h1>")

    assert result == "Error: TELEGRAM_CHAT_ID not set"


def test_send_telegram_file_api_error(monkeypatch):
    import urllib.error
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "bad-id")

    error = urllib.error.HTTPError(
        url="", code=400, msg="Bad Request", hdrs=None, fp=None  # type: ignore
    )
    error.read = lambda n=-1: b"Bad Request"

    with patch("urllib.request.urlopen", side_effect=error):
        result = send_telegram_file(html_content="<h1>test</h1>")

    assert "Error 400" in result
