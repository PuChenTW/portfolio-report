import json
import os
import sys
from datetime import datetime
from typing import cast

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.common_tools.tavily import tavily_search_tool

from portfolio.report import USHolding, TWHolding, CryptoHolding
from pipeline.data import TZ_TAIPEI, _fmt_today

_NEWS_DEFAULTS = {
    "macro_rows": ["今日總體經濟數據暫無法取得。"],
    "us_event": "今日美股重點事件暫無法取得。",
    "tw_notes": {},
    "tip_rows": ["請至 Gmail 或財經網站查看今日市場動態。"],
}

_NEWS_PROMPT_TEMPLATE = """\
你是一位專業的資產管理人，負責每日為客戶撰寫投資組合晨報。今天是 {today}。

客戶目前持倉如下：
{portfolio_json}

請依序搜尋以下主題，務必每個標的都確實查詢，不可略過：

【總體經濟】
- "Fed interest rate inflation CPI {date}"
- "US economy market outlook {date}"

【美股大盤】
- "S&P 500 Nasdaq Dow Jones performance {date}"

【美股個股】（每個標的各搜一次）
- 每個美股 ticker + "stock news earnings analyst {date}"

【台股】
- "台股 加權指數 外資買賣超 今日 {date}"
- 每個台股 ticker + "股價 外資 法人 {date}"

【加密貨幣】
- 每個幣種名稱 + "price analysis {date}"

搜尋完畢後，以資產管理人的角度，根據搜尋結果與持倉損益，填寫以下欄位：
- macro_rows：3-5 條今日總體經濟與市場環境重點，每條一句話，點出對持倉的潛在影響
- us_event：今日美股最重要的催化劑或風險事件，1-2 句，具體說明對持倉的意義
- tw_notes：每個台股標的今日動態，包含外資動向或重要消息，key 為 ticker
- tip_rows：4-6 條具體操作建議，結合當前損益與市場訊號，說明持有、加碼或減碼的理由

語言：台灣繁體中文，禁止簡體中文或中國用語。"""


class _NewsSummary(BaseModel):
    macro_rows: list[str]
    us_event: str
    tw_notes: dict[str, str]
    tip_rows: list[str]


def _make_news_agent(date_str: str) -> Agent[None, _NewsSummary]:
    return Agent(
        "google-gla:gemini-3-flash-preview",
        tools=[tavily_search_tool(os.environ["TAVILY_API_KEY"])],
        output_type=_NewsSummary,
        system_prompt=f"今天日期是 {date_str}。所有搜尋查詢都必須包含這個日期，確保只取得今日最新資訊，不可搜尋過去日期的內容。",
    )


def run_claude_news(
    us_holdings: list[USHolding],
    tw_holdings: list[TWHolding],
    crypto_holdings: list[CryptoHolding],
    totals: dict,
) -> dict:
    now = datetime.now(TZ_TAIPEI)
    today_str = _fmt_today()
    date_str = now.strftime("%Y-%m-%d")

    portfolio_summary = {
        "美股": [
            {"ticker": h["ticker"], "gain_loss": h["gain_loss"]} for h in us_holdings
        ],
        "台股": [{"ticker": h["ticker"]} for h in tw_holdings],
        "加密貨幣": [
            {"ticker": h["ticker"], "quantity": h["quantity"]} for h in crypto_holdings
        ],
    }

    prompt = _NEWS_PROMPT_TEMPLATE.format(
        today=today_str,
        date=date_str,
        portfolio_json=json.dumps(portfolio_summary, ensure_ascii=False),
    )

    try:
        result = _make_news_agent(date_str).run_sync(prompt)
        for msg in result.all_messages():
            for part in msg.parts:
                kind = getattr(part, "part_kind", None)
                if kind == "tool-call":
                    print(f"[search] {getattr(part, 'tool_name', '?')}: {getattr(part, 'args', '')}", file=sys.stderr)
                elif kind == "tool-return":
                    preview = str(getattr(part, "content", ""))[:200]
                    print(f"[result] {getattr(part, 'tool_name', '?')}: {preview}", file=sys.stderr)
        return cast(_NewsSummary, result.output).model_dump()
    except Exception as e:
        print(f"[warn] PydanticAI news agent failed: {e}", file=sys.stderr)
        return _NEWS_DEFAULTS
