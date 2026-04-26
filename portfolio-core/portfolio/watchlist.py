import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WatchlistEntry:
    ticker: str
    name: str
    note: str = ""


def load_watchlist(path: str) -> list[WatchlistEntry]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [WatchlistEntry(ticker=r["ticker"], name=r["name"], note=r.get("note", "")) for r in csv.DictReader(f)]


def add_ticker(path: str, entry: WatchlistEntry) -> None:
    existing = load_watchlist(path)
    if any(e.ticker == entry.ticker for e in existing):
        return
    existing.append(entry)
    _write(path, existing)


def remove_ticker(path: str, ticker: str) -> None:
    existing = load_watchlist(path)
    _write(path, [e for e in existing if e.ticker != ticker])


def _write(path: str, entries: list[WatchlistEntry]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "name", "note"])
        writer.writeheader()
        writer.writerows({"ticker": e.ticker, "name": e.name, "note": e.note} for e in entries)
