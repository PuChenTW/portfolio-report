import asyncio
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from researcher.handlers.commands import (
    handle_watchlist,
    handle_alert,
    handle_holdings,
    handle_status,
)
from researcher.handlers.chat import handle_chat
from researcher.services.workflow_deps import make_deps
from researcher.workflows import premarket

_WATCHLIST_PATH = os.environ.get("WATCHLIST_CSV_PATH", "./watchlist.csv")
_ALERTS_PATH = os.environ.get("PRICE_ALERTS_PATH", "./price-alerts.yml")


async def _cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    reply = handle_watchlist(list(args), watchlist_path=_WATCHLIST_PATH)
    await update.message.reply_text(reply)  # type: ignore[union-attr]


async def _cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    reply = handle_alert(list(args), alerts_path=_ALERTS_PATH)
    await update.message.reply_text(reply)  # type: ignore[union-attr]


async def _cmd_holdings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    reply = handle_holdings(list(args))
    await update.message.reply_text(reply)  # type: ignore[union-attr]


async def _cmd_status(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(handle_status())  # type: ignore[union-attr]


async def _cmd_research(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    market = args[0].upper() if args else "US"
    deps = make_deps()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, premarket.run, market, deps)
    await update.message.reply_text(f"✅ Research triggered for {market}.")  # type: ignore[union-attr]


async def _on_text(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    try:
        reply = await handle_chat(update.message.text.strip())
    except Exception as e:
        reply = f"❌ Error: {e}"
    await update.message.reply_text(reply)


def create_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("watchlist", _cmd_watchlist))
    app.add_handler(CommandHandler("alert", _cmd_alert))
    app.add_handler(CommandHandler("holdings", _cmd_holdings))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("research", _cmd_research))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
    return app
