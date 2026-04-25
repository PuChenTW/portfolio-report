from dataclasses import dataclass


@dataclass
class ResearchEntry:
    date: str
    market: str
    content: str


@dataclass
class PortfolioSnapshot:
    date: str
    market: str
    content: str
