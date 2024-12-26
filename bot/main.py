from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    Application,
    MessageHandler,
    filters,
)
from datetime import datetime
from decouple import config
from database import get_db
from sqlalchemy import text
from models import User
from constants import DEFAULT_SETTINGS, CITY_OPTIONS, ROOM_OPTIONS
from func import (
    create_select_city_options,
    create_select_room_options,
    settings_as_message,
    create_settings_markup,
    min_max_validator,
)
import json
import uuid
import logging
import re

TOKEN: Final = config("TELEGRAMBOT_TOKEN")


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Markup
configure_markup = InlineKeyboardMarkup(
    [[InlineKeyboardButton("⚙️ Configure", callback_data="configure")]]
)


# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # insert user to database, on conflict update
    username = update.message.chat.username
    user_item = dict(
        id=str(uuid.uuid4()),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        username=username,
        name=update.message.chat.full_name,
        profile_url=f"https://t.me/{username}",
        settings=json.dumps(DEFAULT_SETTINGS),
    )
    q = text(
        """
        INSERT INTO bot_user (id, created_at, updated_at, username, name, profile_url, settings) VALUES (:id, :created_at, :updated_at, :username, :name, :profile_url, :settings)
        ON CONFLICT (username) DO UPDATE SET name = :name, profile_url = :profile_url, updated_at = :updated_at;
        """
    )
    db = next(get_db())
    try:
        db.execute(q, user_item)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning user to database: {e}")
    # send hi to user
    await update.message.reply_text(f"Hi! 👋🏼 @{username}")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Query user
    db = next(get_db())
    user = db.query(User).filter(User.username == update.message.chat.username).first()
    # Convert user settings as message
    user_settings = json.loads(user.settings)
    await update.message.reply_text(
        settings_as_message(user_settings),
        reply_markup=configure_markup,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def configure_settings_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if context.user_data.get("settings"):
        settings = context.user_data["settings"]
    else:
        db = next(get_db())
        username = update.callback_query.message.chat.username
        user = db.query(User).filter(User.username == username).first()
        settings = json.loads(user.settings)
        context.user_data["settings"] = settings
    settings_markup = create_settings_markup(settings)
    message = dict(
        text="*Configure your settings:*",
        reply_markup=settings_markup,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(**message)
    else:
        await update.message.reply_text(**message)
    return ConversationHandler.END


# Define states
PRICE, SIZE, CANCEL = range(3)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "configure":
        await configure_settings_command(update, context)
    elif query.data == "city":
        reply_markup = create_select_city_options()
        message = dict(
            text="*Select city:*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(**message)
        else:
            await update.message.reply_text(**message)
        return ConversationHandler.END
    elif query.data == "price":
        message = (
            "Enter new price range:\n"
            "• Must be numbers only\n"
            "• Format: X-Y where X < Y\n"
            "• Minimum value > 0\n"
            "• Must include hyphen (-)\n"
        )
        await query.edit_message_text(text=message)
        return PRICE
    elif query.data == "size":
        message = (
            "Enter new size range:\n"
            "• Must be numbers only\n"
            "• Format: X-Y where X < Y\n"
            "• Minimum value > 0\n"
            "• Must include hyphen (-)\n"
        )
        await query.edit_message_text(text=message)
        return SIZE
    elif query.data == "rooms":
        reply_markup = create_select_room_options()
        message = dict(
            text="*Select number of rooms:*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(**message)
        else:
            await update.message.reply_text(**message)
        return ConversationHandler.END
    elif query.data == "save":
        await save_settings(update, context)
        await query.edit_message_text(text="Settings have been saved!")
        return ConversationHandler.END
    elif query.data == "cancel":
        await cancel_settings(update, context)
        await query.edit_message_text(text="Settings change cancelled!")
        return ConversationHandler.END

    if query.data in CITY_OPTIONS:
        context.user_data["settings"]["city"] = query.data
        await configure_settings_command(update, context)
        return ConversationHandler.END
    if query.data in ROOM_OPTIONS:
        context.user_data["settings"]["rooms"] = query.data
        await configure_settings_command(update, context)
        return ConversationHandler.END


async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    error_message = min_max_validator(new_value)
    if error_message:
        msg = f"⛔️ Price Error: {error_message}!"
        await update.message.reply_text(text=msg)
    else:
        context.user_data["settings"]["price"] = new_value
    await configure_settings_command(update, context)
    return ConversationHandler.END


async def update_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    error_message = min_max_validator(new_value)
    if error_message:
        msg = f"⛔️ Size Error: {error_message}!"
        await update.message.reply_text(text=msg)
    else:
        context.user_data["settings"]["size"] = new_value
    await configure_settings_command(update, context)
    return ConversationHandler.END


async def save_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "settings" in context.user_data:
        db = next(get_db())
        username = update.callback_query.message.chat.username
        user = db.query(User).filter(User.username == username).first()
        new_settings = json.dumps(context.user_data["settings"])
        user.settings = new_settings
        db.commit()
        db.refresh(user)
    return ConversationHandler.END


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "settings" in context.user_data:
        db = next(get_db())
        username = update.callback_query.message.chat.username
        user = db.query(User).filter(User.username == username).first()
        context.user_data["settings"] = json.loads(user.settings)
    return ConversationHandler.END


# Handlers
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Error: {context.error}")


if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))

    # Conversation handler for updating settings
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_size)],
            CANCEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_settings)],
        },
        fallbacks=[CommandHandler("cancel", cancel_settings)],
    )
    app.add_handler(conv_handler)

    # Errors
    app.add_error_handler(error)

    # Run Polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)
