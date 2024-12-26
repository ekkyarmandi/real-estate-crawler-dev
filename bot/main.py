from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
import json
import uuid
import logging

TOKEN: Final = config("TELEGRAMBOT_TOKEN")
DEFAULT_SETTINGS = {
    "city": "Beograd",
    "price": "50000-150000",
    "size": "45-120",
    "rooms": "3.0",
}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Markup
setting_markup = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("City", callback_data="city")],
        [InlineKeyboardButton("Price", callback_data="price")],
        [InlineKeyboardButton("Size", callback_data="size")],
        [InlineKeyboardButton("Rooms", callback_data="rooms")],
        [InlineKeyboardButton("Console", callback_data="console")],
        [
            InlineKeyboardButton("Cancel", callback_data="cancel"),
            InlineKeyboardButton("Save", callback_data="save"),
        ],
    ]
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
    await update.message.reply_text(f"Hai! 👋🏼 @{username}")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Query user
    db = next(get_db())
    user = db.query(User).filter(User.username == update.message.chat.username).first()
    # Put user settings in a context
    if "settings" not in context.user_data:
        context.user_data["settings"] = json.loads(user.settings)
    await update.message.reply_text(
        "Choose a setting to update:", reply_markup=setting_markup
    )


# Define states
CITY, PRICE, SIZE, ROOMS, CANCEL = range(5)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "city":
        # Load user settings from context
        # user_settings = context.user_data["settings"]
        # Send message without edit message
        # await query.message.reply_text(
        #     text=f"Current city: {user_settings['city']}", reply_markup=setting_markup
        # )
        await query.message.reply_text(text="Please enter the new city:")
        return CITY
    elif query.data == "price":
        await query.message.reply_text(text="Please enter the new price range:")
        return PRICE
    elif query.data == "size":
        await query.edit_message_text(text="Please enter the new size range:")
        return SIZE
    elif query.data == "rooms":
        await query.edit_message_text(text="Please enter the new number of rooms:")
        return ROOMS
    elif query.data == "console":
        user_settings = context.user_data["settings"]
        await query.edit_message_text(text=f"Current settings: {user_settings}")
        await settings_command(update, context)
        return ConversationHandler.END
    elif query.data == "save":
        await query.edit_message_text(text="Settings have been saved!")
        return ConversationHandler.END
    elif query.data == "cancel":
        return CANCEL


async def update_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_city = update.message.text
    # Update the city in the settings
    context.user_data["settings"]["city"] = new_city
    await update.message.reply_text(f"City updated to {new_city}.")
    # Show the inline keyboard again
    await settings_command(update, context)
    return ConversationHandler.END


async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    # TODO: update the price in the settings
    # context.user_data['settings']['price'] = new_price
    await update.message.reply_text(f"Price range updated to {new_price}.")
    # Show the inline keyboard again
    await settings_command(update, context)
    return ConversationHandler.END


async def update_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_size = update.message.text
    # TODO: Update the size in the settings
    # context.user_data['settings']['size'] = new_size
    await update.message.reply_text(f"Size range updated to {new_size}.")
    # Show the inline keyboard again
    await settings_command(update, context)
    return ConversationHandler.END


async def update_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_rooms = update.message.text
    # TODO: Update the rooms in the settings
    # context.user_data['settings']['rooms'] = new_rooms
    await update.message.reply_text(f"Number of rooms updated to {new_rooms}.")
    # Show the inline keyboard again
    await settings_command(update, context)
    return ConversationHandler.END


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # reset user settings to before the conversation
    db = next(get_db())
    user = db.query(User).filter(User.username == update.message.chat.username).first()
    context.user_data["settings"] = json.loads(user.settings)
    await update.message.reply_text(text="Settings cancelled!")
    return CANCEL


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
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_city)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_size)],
            ROOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_rooms)],
            CANCEL: [CommandHandler("cancel", cancel_settings)],
        },
        fallbacks=[CommandHandler("cancel", cancel_settings)],
    )

    app.add_handler(conv_handler)

    # Errors
    app.add_error_handler(error)

    # Run Polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)
