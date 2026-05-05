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

## Memory Files

Persistent state lives in the `memory/` directory (path configured via `researcher_memory_path`):

| File | Written by | Read by |
|---|---|---|
| `RESEARCH-LOG.md` | premarket, midday, daily_summary workflows | daily_summary, weekly_review, chat agent |
| `PORTFOLIO-LOG.md` | daily_summary (close snapshot) | weekly_review |
| `TRANSACTION-LOG.md` | `MarkdownTransactionLog.append` (via mutation handlers) | daily_summary (today), weekly_review (this week), chat agent (last N days) |
| `CHAT-LOG.md` | `_append_chat_log` in chat.py | chat agent (`read_chat_log` tool) |
| `INVESTMENT-STRATEGY.md` | manual | premarket workflow, chat agent |
| `WEEKLY-REVIEW.md` | weekly_review workflow | — |

`TRANSACTION-LOG.md` uses `## YYYY-MM-DD HH:MM ACTION TICKER` section headers. Query it with `TransactionLog.entries_since(date)` — never with `last_n_entries`, which counts sections rather than spanning a time window.

## DI and the TransactionLog Interface

`TransactionLog` in `interfaces/ports.py` is the stable contract for transaction persistence. The current implementation is `MarkdownTransactionLog` in `services/transaction_log.py`. To swap to SQLite: implement the Protocol in a new class, update the single construction site in `make_deps()` (workflow_deps.py) and `_make_deps()` (chat.py). No other files change.

Portfolio mutation handlers (`handle_update_holding`, `handle_add_holding`, `handle_remove_holding`) accept `transaction_log: TransactionLog | None = None`. Pass `None` in tests that don't need logging; pass a `MarkdownTransactionLog` instance in production callers.

## Configuration & Secrets

Use environment variables for runtime configuration: `PORTFOLIO_CSV_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_API_KEY`, and `TAVILY_API_KEY`. Optional: `CHAT_MODEL` overrides the model used by the free-chat agent (default `google-gla:gemini-3-flash-preview`). Do not commit secrets or machine-specific `.env` files.

Keep local-only files out of git, including `.env`, `.mcp.json`, `.claude/`, and other machine-specific paths or settings.
