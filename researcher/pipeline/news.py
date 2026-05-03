import json
from datetime import datetime
from typing import cast

from pydantic import BaseModel

from portfolio.report import USHolding, TWHolding, CryptoHolding
from researcher.pipeline.data import TZ_TAIPEI, _fmt_today
from researcher.services.agent_runner import make_search_agent, run_agent_sync

_NEWS_DEFAULTS = {
    "macro_rows": ["今日總體經濟數據暫無法取得。"],
    "us_event": "今日美股重點事件暫無法取得。",
    "tw_notes": {},
    "tip_rows": ["請至 Gmail 或財經網站查看今日市場動態。"],
}

_NEWS_PROMPT_TEMPLATE = """\
你是一位專業的資產管理人，負責每日為客戶撰寫投資組合晨報。今天是 {today}。

客戶目前持倉如下（包含配置比例）：
{portfolio_json}

欄位說明：
- pct_of_currency（幣別內佔比）：該部位佔同幣別總資產的百分比
- pct_global（全域 USD 佔比）：該部位換算為美元後，佔全部資產的百分比；若無匯率資料則為 null
- gain_loss：持倉損益（正為獲利，負為虧損）

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

搜尋完畢後，以資產管理人的角度，根據搜尋結果、持倉損益與配置比例，填寫以下欄位：
- macro_rows：3-5 條今日總體經濟與市場環境重點，每條一句話，點出對持倉的潛在影響
- us_event：今日美股最重要的催化劑或風險事件，1-2 句，具體說明對持倉的意義
- tw_notes：每個台股標的今日動態，包含外資動向或重要消息，key 為 ticker
- tip_rows：4-6 條具體操作建議，需涵蓋以下面向（可合併成一條）：
  * 再平衡建議：若某類別或幣別配置比例明顯偏高或偏低，說明是否需調整
  * 集中度警示：若單一部位 pct_global 超過 15%，點出集中風險
  * 結合新聞的個股操作建議：依今日消息與持倉比重，說明持有、加碼或減碼的理由

語言：台灣繁體中文，禁止簡體中文或中國用語。"""


class _NewsSummary(BaseModel):
    macro_rows: list[str]
    us_event: str
    tw_notes: dict[str, str]
    tip_rows: list[str]


def _build_portfolio_context(
    us_holdings: list[USHolding],
    tw_holdings: list[TWHolding],
    crypto_holdings: list[CryptoHolding],
    summary: dict,
) -> dict:
    """Build three-level portfolio context for the LLM prompt."""
    positions_by_ticker = {p["ticker"]: p for p in summary.get("positions", [])}
    by_currency = summary.get("by_currency", {})

    categories = []
    for cur, bc in by_currency.items():
        for cat, v in bc.get("by_category", {}).items():
            categories.append(
                {
                    "name": cat,
                    "currency": cur,
                    "pct_of_currency": v.get("pct_of_currency_total", None),
                    "pct_global": None,  # category-level global pct not computed; position-level used
                }
            )

    def _pos_entry(ticker: str, extra: dict) -> dict:
        p = positions_by_ticker.get(ticker, {})
        return {
            "ticker": ticker,
            "pct_of_currency": p.get("pct_of_currency_total"),
            "pct_global": p.get("pct_of_global_usd"),
            **extra,
        }

    return {
        "portfolio_overview": {
            "global_total_usd": summary.get("global_total_usd"),
            "currency_allocation": summary.get("currency_pct"),
            "fx_rate": summary.get("fx_rate"),
        },
        "categories": categories,
        "positions": (
            [_pos_entry(h["ticker"], {"gain_loss": h["gain_loss"]}) for h in us_holdings]
            + [
                _pos_entry(
                    h["ticker"],
                    {"gain_loss": positions_by_ticker.get(h["ticker"], {}).get("gain_loss_pct", None)},
                )
                for h in tw_holdings
            ]
            + [
                _pos_entry(
                    h["ticker"] + "-USD" if h["ticker"] + "-USD" in positions_by_ticker else h["ticker"],
                    {"quantity": h["quantity"]},
                )
                for h in crypto_holdings
            ]
        ),
    }


def search_news(
    us_holdings: list[USHolding],
    tw_holdings: list[TWHolding],
    crypto_holdings: list[CryptoHolding],
    summary: dict | None = None,
) -> dict:
    now = datetime.now(TZ_TAIPEI)
    today_str = _fmt_today()
    date_str = now.strftime("%Y-%m-%d")

    if summary is not None:
        portfolio_summary = _build_portfolio_context(us_holdings, tw_holdings, crypto_holdings, summary)
    else:
        portfolio_summary = {
            "美股": [{"ticker": h["ticker"], "gain_loss": h["gain_loss"]} for h in us_holdings],
            "台股": [{"ticker": h["ticker"]} for h in tw_holdings],
            "加密貨幣": [{"ticker": h["ticker"], "quantity": h["quantity"]} for h in crypto_holdings],
        }

    prompt = _NEWS_PROMPT_TEMPLATE.format(
        today=today_str,
        date=date_str,
        portfolio_json=json.dumps(portfolio_summary, ensure_ascii=False),
    )

    agent = make_search_agent(
        _NewsSummary,
        system_prompt=f"今天日期是 {date_str}。所有搜尋查詢都必須包含這個日期，確保只取得今日最新資訊，不可搜尋過去日期的內容。",
    )
    output = run_agent_sync(agent, prompt, max_attempts=5, label="news")
    if output is None:
        return _NEWS_DEFAULTS
    return cast(_NewsSummary, output).model_dump()
