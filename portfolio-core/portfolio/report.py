from typing import NotRequired, TypedDict


class USHolding(TypedDict):
    ticker: str
    name: str
    category: str  # "ETF" | "TECH" | "GOLD" | "NUCLEAR" | "METAL"
    price: str  # pre-formatted, e.g. "$134.25"
    day_change: str  # pre-formatted, e.g. "+2.34%"
    day_change_up: bool
    gain_loss: str  # pre-formatted, e.g. "+18.5%"
    gain_loss_up: bool
    pct_of_currency: NotRequired[float]  # % of same-currency total, e.g. 12.3


class TWHolding(TypedDict):
    ticker: str
    name: str
    price: str
    day_change: str
    day_change_up: bool
    note: str  # free text, e.g. "外資買超 12億"
    pct_of_currency: NotRequired[float]


class CryptoHolding(TypedDict):
    ticker: str
    name: str
    price: str
    day_change: str
    day_change_up: bool
    quantity: str  # e.g. "0.2286 顆"
    pct_of_currency: NotRequired[float]


_GREEN = "#48bb78"
_RED = "#fc8181"

_CATEGORY_TAGS: dict[str, str] = {
    "ETF": "background:#1a365d;color:#63b3ed",
    "TECH": "background:#2d3748;color:#90cdf4",
    "GOLD": "background:#2d2000;color:#f6e05e",
    "NUCLEAR": "background:#1a365d;color:#63b3ed",
    "METAL": "background:#2d3748;color:#90cdf4",
}


def _border(is_last: bool) -> str:
    return "" if is_last else "border-bottom:1px solid #1a2030;"


def _render_us_row(h: USHolding, is_last: bool) -> str:
    border = _border(is_last)
    tag_style = _CATEGORY_TAGS.get(h["category"], "background:#2d3748;color:#90cdf4")
    day_color = _GREEN if h["day_change_up"] else _RED
    gl_color = _GREEN if h["gain_loss_up"] else _RED
    return (
        f"<tr>"
        f'<td style="padding:10px 0;{border}">'
        f'<div style="font-weight:700;color:#fff;font-size:13px;">{h["ticker"]} '
        f'<span style="display:inline-block;font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;margin-left:6px;{tag_style}">{h["category"]}</span></div>'
        f'<div style="font-size:11px;color:#4a5568;margin-top:2px;">{h["name"]}</div>'
        f"</td>"
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:#e2e8f0;">{h["price"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:{day_color};">{h["day_change"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:{gl_color};">{h["gain_loss"]}</td>'
        f"</tr>"
    )


def _render_tw_row(h: TWHolding, is_last: bool) -> str:
    border = _border(is_last)
    day_color = _GREEN if h["day_change_up"] else _RED
    return (
        f"<tr>"
        f'<td style="padding:10px 0;{border}">'
        f'<div style="font-weight:700;color:#fff;font-size:13px;">{h["ticker"]}</div>'
        f'<div style="font-size:11px;color:#4a5568;margin-top:2px;">{h["name"]}</div>'
        f"</td>"
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:#e2e8f0;">{h["price"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:{day_color};">{h["day_change"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:#a0aec0;">{h["note"]}</td>'
        f"</tr>"
    )


def _render_crypto_row(h: CryptoHolding, is_last: bool) -> str:
    border = _border(is_last)
    day_color = _GREEN if h["day_change_up"] else _RED
    return (
        f"<tr>"
        f'<td style="padding:10px 0;{border}">'
        f'<div style="font-weight:700;color:#fff;font-size:13px;">{h["ticker"]}</div>'
        f'<div style="font-size:11px;color:#4a5568;margin-top:2px;">{h["name"]}</div>'
        f"</td>"
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:#e2e8f0;">{h["price"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:{day_color};">{h["day_change"]}</td>'
        f'<td align="right" style="padding:10px 0;{border}font-size:13px;color:#e2e8f0;">{h["quantity"]}</td>'
        f"</tr>"
    )


def _render_macro_rows(items: list[str]) -> str:
    rows = []
    for text in items:
        rows.append(
            "<tr>"
            '<td width="14" valign="top" style="padding-top:7px;padding-right:12px;">'
            '<div style="width:6px;height:6px;border-radius:50%;background:#3182ce;"></div>'
            "</td>"
            f'<td style="font-size:14px;color:#cbd5e0;line-height:1.6;padding-bottom:10px;">{text}</td>'
            "</tr>"
        )
    return "".join(rows)


def _render_news_links(urls: list[str]) -> str:
    if not urls:
        return ""
    rows = []
    for i, url in enumerate(urls):
        rows.append(
            "<tr>"
            f'<td width="24" valign="top" style="padding-top:5px;padding-right:10px;color:#3182ce;font-size:12px;font-weight:700;">{i + 1}.</td>'
            f'<td style="font-size:13px;padding-bottom:8px;"><a href="{url}" style="color:#63b3ed;text-decoration:none;word-break:break-all;">{url}</a></td>'
            "</tr>"
        )
    return "".join(rows)


def _render_tip_rows(items: list[str]) -> str:
    rows = []
    for i, text in enumerate(items):
        is_last = i == len(items) - 1
        pb = "" if is_last else "padding-bottom:14px;"
        n = i + 1
        rows.append(
            "<tr>"
            f'<td width="30" valign="top" style="padding-right:12px;{pb}">'
            f'<div style="width:22px;height:22px;border-radius:50%;background:#2b4c7e;color:#90cdf4;font-size:11px;font-weight:700;text-align:center;line-height:22px;">{n}</div>'
            "</td>"
            f'<td style="font-size:14px;color:#cbd5e0;line-height:1.6;{pb}">{text}</td>'
            "</tr>"
        )
    return "".join(rows)


DAILY_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',Arial,sans-serif;color:#e2e8f0;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;">

  <div style="background:linear-gradient(135deg,#1a1f2e 0%,#0d1321 100%);border:1px solid #2d3748;border-radius:16px 16px 0 0;padding:32px 32px 24px;border-bottom:2px solid #3182ce;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
      <div>
        <div style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.3px;">📊 每日投資摘要</div>
        <div style="font-size:13px;color:#718096;margin-top:4px;">[TODAY_DATE]</div>
      </div>
      <div style="background:#2b6cb0;color:#bee3f8;font-size:11px;font-weight:600;padding:4px 10px;border-radius:20px;letter-spacing:0.5px;">AUTO REPORT</div>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td width="33%" style="padding-right:6px;">
          <div style="background:rgba(255,255,255,0.04);border:1px solid #2d3748;border-radius:10px;padding:12px 14px;">
            <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">🇹🇼 台股</div>
            <div style="font-size:17px;font-weight:700;color:#fff;line-height:1.2;">[TW_TOTAL]</div>
            <div style="font-size:12px;margin-top:8px;font-weight:600;color:[TW_CHANGE_COLOR];">[TW_CHANGE]</div>
          </div>
        </td>
        <td width="33%" style="padding:0 3px;">
          <div style="background:rgba(255,255,255,0.04);border:1px solid #2d3748;border-radius:10px;padding:12px 14px;">
            <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">🇺🇸 美股</div>
            <div style="font-size:17px;font-weight:700;color:#fff;line-height:1.2;">[US_TOTAL]</div>
            <div style="font-size:12px;margin-top:8px;font-weight:600;color:[US_CHANGE_COLOR];">[US_CHANGE]</div>
          </div>
        </td>
        <td width="33%" style="padding-left:6px;">
          <div style="background:rgba(255,255,255,0.04);border:1px solid #2d3748;border-radius:10px;padding:12px 14px;">
            <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">₿ 加密貨幣</div>
            <div style="font-size:17px;font-weight:700;color:#fff;line-height:1.2;">[CRYPTO_TOTAL]</div>
            <div style="font-size:12px;margin-top:8px;font-weight:600;color:[CRYPTO_CHANGE_COLOR];">[CRYPTO_CHANGE]</div>
          </div>
        </td>
      </tr>
    </table>
  </div>

  <div style="background:#141820;border:1px solid #2d3748;border-top:none;border-radius:0 0 16px 16px;overflow:hidden;">

    <div style="padding:24px 32px;border-bottom:1px solid #1e2535;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span style="font-size:18px;">🌍</span>
        <span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">總體經濟</span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">[MACRO_ROWS]</table>
    </div>

    <div style="padding:24px 32px;border-bottom:1px solid #1e2535;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span style="font-size:18px;">🇺🇸</span>
        <span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">美股市況</span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;">
        <colgroup><col width="45%"><col width="18%"><col width="15%"><col width="22%"></colgroup>
        <thead><tr>
          <th align="left" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">標的</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">最新價</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">日漲跌</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">持倉損益</th>
        </tr></thead>
        <tbody>[US_TABLE_ROWS]</tbody>
      </table>
      <div style="background:#1a2035;border-left:3px solid #3182ce;border-radius:0 8px 8px 0;padding:12px 16px;margin-top:16px;">
        <div style="font-size:13px;font-weight:700;color:#fff;margin-bottom:4px;">⚡ 重點事件</div>
        <div style="font-size:13px;color:#a0aec0;line-height:1.5;">[US_EVENT]</div>
      </div>
    </div>

    <div style="padding:24px 32px;border-bottom:1px solid #1e2535;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span style="font-size:18px;">🇹🇼</span>
        <span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">台股市況</span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;">
        <colgroup><col width="40%"><col width="20%"><col width="15%"><col width="25%"></colgroup>
        <thead><tr>
          <th align="left" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">標的</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">最新價</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">日漲跌</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">備註</th>
        </tr></thead>
        <tbody>[TW_TABLE_ROWS]</tbody>
      </table>
    </div>

    <div style="padding:24px 32px;border-bottom:1px solid #1e2535;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span style="font-size:18px;">₿</span>
        <span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">加密貨幣</span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;">
        <colgroup><col width="45%"><col width="18%"><col width="15%"><col width="22%"></colgroup>
        <thead><tr>
          <th align="left" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">幣種</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">最新價</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">日漲跌</th>
          <th align="right" style="font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:0.8px;padding-bottom:10px;border-bottom:1px solid #2d3748;font-weight:600;">持有數量</th>
        </tr></thead>
        <tbody>[CRYPTO_TABLE_ROWS]</tbody>
      </table>
    </div>

    <div style="padding:24px 32px;border-bottom:1px solid #1e2535;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span style="font-size:18px;">💡</span>
        <span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">今日重點提示</span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">[TIP_ROWS]</table>
    </div>

    [NEWS_LINKS_SECTION]

  </div>

  <div style="margin-top:20px;text-align:center;color:#4a5568;font-size:11px;line-height:1.8;">
    <p>資料來源：Yahoo Finance 即時行情 + 網路財經新聞</p>
    <p style="margin-top:4px;color:#2d3748;">⚠️ 本報告僅供參考，不構成投資建議</p>
  </div>

</div>
</body>
</html>"""


_MDV2_ESCAPE = str.maketrans(
    {
        "_": r"\_",
        "*": r"\*",
        "[": r"\[",
        "]": r"\]",
        "(": r"\(",
        ")": r"\)",
        "~": r"\~",
        "`": r"\`",
        ">": r"\>",
        "#": r"\#",
        "+": r"\+",
        "-": r"\-",
        "=": r"\=",
        "|": r"\|",
        "{": r"\{",
        "}": r"\}",
        ".": r"\.",
        "!": r"\!",
    }
)


def _esc(s: str) -> str:
    return s.translate(_MDV2_ESCAPE)


def _arrow(is_up: bool) -> str:
    return "🟢" if is_up else "🔴"


def format_telegram_messages(
    today_date: str,
    tw_total: str,
    tw_change: str,
    tw_change_up: bool,
    us_total: str,
    us_change: str,
    us_change_up: bool,
    crypto_total: str,
    crypto_change: str,
    crypto_change_up: bool,
    us_holdings: list[USHolding],
    us_event: str,
    tw_holdings: list[TWHolding],
    crypto_holdings: list[CryptoHolding],
    macro_rows: list[str],
    tip_rows: list[str],
    news_links: list[str] = [],
) -> list[str]:
    """Format daily report as 2 Telegram MarkdownV2 messages for quick mobile glance."""
    # Message 1: Snapshot — totals + macro
    msg1_lines = [
        f"📊 *每日投資摘要*  {_esc(today_date)}",
        "",
        f"🇹🇼 台股  {_esc(tw_total)}  {_arrow(tw_change_up)} {_esc(tw_change)}",
        f"🇺🇸 美股  {_esc(us_total)}  {_arrow(us_change_up)} {_esc(us_change)}",
        f"₿  加密貨幣  {_esc(crypto_total)}  {_arrow(crypto_change_up)} {_esc(crypto_change)}",
        "",
        "🌍 *總體經濟*",
    ]
    for row in macro_rows:
        msg1_lines.append(f"• {_esc(row)}")

    # Message 2: Insight — US event, TW notes (non-empty only), action items
    msg2_lines = [
        "⚡ *美股重點*",
        _esc(us_event),
    ]

    noted = [h for h in tw_holdings if h.get("note") and h["note"] != "—"]
    if noted:
        msg2_lines.append("")
        msg2_lines.append("🇹🇼 *台股個股*")
        for h in noted:
            msg2_lines.append(f"• {_esc(h['name'])} {_esc(h['ticker'])}：{_esc(h['note'])}")

    msg2_lines.append("")
    msg2_lines.append("💡 *今日行動*")
    for i, tip in enumerate(tip_rows, 1):
        msg2_lines.append(f"{i}\\. {_esc(tip)}")

    if news_links:
        msg2_lines.append("")
        msg2_lines.append("📰 *新聞來源*")
        msg2_lines.append("  ".join(f"[{i + 1}]({url})" for i, url in enumerate(news_links)))

    msg2_lines.append("")
    msg2_lines.append("_⚠️ 僅供參考，不構成投資建議_")

    return ["\n".join(msg1_lines), "\n".join(msg2_lines)]


def generate_daily_report_html(
    today_date: str,
    tw_total: str,
    tw_change: str,
    tw_change_up: bool,
    us_total: str,
    us_change: str,
    us_change_up: bool,
    crypto_total: str,
    crypto_change: str,
    crypto_change_up: bool,
    us_holdings: list[USHolding],
    us_event: str,
    tw_holdings: list[TWHolding],
    crypto_holdings: list[CryptoHolding],
    macro_rows: list[str],
    tip_rows: list[str],
    news_links: list[str] = [],
) -> str:
    """Generate the daily investment summary HTML email from pre-aggregated data."""
    us_rows = "".join(_render_us_row(h, i == len(us_holdings) - 1) for i, h in enumerate(us_holdings))
    tw_rows = "".join(_render_tw_row(h, i == len(tw_holdings) - 1) for i, h in enumerate(tw_holdings))
    crypto_rows = "".join(_render_crypto_row(h, i == len(crypto_holdings) - 1) for i, h in enumerate(crypto_holdings))

    rendered_links = _render_news_links(news_links)
    news_links_section = (
        '<div style="padding:24px 32px;">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">'
        '<span style="font-size:18px;">📰</span>'
        '<span style="font-size:14px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">重要新聞來源</span>'
        "</div>"
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">{rendered_links}</table>'
        "</div>"
        if rendered_links
        else ""
    )

    return (
        DAILY_REPORT_TEMPLATE.replace("[TODAY_DATE]", today_date)
        .replace("[TW_TOTAL]", tw_total)
        .replace("[TW_CHANGE_COLOR]", _GREEN if tw_change_up else _RED)
        .replace("[TW_CHANGE]", tw_change)
        .replace("[US_TOTAL]", us_total)
        .replace("[US_CHANGE_COLOR]", _GREEN if us_change_up else _RED)
        .replace("[US_CHANGE]", us_change)
        .replace("[CRYPTO_TOTAL]", crypto_total)
        .replace("[CRYPTO_CHANGE_COLOR]", _GREEN if crypto_change_up else _RED)
        .replace("[CRYPTO_CHANGE]", crypto_change)
        .replace("[MACRO_ROWS]", _render_macro_rows(macro_rows))
        .replace("[US_TABLE_ROWS]", us_rows)
        .replace("[US_EVENT]", us_event)
        .replace("[TW_TABLE_ROWS]", tw_rows)
        .replace("[CRYPTO_TABLE_ROWS]", crypto_rows)
        .replace("[TIP_ROWS]", _render_tip_rows(tip_rows))
        .replace("[NEWS_LINKS_SECTION]", news_links_section)
    )
