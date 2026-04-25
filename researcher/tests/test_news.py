from researcher.pipeline.news import _build_portfolio_context
from portfolio.report import USHolding, TWHolding, CryptoHolding

_SUMMARY = {
    "positions": [
        {
            "ticker": "MSFT", "currency": "USD", "category": "美股",
            "current_value": 1200.0, "gain_loss_pct": 18.5,
            "pct_of_currency_total": 50.0, "pct_of_global_usd": 30.0,
        },
        {
            "ticker": "2330.TW", "currency": "TWD", "category": "台股",
            "current_value": 92000.0, "gain_loss_pct": 58.62,
            "pct_of_currency_total": 100.0, "pct_of_global_usd": 45.0,
        },
        {
            "ticker": "BTC-USD", "currency": "USD", "category": "加密貨幣",
            "current_value": 3250.0, "gain_loss_pct": 8.3,
            "pct_of_currency_total": 50.0, "pct_of_global_usd": 25.0,
        },
    ],
    "by_currency": {
        "USD": {
            "total_value": 4450.0,
            "by_category": {
                "美股": {"value": 1200.0, "pct_of_currency_total": 27.0},
                "加密貨幣": {"value": 3250.0, "pct_of_currency_total": 73.0},
            },
        },
        "TWD": {
            "total_value": 92000.0,
            "by_category": {
                "台股": {"value": 92000.0, "pct_of_currency_total": 100.0},
            },
        },
    },
    "fx_rate": 32.0,
    "global_total_usd": 7325.0,
    "currency_pct": {"USD": 60.7, "TWD": 39.3},
}

_US: list[USHolding] = [
    {
        "ticker": "MSFT", "name": "Microsoft", "category": "TECH",
        "price": "$415.00", "day_change": "+1.2%", "day_change_up": True,
        "gain_loss": "+18.5%", "gain_loss_up": True,
    }
]

_TW: list[TWHolding] = [
    {
        "ticker": "2330.TW", "name": "台積電",
        "price": "NT$920", "day_change": "+0.5%", "day_change_up": True,
        "note": "—",
    }
]

_CRYPTO: list[CryptoHolding] = [
    {
        "ticker": "BTC", "name": "Bitcoin",
        "price": "$65,000", "day_change": "+2.0%", "day_change_up": True,
        "quantity": "0.05 顆",
    }
]


def test_build_portfolio_context_top_level_keys():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    assert "portfolio_overview" in ctx
    assert "categories" in ctx
    assert "positions" in ctx


def test_build_portfolio_context_overview_fields():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    overview = ctx["portfolio_overview"]
    assert overview["fx_rate"] == 32.0
    assert overview["global_total_usd"] == 7325.0
    assert overview["currency_allocation"] == {"USD": 60.7, "TWD": 39.3}


def test_build_portfolio_context_positions_have_allocation():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    for pos in ctx["positions"]:
        assert "pct_of_currency" in pos
        assert "pct_global" in pos
        assert "ticker" in pos


def test_build_portfolio_context_us_position_gain_loss():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    msft = next(p for p in ctx["positions"] if p["ticker"] == "MSFT")
    assert msft["gain_loss"] == "+18.5%"
    assert msft["pct_of_currency"] == 50.0
    assert msft["pct_global"] == 30.0


def test_build_portfolio_context_tw_position():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    tsmc = next(p for p in ctx["positions"] if p["ticker"] == "2330.TW")
    assert tsmc["pct_of_currency"] == 100.0
    assert tsmc["pct_global"] == 45.0


def test_build_portfolio_context_crypto_position():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    btc = next(p for p in ctx["positions"] if "BTC" in p["ticker"])
    assert "quantity" in btc
    assert btc["pct_of_currency"] == 50.0


def test_build_portfolio_context_categories():
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, _SUMMARY)
    assert len(ctx["categories"]) > 0
    for cat in ctx["categories"]:
        assert "name" in cat
        assert "currency" in cat
        assert "pct_of_currency" in cat


def test_build_portfolio_context_no_fx():
    summary_no_fx = {**_SUMMARY, "fx_rate": None, "global_total_usd": None, "currency_pct": None}
    ctx = _build_portfolio_context(_US, _TW, _CRYPTO, summary_no_fx)
    assert ctx["portfolio_overview"]["fx_rate"] is None
    assert ctx["portfolio_overview"]["global_total_usd"] is None
    # positions still have pct_of_currency from summary
    for pos in ctx["positions"]:
        assert "pct_of_currency" in pos
