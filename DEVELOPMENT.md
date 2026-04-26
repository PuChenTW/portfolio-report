# Development Guide

## Project Structure

This is a `uv` workspace with three Python packages:

```
portfolio-mcp/
├── portfolio-core/        # Shared portfolio logic (prices, reports, Telegram delivery)
│   ├── portfolio/
│   │   ├── portfolio.py   # CSV loading, batch yfinance fetches, P&L calculation
│   │   ├── report.py      # HTML rendering, MarkdownV2 formatting, holding view models
│   │   └── telegram.py    # send_telegram_file, send_telegram_messages
│   └── tests/
├── mcp-server/            # Thin FastMCP server exposing portfolio tools to Claude
│   └── server.py          # get_portfolio_summary, get_price tool definitions
└── researcher/            # Telegram bot + APScheduler + AI research pipelines
    ├── __main__.py        # Entry point: starts bot + scheduler
    ├── bot.py             # Telegram Application setup, command registration
    ├── scheduler.py       # APScheduler cron job definitions
    ├── interfaces/
    │   └── ports.py       # Notifier, PortfolioReader, MemoryReader Protocols
    ├── services/
    │   ├── agent_runner.py      # PydanticAI agent construction + retry
    │   ├── memory_service.py    # MemoryReader impl wrapping memory/io.py
    │   ├── portfolio_service.py # PortfolioReader impl wrapping portfolio-core
    │   └── workflow_deps.py     # WorkflowDeps dataclass + make_deps() factory
    ├── infra/
    │   └── telegram.py    # TelegramNotifier: concrete Notifier adapter
    ├── handlers/          # Telegram command and message handlers
    ├── pipeline/
    │   ├── data.py        # fetch_portfolio, build_holdings, build_totals
    │   └── news.py        # AI news summarization via PydanticAI + Tavily
    ├── workflows/
    │   ├── daily_summary.py   # Full P&L + news + HTML/MarkdownV2 report
    │   ├── premarket.py       # Premarket research and alert delivery
    │   ├── midday.py          # US midday price alert and thesis check
    │   └── weekly_review.py   # Weekly portfolio reflection
    └── memory/
        └── io.py          # read/append/query markdown memory files
```

## Architecture

The `researcher` package uses a layered architecture to keep business logic testable and independent of external services:

```
interfaces/ports.py   ← Protocol definitions (Notifier, PortfolioReader, MemoryReader)
        ↑
services/             ← Concrete implementations injected at startup
        ↑
workflows/            ← Orchestration — depend only on Protocol interfaces
        ↑
infra/                ← External adapters (Telegram, etc.)
```

**Dependency injection** is handled by `WorkflowDeps` in `services/workflow_deps.py`. The `make_deps()` factory wires together the concrete implementations. Workflows receive a `WorkflowDeps` instance and call methods on the Protocol interfaces — they never import `TelegramNotifier` or `PortfolioService` directly. This makes workflows trivially testable by passing mock implementations.

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `portfolio-core/portfolio/portfolio.py` | CSV loading, batched yfinance price fetches, portfolio P&L grouped by currency |
| `portfolio-core/portfolio/report.py` | HTML report rendering, holding view models, Telegram MarkdownV2 message formatting |
| `portfolio-core/portfolio/telegram.py` | `send_telegram_file` (HTML attachment), `send_telegram_messages` (inline MarkdownV2) |
| `mcp-server/server.py` | FastMCP server: `get_portfolio_summary`, `get_price` tool definitions |
| `researcher/interfaces/ports.py` | `Notifier`, `PortfolioReader`, `MemoryReader` Protocol definitions |
| `researcher/services/agent_runner.py` | `make_search_agent`, `run_agent_sync`, `run_agent_async` with exponential-backoff retry |
| `researcher/services/workflow_deps.py` | `WorkflowDeps` dataclass, `make_deps()` composition root |
| `researcher/infra/telegram.py` | `TelegramNotifier` — concrete `Notifier` wrapping `portfolio.telegram` |
| `researcher/pipeline/data.py` | Portfolio fetch, holding transformation, total calculation |
| `researcher/pipeline/news.py` | News summarization via PydanticAI + Tavily |
| `researcher/scheduler.py` | APScheduler cron job setup for all workflows |
| `researcher/memory/io.py` | Read/append/query markdown memory files |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORTFOLIO_CSV_PATH` | `./portfolio.csv` | Path to portfolio CSV file |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot API token (required) |
| `TELEGRAM_CHAT_ID` | — | Target Telegram chat ID (required) |
| `GOOGLE_API_KEY` | — | Google Gemini API key for PydanticAI (required for research) |
| `TAVILY_API_KEY` | — | Tavily search API key (required for news) |
| `WATCHLIST_CSV_PATH` | `./watchlist.csv` | Path to watchlist CSV |
| `PRICE_ALERTS_PATH` | `./price-alerts.yml` | Path to YAML price alerts file |
| `RESEARCHER_MEMORY_PATH` | `./memory` | Directory for markdown memory files |

## Development Commands

All commands run from the repo root unless noted.

```bash
# Install workspace dependencies
uv sync

# Run portfolio-core tests
uv run --package portfolio-core pytest portfolio-core/tests/ -v

# Run researcher tests
uv run --package researcher pytest researcher/tests/ -v

# Start the MCP server (stdio transport)
uv run --package mcp-server python mcp-server/server.py

# Open MCP inspector for local tool testing
cd mcp-server && uv run mcp dev server.py

# Start the Telegram bot + scheduler
uv run --package researcher python -m researcher

# Static type checking
uv run pyright

# Format all Python files
uv run ruff format .

# Check formatting without modifying files
uv run ruff format --check .
```

## Testing

Tests live in:
- `portfolio-core/tests/` — shared portfolio logic (price fetching, P&L calculation, report formatting)
- `researcher/tests/` — pipeline and workflow logic

**Philosophy:** mock network calls (`yfinance`, Telegram delivery, Tavily), not business logic. Tests should be fast and deterministic. Pass mock implementations of `Notifier`, `PortfolioReader`, and `MemoryReader` protocols directly to workflow functions — no patching required.

Example pattern:

```python
class FakeNotifier:
    def __init__(self):
        self.messages = []

    def send_messages(self, messages: list[str]) -> None:
        self.messages.extend(messages)

def test_daily_summary_sends_report():
    notifier = FakeNotifier()
    deps = WorkflowDeps(notifier=notifier, memory=FakeMemory(), portfolio=FakePortfolio())
    daily_summary.run("TW", deps)
    assert len(notifier.messages) > 0
```

## Adding a New Workflow

1. **Create the workflow file** at `researcher/workflows/<name>.py`. Define a `run(deps: WorkflowDeps)` function that uses only the Protocol interfaces on `deps`.

2. **Use deps interfaces**, not concrete classes:
   ```python
   from researcher.services.workflow_deps import WorkflowDeps

   def run(deps: WorkflowDeps) -> None:
       data = deps.portfolio.fetch()
       deps.notifier.send_messages(["Hello from new workflow"])
   ```

3. **Register in the scheduler** (`researcher/scheduler.py`):
   ```python
   import researcher.workflows.<name> as <name>

   scheduler.add_job(
       _wrap(<name>.run, deps),
       CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=_TZ_TW),
   )
   ```

4. **Optionally register a Telegram command** in `researcher/bot.py` and add a handler in `researcher/handlers/`.

5. **Write tests** in `researcher/tests/` with fake implementations of the Protocol interfaces.

## Coding Conventions

- **Python 3.13+** — use modern type hints (`list[str]`, `dict[str, int]`, `X | None`)
- **Type hints on all public functions**
- **`snake_case`** for modules, functions, and variables
- **4-space indentation**; formatter is Ruff (`uv run ruff format .`)
- **Early returns** — avoid deeply nested conditionals
- **Batch price fetches** — never regress to per-ticker `yfinance` calls
- **No FX conversion** — keep TWD and USD totals separate
- **Failed price fetches** go into `errors`, never raise and crash the pipeline
- **Comments explain why**, not what
- Run `uv run ruff format .` before every commit
