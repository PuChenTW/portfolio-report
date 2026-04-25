import asyncio
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from researcher.handlers.commands import handle_watchlist, handle_alert, handle_holdings, handle_status
from researcher.handlers.chat import handle_chat

_WATCHLIST_PATH = os.environ.get("WATCHLIST_CSV_PATH", "./watchlist.csv")
_ALERTS_PATH = os.environ.get("PRICE_ALERTS_PATH", "./price-alerts.yml")


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    try:
        reply = await _route(text)
    except Exception as e:
        reply = f"❌ Error: {e}"
    await update.message.reply_text(reply)


async def _route(text: str) -> str:
    if not text.startswith("/"):
        return await handle_chat(text)

    parts = text.lstrip("/").split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "watchlist":
        return handle_watchlist(args, watchlist_path=_WATCHLIST_PATH)
    if cmd == "alert":
        return handle_alert(args, alerts_path=_ALERTS_PATH)
    if cmd == "holdings":
        return handle_holdings(args)
    if cmd == "status":
        return handle_status()
    if cmd == "research":
        from researcher.workflows import premarket
        loop = asyncio.get_event_loop()
        market = args[0].upper() if args else "US"
        await loop.run_in_executor(None, premarket.run, market)
        return f"✅ Research triggered for {market}."
    return f"Unknown command: /{cmd}\nAvailable: /watchlist, /alert, /research, /status"


def create_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    app.add_handler(MessageHandler(filters.COMMAND, _on_message))
    return app
