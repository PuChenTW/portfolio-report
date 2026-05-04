# Project Mission

This project is an **AI-driven investment portfolio manager** — a personal financial steward that runs autonomously, much like OpenClaw or Hermes AI Agent in spirit. It monitors holdings, writes research reports, and answers investment questions on behalf of the user.

## What It Does

The system runs as a persistent agent with three main responsibilities:

1. **Tracking** — Fetches live prices for the user's portfolio on a schedule (pre-market, midday, close). Calculates P&L, flags notable moves, and persists findings to a research log.
2. **Reporting** — Generates daily summaries (pre-market outlook, midday check-in, end-of-day close insight) and a weekly portfolio reflection. Delivers them via Telegram.
3. **Answering** — Responds to free-form investment questions in a multi-turn chat over Telegram, with access to the portfolio, watchlist, research log, strategy notes, and chat history as tool-readable memory.

## Agent Design Philosophy

- **Scheduled, not reactive.** The core loop is cron-driven: pre-market → midday → close → weekly. Each workflow is a self-contained function with injected dependencies (data, memory, notifier).
- **Memory over state.** Persistent knowledge lives in markdown files (`RESEARCH-LOG.md`, `CHAT-LOG.md`, strategy notes). Agents read and append; there is no database.
- **Tool-augmented LLM.** Research agents use Tavily for live web search; analysis agents work only from local data. PydanticAI is the agent framework.
- **Delivery via Telegram.** All output goes to the user's Telegram chat — HTML report attachments for rich summaries, MarkdownV2 inline messages for alerts and insights.
- **Fail-safe pipeline.** News failures fall back gracefully; price errors are surfaced in the report but never crash the pipeline.

## Intended Scope

Single-user, personal-use system. Not designed for multi-tenancy, public APIs, or real-time trading. The goal is high-quality daily insight and a conversational interface — not automated execution.

---

# Repository Structure & Module Organization

This repository is a `uv` workspace with three Python packages:

- `portfolio-core/`: shared portfolio logic in `portfolio/`, plus tests in `portfolio-core/tests/`.
- `mcp-server/`: MCP server entry point in `server.py` and sample data in `portfolio.csv`.
- `researcher/`: Telegram bot and scheduled research agent, with pipeline logic in `researcher/pipeline/`, workflows in `researcher/workflows/`, memory persistence in `researcher/memory/`, command handlers in `researcher/handlers/`, and a layered service architecture in `researcher/interfaces/`, `researcher/services/`, and `researcher/infra/`.

Keep shared domain logic in `portfolio-core`. `mcp-server` should stay thin and expose tools only. `researcher` owns the pipeline, research, scheduling, and delivery.

Core modules:

- `portfolio-core/portfolio/portfolio.py`: CSV loading, batched price fetches, and portfolio summary calculation.
- `portfolio-core/portfolio/report.py`: HTML report rendering, holding view models, and Telegram MarkdownV2 message formatting.
- `portfolio-core/portfolio/telegram.py`: Telegram delivery — `send_telegram_file` (HTML attachment) and `send_telegram_messages` (inline MarkdownV2 messages).
- `researcher/pipeline/data.py`: portfolio fetch, holding transformation, and total calculation.
- `researcher/pipeline/news.py`: news summarization via PydanticAI and Tavily. `search_news` is the Tavily-based morning pipeline. `generate_close_insight` (no Tavily) cross-references today's `RESEARCH-LOG.md` entries with close prices to produce a closing review; `_extract_today_research` filters the log to the relevant market and date.
- `researcher/workflows/daily_summary.py`: pipeline orchestration — runs data + close insight + format + send for TW or US market close. Reads today's pre-market and midday entries from `RESEARCH-LOG.md`; uses `generate_close_insight` (no Tavily) to cross-reference research with actual close prices; falls back to `search_news` if no today's entries exist. Appends a `Close Insight` section to `RESEARCH-LOG.md` after sending.
- `researcher/workflows/premarket.py`: pre-market research and alert delivery.
- `researcher/workflows/midday.py`: US midday price alert and thesis check.
- `researcher/workflows/weekly_review.py`: weekly portfolio reflection.
- `researcher/handlers/chat.py`: free-form multi-turn chat — singleton PydanticAI agent with `get_portfolio`, `get_watchlist`, `read_chat_log`, `read_research_log`, `read_strategy`, and `save_note` tools; per-user history in `_sessions`; each exchange appended to `CHAT-LOG.md` immediately via `_append_chat_log`; `reset_chat_session` clears in-memory history only.
- `researcher/handlers/commands.py`: pure (non-async) handler functions for watchlist, alert, and portfolio mutation — `handle_watchlist`, `handle_alert`, `handle_update_holding`, `handle_add_holding`, `handle_remove_holding`, `handle_holdings`, `handle_status`. Called by both `bot.py` and `interactive.py`.
- `researcher/handlers/interactive.py`: interactive mini-apps for `/watchlist`, `/alert`, and `/update` — `ConversationHandler` factories (`build_watchlist_conversation`, `build_alert_conversation`, `build_update_conversation`) with inline keyboard flows and guided text prompts; `/update` supports Edit, Add, and Remove sub-flows.
- `researcher/memory/io.py`: read/append/query markdown memory files.
- `researcher/interfaces/ports.py`: `Notifier`, `PortfolioReader`, and `MemoryReader` Protocol definitions — the DI contracts all workflows depend on.
- `researcher/services/agent_runner.py`: `make_search_agent`, `make_analysis_agent`, `run_agent_sync`, `run_agent_async` — single source for PydanticAI agent construction and exponential-backoff retry. `make_search_agent` attaches Tavily; `make_analysis_agent` has no tools (local-data analysis only).
- `researcher/services/memory_service.py`: `MemoryService` — concrete `MemoryReader` wrapping `memory/io.py`.
- `researcher/services/portfolio_service.py`: `PortfolioService` — concrete `PortfolioReader` wrapping `pipeline/data.py` and `portfolio.portfolio`.
- `researcher/services/workflow_deps.py`: `WorkflowDeps` dataclass and `make_deps()` factory — composition root for injecting services into workflows.
- `researcher/infra/telegram.py`: `TelegramNotifier` — concrete `Notifier` adapter over `portfolio.telegram`.

---

# Developer Guide

For build commands, coding style, testing guidelines, commit conventions, and configuration, see @DEVELOPMENT.md
