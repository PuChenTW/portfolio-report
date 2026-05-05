from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from researcher.handlers.commands import (
    handle_add_holding,
    handle_alert,
    handle_remove_holding,
    handle_update_holding,
    handle_watchlist,
)
from researcher.pipeline.data import fetch_portfolio
from portfolio.watchlist import load_watchlist
from researcher.config import settings

# Watchlist states (0–4)
WATCHLIST_MENU = 0
WATCHLIST_ADD_TICKER = 1
WATCHLIST_ADD_NAME = 2
WATCHLIST_ADD_NOTE = 3
WATCHLIST_REMOVE_PICK = 4

# Alert states (10–12)
ALERT_PICK_TICKER = 10
ALERT_PICK_DIRECTION = 11
ALERT_ENTER_VALUE = 12

# Update states (20–35)
UPDATE_MENU = 20
UPDATE_PICK_TICKER = 21
UPDATE_ENTER_SHARES = 22
UPDATE_ENTER_COST = 23
UPDATE_CONFIRM = 24
UPDATE_ADD_TICKER = 25
UPDATE_ADD_NAME = 26
UPDATE_ADD_SHARES = 27
UPDATE_ADD_COST = 28
UPDATE_ADD_CURRENCY = 29
UPDATE_ADD_CATEGORY = 30
UPDATE_REMOVE_PICK = 31
UPDATE_REMOVE_CONFIRM = 32
UPDATE_CASH_PICK = 33
UPDATE_CASH_AMOUNT = 34


def _make_ticker_keyboard(
    tickers: list[str],
    prefix: str,
    extra_buttons: list[InlineKeyboardButton] | None = None,
) -> InlineKeyboardMarkup:
    pairs = [tickers[i : i + 2] for i in range(0, len(tickers), 2)]
    rows = [[InlineKeyboardButton(t, callback_data=f"{prefix}:{t}") for t in pair] for pair in pairs]
    if extra_buttons:
        rows.append(extra_buttons)
    return InlineKeyboardMarkup(rows)


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


async def _handle_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer("Session timed out.")
    elif update.message:
        await update.message.reply_text("Session timed out. Send the command again to restart.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Watchlist flow
# ---------------------------------------------------------------------------


async def watchlist_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Add", callback_data="wl:add"),
                InlineKeyboardButton("➖ Remove", callback_data="wl:remove"),
                InlineKeyboardButton("📋 List", callback_data="wl:list"),
            ]
        ]
    )
    await update.message.reply_text("What would you like to do?", reply_markup=keyboard)  # type: ignore[union-attr]
    return WATCHLIST_MENU


async def watchlist_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    action = query.data.split(":")[1]  # type: ignore[union-attr]

    if action == "list":
        reply = handle_watchlist(["list"])
        await query.edit_message_text(reply)  # type: ignore[union-attr]
        return ConversationHandler.END

    if action == "add":
        await query.edit_message_text("Enter ticker symbol (e.g. NVDA):")  # type: ignore[union-attr]
        return WATCHLIST_ADD_TICKER

    # action == "remove"
    entries = load_watchlist(settings.watchlist_csv_path)
    if not entries:
        await query.edit_message_text("Watchlist is empty.")  # type: ignore[union-attr]
        return ConversationHandler.END
    tickers = [e.ticker for e in entries]
    keyboard = _make_ticker_keyboard(
        tickers,
        "wl:rm",
        [InlineKeyboardButton("❌ Cancel", callback_data="wl:cancel")],
    )
    await query.edit_message_text("Select a ticker to remove:", reply_markup=keyboard)  # type: ignore[union-attr]
    return WATCHLIST_REMOVE_PICK


async def watchlist_add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    context.user_data["wl_ticker"] = update.message.text.strip().upper()  # type: ignore[union-attr]
    await update.message.reply_text("Enter company name (or /skip to use the ticker):")  # type: ignore[union-attr]
    return WATCHLIST_ADD_NAME


async def watchlist_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    text = update.message.text.strip()  # type: ignore[union-attr]
    context.user_data["wl_name"] = context.user_data["wl_ticker"] if text == "/skip" else text
    await update.message.reply_text("Enter a note (or /skip to leave blank):")  # type: ignore[union-attr]
    return WATCHLIST_ADD_NOTE


async def watchlist_add_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    text = update.message.text.strip()  # type: ignore[union-attr]
    note = "" if text == "/skip" else text
    ticker = context.user_data.pop("wl_ticker", "")
    name = context.user_data.pop("wl_name", ticker)
    context.user_data.pop("wl_note", None)
    reply = handle_watchlist(["add", ticker, name, note])
    await update.message.reply_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


async def watchlist_remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "wl:cancel":
        await query.edit_message_text("Operation cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    ticker = data.split(":", 2)[2]  # wl:rm:TICKER
    reply = handle_watchlist(["remove", ticker])
    await query.edit_message_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


def build_watchlist_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("watchlist", watchlist_entry)],
        states={
            WATCHLIST_MENU: [CallbackQueryHandler(watchlist_menu_action, pattern=r"^wl:(add|remove|list)$")],
            WATCHLIST_ADD_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, watchlist_add_ticker)],
            WATCHLIST_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, watchlist_add_name)],
            WATCHLIST_ADD_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, watchlist_add_note)],
            WATCHLIST_REMOVE_PICK: [CallbackQueryHandler(watchlist_remove_pick, pattern=r"^wl:(rm:.+|cancel)$")],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _handle_timeout),
                CallbackQueryHandler(_handle_timeout),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        conversation_timeout=120,
        allow_reentry=True,
        per_message=False,
    )


# ---------------------------------------------------------------------------
# Alert flow
# ---------------------------------------------------------------------------


async def alert_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = fetch_portfolio()
    tickers = [p["ticker"] for p in data["summary"]["positions"] if not p.get("is_cash")]
    keyboard = _make_ticker_keyboard(
        tickers,
        "al:ticker",
        [InlineKeyboardButton("❌ Cancel", callback_data="al:cancel")],
    )
    await update.message.reply_text("Select a ticker to set an alert:", reply_markup=keyboard)  # type: ignore[union-attr]
    return ALERT_PICK_TICKER


async def alert_pick_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "al:cancel":
        await query.edit_message_text("Alert setup cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    ticker = data.split(":", 2)[2]  # al:ticker:AAPL
    assert context.user_data is not None
    context.user_data["al_ticker"] = ticker
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📈 Set Above", callback_data="al:dir:above"),
                InlineKeyboardButton("📉 Set Below", callback_data="al:dir:below"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="al:cancel")],
        ]
    )
    await query.edit_message_text(f"Set alert for <b>{ticker}</b>:", reply_markup=keyboard, parse_mode="HTML")  # type: ignore[union-attr]
    return ALERT_PICK_DIRECTION


async def alert_pick_direction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "al:cancel":
        assert context.user_data is not None
        context.user_data.pop("al_ticker", None)
        await query.edit_message_text("Alert setup cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    direction = data.split(":", 2)[2]  # al:dir:above
    assert context.user_data is not None
    context.user_data["al_direction"] = direction
    ticker = context.user_data.get("al_ticker", "")
    await query.edit_message_text(f"Enter the price threshold for {ticker} ({direction}):")  # type: ignore[union-attr]
    return ALERT_ENTER_VALUE


async def alert_enter_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return ALERT_ENTER_VALUE

    assert context.user_data is not None
    ticker = context.user_data.pop("al_ticker", "")
    direction = context.user_data.pop("al_direction", "above")
    reply = handle_alert(["set", ticker, f"{direction}={text}"])
    await update.message.reply_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


def build_alert_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("alert", alert_entry)],
        states={
            ALERT_PICK_TICKER: [CallbackQueryHandler(alert_pick_ticker, pattern=r"^al:(ticker:.+|cancel)$")],
            ALERT_PICK_DIRECTION: [CallbackQueryHandler(alert_pick_direction, pattern=r"^al:(dir:.+|cancel)$")],
            ALERT_ENTER_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, alert_enter_value)],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _handle_timeout),
                CallbackQueryHandler(_handle_timeout),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        conversation_timeout=120,
        allow_reentry=True,
        per_message=False,
    )


# ---------------------------------------------------------------------------
# Update flow
# ---------------------------------------------------------------------------


_CURRENCIES = ["TWD", "USD"]
_CATEGORIES = ["台股", "台灣ETF", "美股", "美國ETF", "加密貨幣"]


async def update_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Edit", callback_data="upd:menu:edit"),
                InlineKeyboardButton("➕ Add", callback_data="upd:menu:add"),
                InlineKeyboardButton("🗑 Remove", callback_data="upd:menu:remove"),
            ],
            [InlineKeyboardButton("💰 Cash", callback_data="upd:menu:cash")],
            [InlineKeyboardButton("❌ Cancel", callback_data="upd:menu:cancel")],
        ]
    )
    await update.message.reply_text("Portfolio position — what would you like to do?", reply_markup=keyboard)  # type: ignore[union-attr]
    return UPDATE_MENU


async def update_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    action = query.data.split(":", 2)[2]  # type: ignore[union-attr]

    if action == "cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    if action == "add":
        await query.edit_message_text("Enter ticker symbol (e.g. NVDA or BTC-USD):")  # type: ignore[union-attr]
        return UPDATE_ADD_TICKER

    if action == "cash":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🇹🇼 TWD (新台幣)", callback_data="upd:cash:CASH_TWD"),
                    InlineKeyboardButton("🇺🇸 USD (美元)", callback_data="upd:cash:CASH_USD"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel")],
            ]
        )
        await query.edit_message_text("Select cash currency to update:", reply_markup=keyboard)  # type: ignore[union-attr]
        return UPDATE_CASH_PICK

    # edit or remove — need existing tickers
    data = fetch_portfolio()
    tickers = [p["ticker"] for p in data["summary"]["positions"] if not p.get("is_cash")]
    if not tickers:
        await query.edit_message_text("No positions in portfolio.")  # type: ignore[union-attr]
        return ConversationHandler.END

    assert context.user_data is not None
    context.user_data["upd_action"] = action

    if action == "edit":
        keyboard = _make_ticker_keyboard(
            tickers,
            "upd:ticker",
            [InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel")],
        )
        await query.edit_message_text("Select a position to edit:", reply_markup=keyboard)  # type: ignore[union-attr]
        return UPDATE_PICK_TICKER

    # remove
    keyboard = _make_ticker_keyboard(
        tickers,
        "upd:rm",
        [InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel")],
    )
    await query.edit_message_text("Select a position to remove:", reply_markup=keyboard)  # type: ignore[union-attr]
    return UPDATE_REMOVE_PICK


# --- Edit sub-flow ---


async def update_pick_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "upd:cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    ticker = data.split(":", 2)[2]  # upd:ticker:AAPL
    assert context.user_data is not None
    context.user_data["upd_ticker"] = ticker
    await query.edit_message_text(f"Enter new share count for <b>{ticker}</b>:", parse_mode="HTML")  # type: ignore[union-attr]
    return UPDATE_ENTER_SHARES


async def update_enter_shares(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return UPDATE_ENTER_SHARES

    assert context.user_data is not None
    ticker = context.user_data.get("upd_ticker", "")
    context.user_data["upd_shares"] = text
    await update.message.reply_text(f"Enter new cost price for <b>{ticker}</b>:", parse_mode="HTML")  # type: ignore[union-attr]
    return UPDATE_ENTER_COST


async def update_enter_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return UPDATE_ENTER_COST

    assert context.user_data is not None
    ticker = context.user_data.get("upd_ticker", "")
    shares = context.user_data.get("upd_shares", "")
    context.user_data["upd_cost"] = text
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="upd:confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel"),
            ]
        ]
    )
    await update.message.reply_text(  # type: ignore[union-attr]
        f"Update <b>{ticker}</b>: {shares} shares @ {text}. Confirm?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return UPDATE_CONFIRM


async def update_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    assert context.user_data is not None
    ticker = context.user_data.pop("upd_ticker", "")
    shares = context.user_data.pop("upd_shares", "")
    cost = context.user_data.pop("upd_cost", "")
    context.user_data.pop("upd_action", None)

    if data == "upd:cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    reply = handle_update_holding([ticker, shares, cost])
    await query.edit_message_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


# --- Add sub-flow ---


async def update_add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    context.user_data["add_ticker"] = update.message.text.strip().upper()  # type: ignore[union-attr]
    await update.message.reply_text("Enter company/asset name:")  # type: ignore[union-attr]
    return UPDATE_ADD_NAME


async def update_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    context.user_data["add_name"] = update.message.text.strip()  # type: ignore[union-attr]
    await update.message.reply_text("Enter number of shares/units:")  # type: ignore[union-attr]
    return UPDATE_ADD_SHARES


async def update_add_shares(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return UPDATE_ADD_SHARES
    assert context.user_data is not None
    context.user_data["add_shares"] = text
    await update.message.reply_text("Enter cost price per share/unit:")  # type: ignore[union-attr]
    return UPDATE_ADD_COST


async def update_add_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return UPDATE_ADD_COST
    assert context.user_data is not None
    context.user_data["add_cost"] = text
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(c, callback_data=f"upd:cur:{c}") for c in _CURRENCIES]])
    await update.message.reply_text("Select currency:", reply_markup=keyboard)  # type: ignore[union-attr]
    return UPDATE_ADD_CURRENCY


async def update_add_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    currency = query.data.split(":", 2)[2]  # type: ignore[union-attr]
    assert context.user_data is not None
    context.user_data["add_currency"] = currency
    rows = [[InlineKeyboardButton(cat, callback_data=f"upd:cat:{cat}") for cat in _CATEGORIES[i : i + 2]] for i in range(0, len(_CATEGORIES), 2)]
    keyboard = InlineKeyboardMarkup(rows)
    await query.edit_message_text("Select category:", reply_markup=keyboard)  # type: ignore[union-attr]
    return UPDATE_ADD_CATEGORY


async def update_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    category = query.data.split(":", 2)[2]  # type: ignore[union-attr]
    assert context.user_data is not None
    ticker = context.user_data.pop("add_ticker", "")
    name = context.user_data.pop("add_name", ticker)
    shares = context.user_data.pop("add_shares", "0")
    cost = context.user_data.pop("add_cost", "0")
    currency = context.user_data.pop("add_currency", "USD")
    reply = handle_add_holding([ticker, name, shares, cost, currency, category])
    await query.edit_message_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


# --- Remove sub-flow ---


async def update_remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "upd:cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    ticker = data.split(":", 2)[2]  # upd:rm:AAPL
    assert context.user_data is not None
    context.user_data["upd_ticker"] = ticker
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🗑 Confirm Remove", callback_data="upd:rmconfirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel"),
            ]
        ]
    )
    await query.edit_message_text(  # type: ignore[union-attr]
        f"Remove <b>{ticker}</b> from portfolio. Are you sure?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return UPDATE_REMOVE_CONFIRM


async def update_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    assert context.user_data is not None
    ticker = context.user_data.pop("upd_ticker", "")
    context.user_data.pop("upd_action", None)

    if data == "upd:cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    reply = handle_remove_holding([ticker])
    await query.edit_message_text(reply)  # type: ignore[union-attr]
    return ConversationHandler.END


# --- Cash sub-flow ---

_CASH_DISPLAY = {
    "CASH_TWD": ("新台幣現金", "NT$"),
    "CASH_USD": ("美元現金", "$"),
}


async def update_cash_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    data: str = query.data  # type: ignore[union-attr]

    if data == "upd:cancel":
        await query.edit_message_text("Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    ticker = data.split(":", 2)[2]  # upd:cash:CASH_TWD
    if context.user_data is None:
        return ConversationHandler.END
    context.user_data["upd_ticker"] = ticker
    name, _ = _CASH_DISPLAY.get(ticker, (ticker, ""))
    await query.edit_message_text(  # type: ignore[union-attr]
        f"Enter new cash amount for <b>{name}</b> (numbers only):",
        parse_mode="HTML",
    )
    return UPDATE_CASH_AMOUNT


async def update_cash_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()  # type: ignore[union-attr]
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")  # type: ignore[union-attr]
        return UPDATE_CASH_AMOUNT

    if context.user_data is None:
        return ConversationHandler.END
    ticker = context.user_data.get("upd_ticker", "")
    name, symbol = _CASH_DISPLAY.get(ticker, (ticker, ""))
    context.user_data["upd_shares"] = "1"
    context.user_data["upd_cost"] = text

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="upd:confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="upd:cancel"),
            ]
        ]
    )
    formatted = f"{symbol}{amount:,.0f}"
    await update.message.reply_text(  # type: ignore[union-attr]
        f"Update <b>{name}</b>: {formatted}. Confirm?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return UPDATE_CONFIRM


def build_update_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("update", update_entry)],
        states={
            UPDATE_MENU: [CallbackQueryHandler(update_menu_action, pattern=r"^upd:menu:.+$")],
            UPDATE_PICK_TICKER: [CallbackQueryHandler(update_pick_ticker, pattern=r"^upd:(ticker:.+|cancel)$")],
            UPDATE_ENTER_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_enter_shares)],
            UPDATE_ENTER_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_enter_cost)],
            UPDATE_CONFIRM: [CallbackQueryHandler(update_confirm, pattern=r"^upd:(confirm|cancel)$")],
            UPDATE_ADD_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_add_ticker)],
            UPDATE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_add_name)],
            UPDATE_ADD_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_add_shares)],
            UPDATE_ADD_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_add_cost)],
            UPDATE_ADD_CURRENCY: [CallbackQueryHandler(update_add_currency, pattern=r"^upd:cur:.+$")],
            UPDATE_ADD_CATEGORY: [CallbackQueryHandler(update_add_category, pattern=r"^upd:cat:.+$")],
            UPDATE_REMOVE_PICK: [CallbackQueryHandler(update_remove_pick, pattern=r"^upd:(rm:.+|cancel)$")],
            UPDATE_REMOVE_CONFIRM: [CallbackQueryHandler(update_remove_confirm, pattern=r"^upd:(rmconfirm|cancel)$")],
            UPDATE_CASH_PICK: [CallbackQueryHandler(update_cash_pick, pattern=r"^upd:(cash:.+|cancel)$")],
            UPDATE_CASH_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_cash_amount)],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _handle_timeout),
                CallbackQueryHandler(_handle_timeout),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        conversation_timeout=120,
        allow_reentry=True,
        per_message=False,
    )
