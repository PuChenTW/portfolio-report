import pytest
from portfolio.alerts import load_alerts, check_positions


@pytest.fixture
def rules_path(tmp_path):
    p = tmp_path / "price-alerts.yml"
    p.write_text("defaults:\n  stop_loss_pct: -0.15\n  take_profit_pct: 0.50\noverrides:\n  TSLA:\n    below: 200.0\n    above: 400.0\n")
    return str(p)


def test_load_alerts_defaults(rules_path):
    rules = load_alerts(rules_path)
    assert rules.defaults["stop_loss_pct"] == -0.15
    assert rules.defaults["take_profit_pct"] == 0.50


def test_load_alerts_overrides(rules_path):
    rules = load_alerts(rules_path)
    assert rules.overrides["TSLA"]["below"] == 200.0


def test_load_alerts_missing_file(tmp_path):
    rules = load_alerts(str(tmp_path / "nope.yml"))
    assert rules.defaults == {}
    assert rules.overrides == {}


def test_check_positions_stop_loss_pct(rules_path):
    rules = load_alerts(rules_path)
    positions = [{"ticker": "AAPL", "cost_price": 100.0, "current_price": 84.0, "is_cash": False}]
    alerts = check_positions(positions, rules)
    assert len(alerts) == 1
    assert alerts[0].ticker == "AAPL"
    assert alerts[0].kind == "below"


def test_check_positions_take_profit_pct(rules_path):
    rules = load_alerts(rules_path)
    positions = [{"ticker": "NVDA", "cost_price": 100.0, "current_price": 151.0, "is_cash": False}]
    alerts = check_positions(positions, rules)
    assert len(alerts) == 1
    assert alerts[0].kind == "above"


def test_check_positions_absolute_override(rules_path):
    rules = load_alerts(rules_path)
    positions = [{"ticker": "TSLA", "cost_price": 300.0, "current_price": 195.0, "is_cash": False}]
    alerts = check_positions(positions, rules)
    assert any(a.ticker == "TSLA" and a.kind == "below" for a in alerts)


def test_check_positions_cash_skipped(rules_path):
    rules = load_alerts(rules_path)
    positions = [{"ticker": "CASH_TWD", "cost_price": 1.0, "current_price": 1.0, "is_cash": True}]
    alerts = check_positions(positions, rules)
    assert alerts == []


def test_check_positions_no_alert_in_range(rules_path):
    rules = load_alerts(rules_path)
    positions = [{"ticker": "AAPL", "cost_price": 100.0, "current_price": 110.0, "is_cash": False}]
    alerts = check_positions(positions, rules)
    assert alerts == []
