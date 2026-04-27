import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from pydantic_ai import Agent, RunContext
from pydantic_ai.common_tools.tavily import tavily_search_tool
from pydantic_ai.messages import ModelMessage

from portfolio.portfolio import TZ_TAIPEI
from portfolio.watchlist import load_watchlist
from researcher.memory.io import append_entry, last_n_entries, read_file
from researcher.services.portfolio_service import PortfolioService

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")
_WATCHLIST_PATH = os.environ.get("WATCHLIST_CSV_PATH", "./watchlist.csv")
_DEFAULT_MODEL = "google-gla:gemini-3-flash-preview"

# Per-user conversation history (in-memory; cleared on bot restart)
_sessions: dict[int, list[ModelMessage]] = {}


@dataclass
class _ChatDeps:
    memory_path: str
    watchlist_path: str


def _make_agent() -> Agent[_ChatDeps, str]:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    model = os.environ.get("CHAT_MODEL", _DEFAULT_MODEL)
    tools = [tavily_search_tool(api_key)] if api_key else []

    agent: Agent[_ChatDeps, str] = Agent(
        model,
        deps_type=_ChatDeps,
        tools=tools,
        output_type=str,
        system_prompt=("你是一位專業的投資研究助理，熟悉台灣、美國股市和加密貨幣。你可以使用工具存取用戶的投資組合、觀察名單和研究紀錄。請用台灣繁體中文回答，回答簡潔、有見地。"),
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
    def read_research_log(ctx: RunContext[_ChatDeps], n: int = 5) -> str:
        """Read the last n entries from the research log."""
        path = os.path.join(ctx.deps.memory_path, "RESEARCH-LOG.md")
        return last_n_entries(path, n) or "(無研究紀錄)"

    @agent.tool
    def read_strategy(ctx: RunContext[_ChatDeps]) -> str:
        """Read the investment strategy document."""
        path = os.path.join(ctx.deps.memory_path, "INVESTMENT-STRATEGY.md")
        return read_file(path) or "(策略文件尚未設定)"

    @agent.tool
    def save_note(ctx: RunContext[_ChatDeps], content: str) -> str:
        """Save a note or insight to the research log for long-term memory."""
        now = datetime.now(TZ_TAIPEI)
        entry = f"## {now.strftime('%Y-%m-%d')} Chat Note\n{content}"
        path = os.path.join(ctx.deps.memory_path, "RESEARCH-LOG.md")
        append_entry(path, entry)
        return "已儲存至研究紀錄。"

    return agent


_agent: Agent[_ChatDeps, str] | None = None


def _get_agent() -> Agent[_ChatDeps, str]:
    global _agent
    if _agent is None:
        _agent = _make_agent()
    return _agent


def _make_deps() -> _ChatDeps:
    return _ChatDeps(
        memory_path=_MEMORY_PATH,
        watchlist_path=_WATCHLIST_PATH,
    )


async def handle_chat(message: str, user_id: int) -> str:
    """Handle a free-form chat message with per-user multi-turn history."""
    agent = _get_agent()
    history = _sessions.get(user_id, [])
    try:
        result = await agent.run(message, deps=_make_deps(), message_history=history)
        _sessions[user_id] = result.all_messages()
        return result.output
    except Exception as e:
        print(f"[warn] chat failed for user {user_id}: {e}", file=sys.stderr)
        return "抱歉，目前無法處理您的訊息，請稍後再試。"


def reset_chat_session(user_id: int) -> str:
    """Clear the conversation history for a user."""
    _sessions.pop(user_id, None)
    return "對話已重置，開始新的對話。"


async def save_chat_to_memory(user_id: int) -> str:
    """Summarize the current conversation and save it to the research log."""
    history = _sessions.get(user_id)
    if not history:
        return "目前沒有對話紀錄可儲存。"
    agent = _get_agent()
    try:
        result = await agent.run(
            "請將以上對話的重點摘要，包括討論的標的、重要洞見與行動項目（條列式，100字以內），然後使用 save_note 工具儲存摘要。",
            deps=_make_deps(),
            message_history=history,
        )
        return f"對話已儲存。摘要：\n{result.output}"
    except Exception as e:
        print(f"[warn] save_chat failed for user {user_id}: {e}", file=sys.stderr)
        return "儲存失敗，請稍後再試。"
