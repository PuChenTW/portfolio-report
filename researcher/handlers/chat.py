import asyncio
import os
import sys
from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

from portfolio.portfolio import TZ_TAIPEI
from researcher.memory.io import last_n_entries

_MEMORY_PATH = os.environ.get("RESEARCHER_MEMORY_PATH", "./memory")


class _ChatIntent(BaseModel):
    kind: str  # "command" | "research" | "other"
    command: str | None  # e.g. "/watchlist add AAPL" if kind == "command"
    answer: str | None  # direct answer if kind == "research" or "other"


async def handle_chat(message: str) -> str:
    """Parse a free-form message and return a reply string."""
    now = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")
    recent_log = last_n_entries(f"{_MEMORY_PATH}/RESEARCH-LOG.md", 2)

    intent_prompt = (
        f"今天是 {date_str}。用戶傳來：\n「{message}」\n\n"
        f"近期研究紀錄：\n{recent_log}\n\n"
        f"判斷用戶意圖：\n"
        f"1. 若意圖是操作指令（新增/移除持倉、設定警示）→ kind='command'，command 填對應指令字串\n"
        f"   支援的指令：/watchlist add/remove/list, /alert set/show, /research\n"
        f"2. 若是研究問題 → kind='research'，用 Tavily 搜尋後 answer 填簡短回答（3-5 句）\n"
        f"3. 其他 → kind='other'，answer 填禮貌回覆\n"
        f"語言：台灣繁體中文。"
    )

    agent = Agent(
        "google-gla:gemini-3-flash-preview",
        tools=[tavily_search_tool(os.environ["TAVILY_API_KEY"])],
        output_type=_ChatIntent,
        system_prompt=f"date={date_str}",
    )

    intent: _ChatIntent | None = None
    for attempt in range(3):
        try:
            result = await agent.run(intent_prompt)
            intent = result.output
            break
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2**attempt)
            else:
                print(f"[warn] chat intent failed: {e}", file=sys.stderr)
                return "抱歉，目前無法處理您的訊息，請稍後再試。"

    if intent is None:
        return "抱歉，目前無法處理您的訊息，請稍後再試。"
    if intent.kind == "command" and intent.command:
        return f"已識別為指令：`{intent.command}`\n請直接輸入此指令執行。"
    return intent.answer or "抱歉，我無法理解您的訊息。"
