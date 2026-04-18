import os
from typing import Any

import yfinance as yf
from mcp.server.fastmcp import FastMCP

from portfolio.portfolio import compute_summary, now_taipei

CSV_PATH = os.environ.get("PORTFOLIO_CSV_PATH", "./portfolio.csv")

mcp = FastMCP("portfolio-mcp")


@mcp.tool()
def get_portfolio_summary() -> dict[str, Any]:
    """Read holdings CSV, fetch live prices, and return P&L grouped by currency."""
    return compute_summary(CSV_PATH)


@mcp.tool()
def get_price(ticker: str) -> dict[str, Any]:
    """Fetch the live price for a single ticker."""
    try:
        info = yf.Ticker(ticker).fast_info
        price = float(info["lastPrice"])
        currency = info.get("currency", "UNKNOWN")
    except (KeyError, TypeError, ValueError):
        return {
            "ticker": ticker,
            "error": "Failed to fetch price",
            "fetched_at": now_taipei(),
        }
    return {
        "ticker": ticker,
        "price": price,
        "currency": currency,
        "fetched_at": now_taipei(),
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
