import os

from portfolio.portfolio import compute_summary
from portfolio.report import CryptoHolding, TWHolding, USHolding
from researcher.pipeline.data import build_holdings, build_totals, fetch_portfolio


class PortfolioService:
    def fetch(self) -> dict:
        return fetch_portfolio()

    def fetch_summary(self) -> dict:
        csv_path = os.environ.get("PORTFOLIO_CSV_PATH", "./portfolio.csv")
        return compute_summary(csv_path)

    def build_holdings(self, data: dict) -> tuple[list[USHolding], list[TWHolding], list[CryptoHolding]]:
        return build_holdings(data)

    def build_totals(self, data: dict) -> dict:
        return build_totals(data)
