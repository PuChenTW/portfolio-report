import asyncio
import os
from typing import Any
from telegram import BotCommand, Update
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
from researcher.handlers.chat import handle_chat, persist_session, reset_chat_session
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


async def _cmd_newchat(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else 0
    reply, history = reset_chat_session(user_id)
    if history:
        asyncio.create_task(persist_session(history))
    await update.message.reply_text(reply)  # type: ignore[union-attr]


async def _on_text(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id if update.effective_user else 0
    try:
        reply = await handle_chat(update.message.text.strip(), user_id)
    except Exception as e:
        reply = f"❌ Error: {e}"
    await update.message.reply_text(reply)


_COMMAND_REGISTRY: list[tuple[str, str, Any]] = [
    ("status", "Check agent status", _cmd_status),
    ("watchlist", "Manage watchlist: add/remove/list", _cmd_watchlist),
    ("alert", "Manage price alerts: set/show", _cmd_alert),
    ("holdings", "Update a position: update TICKER SHARES COST", _cmd_holdings),
    ("research", "Trigger pre-market research: [TW|US]", _cmd_research),
    ("newchat", "Reset the current conversation session", _cmd_newchat),
]

COMMANDS = [BotCommand(name, desc) for name, desc, _ in _COMMAND_REGISTRY]


def create_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    for name, _, handler in _COMMAND_REGISTRY:
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
    return app
