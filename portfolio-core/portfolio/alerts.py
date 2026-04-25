from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AlertRules:
    defaults: dict = field(default_factory=dict)
    overrides: dict = field(default_factory=dict)


@dataclass
class PriceAlert:
    ticker: str
    kind: str  # "above" | "below"
    threshold_price: float
    current_price: float


def load_alerts(path: str) -> AlertRules:
    p = Path(path)
    if not p.exists():
        return AlertRules()
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AlertRules(
        defaults=data.get("defaults", {}),
        overrides=data.get("overrides", {}),
    )


def check_positions(positions: list[dict], rules: AlertRules) -> list[PriceAlert]:
    alerts: list[PriceAlert] = []
    for p in positions:
        if p.get("is_cash"):
            continue
        ticker = p["ticker"]
        cost = p["cost_price"]
        current = p["current_price"]
        override = rules.overrides.get(ticker, {})

        # Absolute price thresholds (override)
        if "below" in override and current < override["below"]:
            alerts.append(PriceAlert(ticker, "below", override["below"], current))
        elif "above" in override and current > override["above"]:
            alerts.append(PriceAlert(ticker, "above", override["above"], current))
        else:
            # Percentage thresholds (defaults)
            stop_pct = rules.defaults.get("stop_loss_pct")
            take_pct = rules.defaults.get("take_profit_pct")
            if cost > 0:
                change_pct = (current - cost) / cost
                if stop_pct is not None and change_pct <= stop_pct:
                    alerts.append(PriceAlert(ticker, "below", cost * (1 + stop_pct), current))
                elif take_pct is not None and change_pct >= take_pct:
                    alerts.append(PriceAlert(ticker, "above", cost * (1 + take_pct), current))
    return alerts
