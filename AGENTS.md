# Repository Guidelines

## Project Structure & Module Organization

This repository is a `uv` workspace with three Python packages:

- `portfolio-core/`: shared portfolio logic in `portfolio/`, plus tests in `portfolio-core/tests/`.
- `mcp-server/`: MCP server entry point in `server.py` and sample data in `portfolio.csv`.
- `researcher/`: Telegram bot and scheduled research agent, with pipeline logic in `researcher/pipeline/`, workflows in `researcher/workflows/`, memory persistence in `researcher/memory/`, and command handlers in `researcher/handlers/`.

Keep shared domain logic in `portfolio-core`. `mcp-server` should stay thin and expose tools only. `researcher` owns the pipeline, research, scheduling, and delivery.

Core modules:

- `portfolio-core/portfolio/portfolio.py`: CSV loading, batched price fetches, and portfolio summary calculation.
- `portfolio-core/portfolio/report.py`: HTML report rendering, holding view models, and Telegram MarkdownV2 message formatting.
- `portfolio-core/portfolio/telegram.py`: Telegram delivery — `send_telegram_file` (HTML attachment) and `send_telegram_messages` (inline MarkdownV2 messages).
- `researcher/pipeline/data.py`: portfolio fetch, holding transformation, and total calculation.
- `researcher/pipeline/news.py`: news summarization via PydanticAI and Tavily.
- `researcher/workflows/daily_summary.py`: pipeline orchestration — runs data + news + format + send for TW or US market close.
- `researcher/workflows/premarket.py`: pre-market research and alert delivery.
- `researcher/workflows/midday.py`: US midday price alert and thesis check.
- `researcher/workflows/weekly_review.py`: weekly portfolio reflection.
- `researcher/memory/io.py`: read/append/query markdown memory files.

## Build, Test, and Development Commands

Run commands from the repo root unless noted otherwise:

- `uv sync`: install workspace dependencies into `.venv`.
- `uv run --package portfolio-core pytest portfolio-core/tests/ -v`: run the portfolio-core test suite.
- `uv run --package researcher pytest researcher/tests/ -v`: run the researcher test suite.
- `uv run --package mcp-server python mcp-server/server.py`: start the MCP server over stdio.
- `cd mcp-server && uv run mcp dev server.py`: open the MCP inspector for local tool testing.
- `uv run --package researcher python -m researcher`: start the Telegram bot and scheduler.
- `uv run pyright`: run static type checking using `pyrightconfig.json`.

## Coding Style & Naming Conventions

Target Python 3.13. Use 4-space indentation, type hints on public functions, and `snake_case` for modules, functions, and variables. Keep functions focused, prefer early returns, and avoid unnecessary abstraction. Comments should explain why, not restate code. No formatter is configured here, so match the surrounding style and keep imports tidy.

Design constraints:

- No FX conversion. Keep totals grouped by currency.
- Batch quote fetches where possible. Do not regress into per-ticker network calls when one batched call works.
- Failed price fetches should be reported in `errors` and should not crash the whole summary or report pipeline.
- If the news step fails, fall back to defaults and continue report generation.

## Testing Guidelines

Tests use `pytest`. `portfolio-core/tests/` covers shared portfolio logic; `researcher/tests/` covers pipeline and workflow logic. Prefer fast, deterministic tests with mocks for network calls such as `yfinance` and Telegram delivery. Add or update tests alongside behavior changes — shared logic in `portfolio-core`, pipeline/research logic in `researcher`.

## Commit & Pull Request Guidelines

Follow the commit style already in history: `feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `chore: ...`. Keep subjects short and imperative. PRs should explain the user-visible change, note any config or env var impact, and include the exact verification command(s) you ran. Attach screenshots or sample HTML output when changing report rendering or MCP-visible responses.

## Configuration & Secrets

Use environment variables for runtime configuration: `PORTFOLIO_CSV_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_API_KEY`, and `TAVILY_API_KEY`. Do not commit secrets or machine-specific `.env` files.

Keep local-only files out of git, including `.env`, `.mcp.json`, `.claude/`, and other machine-specific paths or settings.
