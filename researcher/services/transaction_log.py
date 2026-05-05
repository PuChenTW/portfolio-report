from datetime import date, datetime

from portfolio.portfolio import TZ_TAIPEI
from researcher.memory import io


class MarkdownTransactionLog:
    def __init__(self, path: str) -> None:
        self._path = path

    def append(self, ticker: str, action: str, detail: str, reason: str = "") -> None:
        now = datetime.now(TZ_TAIPEI)
        lines = [f"## {now.strftime('%Y-%m-%d %H:%M')} {action} {ticker}"]
        if detail:
            lines.append(detail)
        if reason:
            lines.append(f"Reason: {reason}")
        io.append_entry(self._path, "\n".join(lines))

    def entries_since(self, since: date) -> str:
        return io.entries_since(self._path, since)
