from dataclasses import dataclass, field

from researcher.config import settings
from researcher.infra.telegram import TelegramNotifier
from researcher.interfaces.ports import MemoryReader, Notifier, PortfolioReader
from researcher.services.memory_service import MemoryService
from researcher.services.portfolio_service import PortfolioService


@dataclass
class WorkflowDeps:
    notifier: Notifier
    memory: MemoryReader
    portfolio: PortfolioReader | None = field(default=None)


def make_deps() -> WorkflowDeps:
    return WorkflowDeps(
        notifier=TelegramNotifier(),
        memory=MemoryService(settings.researcher_memory_path),
        portfolio=PortfolioService(),
    )
