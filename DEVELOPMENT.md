# Developer Guide

This file covers build commands, coding conventions, testing, and configuration for contributors and AI agents working on implementation tasks.

## Build, Test, and Development Commands

Run commands from the repo root unless noted otherwise:

- `uv sync`: install workspace dependencies into `.venv`.
- `uv run --package portfolio-core pytest portfolio-core/tests/ -v`: run the portfolio-core test suite.
- `uv run --package researcher pytest researcher/tests/ -v`: run the researcher test suite.
- `uv run --package mcp-server python mcp-server/server.py`: start the MCP server over stdio.
- `cd mcp-server && uv run mcp dev server.py`: open the MCP inspector for local tool testing.
- `uv run --package researcher python -m researcher`: start the Telegram bot and scheduler.
- `uv run pyright`: run static type checking using `pyrightconfig.json`.
- `uv run ruff format .`: format all Python files across the workspace.
- `uv run ruff format --check .`: check formatting without modifying files.

## Coding Style & Naming Conventions

Target Python 3.13. Use 4-space indentation, type hints on public functions, and `snake_case` for modules, functions, and variables. Keep functions focused, prefer early returns, and avoid unnecessary abstraction. Comments should explain why, not restate code. Run `uv run ruff format .` before committing to keep style consistent.

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

Use environment variables for runtime configuration: `PORTFOLIO_CSV_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_API_KEY`, and `TAVILY_API_KEY`. Optional: `CHAT_MODEL` overrides the model used by the free-chat agent (default `google-gla:gemini-3-flash-preview`). Do not commit secrets or machine-specific `.env` files.

Keep local-only files out of git, including `.env`, `.mcp.json`, `.claude/`, and other machine-specific paths or settings.
