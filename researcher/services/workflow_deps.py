import os
from dataclasses import dataclass, field

from researcher.config import settings
from researcher.infra.telegram import TelegramNotifier
from researcher.interfaces.ports import MemoryReader, Notifier, PortfolioReader, TransactionLog
from researcher.services.memory_service import MemoryService
from researcher.services.portfolio_service import PortfolioService
from researcher.services.transaction_log import MarkdownTransactionLog


@dataclass
class WorkflowDeps:
    notifier: Notifier
    memory: MemoryReader
    transaction_log: TransactionLog
    portfolio: PortfolioReader | None = field(default=None)


def make_deps() -> WorkflowDeps:
    memory_path = settings.researcher_memory_path
    return WorkflowDeps(
        notifier=TelegramNotifier(),
        memory=MemoryService(memory_path),
        transaction_log=MarkdownTransactionLog(
            os.path.join(memory_path, "TRANSACTION-LOG.md")
        ),
        portfolio=PortfolioService(),
    )
