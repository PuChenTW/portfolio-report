import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from pydantic_ai import Agent, RunContext
from pydantic_ai.common_tools.tavily import tavily_search_tool
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.google import GoogleModelSettings

from portfolio.portfolio import TZ_TAIPEI
from portfolio.watchlist import load_watchlist
from researcher.config import settings
from researcher.handlers.commands import handle_add_holding, handle_remove_holding, handle_update_holding
from researcher.interfaces.ports import TransactionLog
from researcher.memory.io import append_entry, last_n_entries, read_file
from researcher.services.portfolio_service import PortfolioService
from researcher.services.transaction_log import MarkdownTransactionLog

_CHAT_LOG = "CHAT-LOG.md"


def _to_telegram_html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"```(?:\w+)?\n?(.*?)```", r"<pre><code>\1</code></pre>", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*\n]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    return text.strip()


# Per-user conversation history (in-memory; cleared on bot restart)
_sessions: dict[int, list[ModelMessage]] = {}


@dataclass
class _ChatDeps:
    memory_path: str
    watchlist_path: str
    portfolio_path: str
    transaction_log: TransactionLog


def _make_agent() -> Agent[_ChatDeps, str]:
    tools = [tavily_search_tool(settings.tavily_api_key)] if settings.tavily_api_key else []

    agent: Agent[_ChatDeps, str] = Agent(
        settings.chat_model,
        deps_type=_ChatDeps,
        tools=tools,
        output_type=str,
        model_settings=GoogleModelSettings(google_thinking_config={"include_thoughts": False}),
        system_prompt=(
            "你是一位專業的投資研究助理，熟悉台灣、美國股市和加密貨幣。你可以使用工具存取用戶的投資組合、觀察名單、研究紀錄和過去的對話紀錄，也可以搜尋網路取得最新市場資訊。你也可以透過工具更新、新增或移除持倉，但必須在使用者明確確認後才能執行。請用台灣繁體中文回答，回答簡潔、有見地。"
        ),
    )

    @agent.tool
    def get_portfolio(ctx: RunContext[_ChatDeps]) -> str:
        """Fetch current portfolio holdings and performance summary."""
        try:
            summary = PortfolioService().fetch_summary()
            return json.dumps(summary, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"無法取得投資組合: {e}"

    @agent.tool
    def get_watchlist(ctx: RunContext[_ChatDeps]) -> str:
        """Fetch the current watchlist entries."""
        try:
            entries = load_watchlist(ctx.deps.watchlist_path)
            if not entries:
                return "觀察名單為空。"
            return "\n".join(f"{e.ticker} {e.name}: {e.note or '(無備註)'}" for e in entries)
        except Exception as e:
            return f"無法取得觀察名單: {e}"

    @agent.tool
    def read_chat_log(ctx: RunContext[_ChatDeps], n: int = 10) -> str:
        """Read the last n exchanges from the conversation log to recall past discussions."""
        path = os.path.join(ctx.deps.memory_path, _CHAT_LOG)
        return last_n_entries(path, n) or "(無對話紀錄)"

    @agent.tool
    def read_research_log(ctx: RunContext[_ChatDeps], n: int = 5) -> str:
        """Read the last n entries from the research log (premarket/midday/weekly notes)."""
        path = os.path.join(ctx.deps.memory_path, "RESEARCH-LOG.md")
        return last_n_entries(path, n) or "(無研究紀錄)"

    @agent.tool
    def read_strategy(ctx: RunContext[_ChatDeps]) -> str:
        """Read the investment strategy document."""
        path = os.path.join(ctx.deps.memory_path, "INVESTMENT-STRATEGY.md")
        return read_file(path) or "(策略文件尚未設定)"

    @agent.tool
    def save_note(ctx: RunContext[_ChatDeps], content: str) -> str:
        """Save an explicit research insight or action item to the research log."""
        now = datetime.now(TZ_TAIPEI)
        entry = f"## {now.strftime('%Y-%m-%d')} Chat Note\n{content}"
        path = os.path.join(ctx.deps.memory_path, "RESEARCH-LOG.md")
        append_entry(path, entry)
        return "已儲存至研究紀錄。"

    @agent.tool
    def update_holding(ctx: RunContext[_ChatDeps], ticker: str, shares: float, cost_price: float, reason: str = "") -> str:
        """Update shares and average cost for an existing holding. reason: why this trade was made. Only call after user confirms."""
        return handle_update_holding([ticker, str(shares), str(cost_price)], ctx.deps.portfolio_path, reason, ctx.deps.transaction_log)

    @agent.tool
    def add_holding(ctx: RunContext[_ChatDeps], ticker: str, name: str, shares: float, cost_price: float, currency: str, category: str, reason: str = "") -> str:
        """Add a new holding. currency: TWD or USD. category: 台股/台灣ETF/美股/美國ETF/加密貨幣. reason: investment thesis. Only call after user confirms."""
        return handle_add_holding([ticker, name, str(shares), str(cost_price), currency, category], ctx.deps.portfolio_path, reason, ctx.deps.transaction_log)

    @agent.tool
    def remove_holding(ctx: RunContext[_ChatDeps], ticker: str, reason: str = "") -> str:
        """Remove a holding from the portfolio. reason: why selling/exiting. Only call after user confirms."""
        return handle_remove_holding([ticker], ctx.deps.portfolio_path, reason, ctx.deps.transaction_log)

    @agent.tool
    def read_transaction_log(ctx: RunContext[_ChatDeps], since_days: int = 30) -> str:
        """Read portfolio transactions from the last since_days days (default 30)."""
        since = date.today() - timedelta(days=since_days)
        return ctx.deps.transaction_log.entries_since(since) or "(無持倉異動紀錄)"

    return agent


_agent: Agent[_ChatDeps, str] | None = None


def _get_agent() -> Agent[_ChatDeps, str]:
    global _agent
    if _agent is None:
        _agent = _make_agent()
    return _agent


def _make_deps() -> _ChatDeps:
    memory_path = settings.researcher_memory_path
    return _ChatDeps(
        memory_path=memory_path,
        watchlist_path=settings.watchlist_csv_path,
        portfolio_path=settings.portfolio_csv_path,
        transaction_log=MarkdownTransactionLog(
            os.path.join(memory_path, "TRANSACTION-LOG.md")
        ),
    )


def _append_chat_log(user_msg: str, bot_reply: str) -> None:
    """Append a single exchange to CHAT-LOG.md immediately after each turn."""
    now = datetime.now(TZ_TAIPEI)
    entry = f"## {now.strftime('%Y-%m-%d %H:%M')}\n**User**: {user_msg}\n**Bot**: {bot_reply}"
    path = os.path.join(settings.researcher_memory_path, _CHAT_LOG)
    try:
        append_entry(path, entry)
    except Exception as e:
        print(f"[warn] chat log write failed: {e}", file=sys.stderr)


async def handle_chat(message: str, user_id: int) -> str:
    """Handle a free-form chat message with per-user multi-turn history."""
    agent = _get_agent()
    history = _sessions.get(user_id, [])
    try:
        result = await agent.run(message, deps=_make_deps(), message_history=history)
        _sessions[user_id] = result.all_messages()
        reply = _to_telegram_html(result.output)
        _append_chat_log(message, reply)
        return reply
    except Exception as e:
        print(f"[warn] chat failed for user {user_id}: {e}", file=sys.stderr)
        return "抱歉，目前無法處理您的訊息，請稍後再試。"


def reset_chat_session(user_id: int) -> str:
    """Clear the in-memory conversation history for a user."""
    _sessions.pop(user_id, None)
    return "對話已重置，開始新的對話。"
