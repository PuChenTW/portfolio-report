# Repository Guidelines

## Project Structure & Module Organization

This repository is a `uv` workspace with three Python packages:

- `portfolio-core/`: shared portfolio logic in `portfolio/`, plus tests in `portfolio-core/tests/`.
- `mcp-server/`: MCP server entry point in `server.py` and sample data in `portfolio.csv`.
- `daily-report/`: daily report pipeline, with orchestration in `pipeline/`, a thin entry point in `daily_report_pipeline.py`, and cron-friendly execution in `run_daily_report.sh`.

Keep shared domain logic in `portfolio-core`. `mcp-server` should stay thin and expose tools only; `daily-report` should orchestrate reporting and delivery.

Core modules:

- `portfolio-core/portfolio/portfolio.py`: CSV loading, batched price fetches, and portfolio summary calculation.
- `portfolio-core/portfolio/report.py`: HTML report rendering, holding view models, and Telegram MarkdownV2 message formatting.
- `portfolio-core/portfolio/telegram.py`: Telegram delivery — `send_telegram_file` (HTML attachment) and `send_telegram_messages` (inline MarkdownV2 messages).
- `daily-report/pipeline/data.py`: portfolio fetch, holding transformation, and total calculation.
- `daily-report/pipeline/news.py`: news summarization via PydanticAI and Tavily.
- `daily-report/pipeline/run.py`: pipeline orchestration.

## Build, Test, and Development Commands

Run commands from the repo root unless noted otherwise:

- `uv sync`: install workspace dependencies into `.venv`.
- `uv run --package portfolio-core pytest portfolio-core/tests/ -v`: run the current test suite.
- `uv run --package mcp-server python mcp-server/server.py`: start the MCP server over stdio.
- `cd mcp-server && uv run mcp dev server.py`: open the MCP inspector for local tool testing.
- `cd daily-report && uv run python daily_report_pipeline.py`: run the daily report manually.
- `./daily-report/run_daily_report.sh`: run the cron-oriented wrapper with env loading and log output.
- `uv run pyright`: run static type checking using `pyrightconfig.json`.

## Coding Style & Naming Conventions

Target Python 3.13. Use 4-space indentation, type hints on public functions, and `snake_case` for modules, functions, and variables. Keep functions focused, prefer early returns, and avoid unnecessary abstraction. Comments should explain why, not restate code. No formatter is configured here, so match the surrounding style and keep imports tidy.

Design constraints:

- No FX conversion. Keep totals grouped by currency.
- Batch quote fetches where possible. Do not regress into per-ticker network calls when one batched call works.
- Failed price fetches should be reported in `errors` and should not crash the whole summary or report pipeline.
- If the news step fails, fall back to defaults and continue report generation.

## Testing Guidelines

Tests use `pytest` and currently live under `portfolio-core/tests/` as `test_*.py`. Prefer fast, deterministic tests with mocks for network calls such as `yfinance` and Telegram delivery. Add or update tests alongside behavior changes in `portfolio-core`; for `mcp-server` and `daily-report`, cover core logic in shared modules whenever possible.

## Commit & Pull Request Guidelines

Follow the commit style already in history: `feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `chore: ...`. Keep subjects short and imperative. PRs should explain the user-visible change, note any config or env var impact, and include the exact verification command(s) you ran. Attach screenshots or sample HTML output when changing report rendering or MCP-visible responses.

## Configuration & Secrets

Use environment variables for runtime configuration: `PORTFOLIO_CSV_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_API_KEY`, and `TAVILY_API_KEY`. Do not commit secrets or machine-specific `.env` files.

Keep local-only files out of git, including `.env`, `.mcp.json`, `.claude/`, and other machine-specific paths or settings.
