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
from models import User, CustomListing
from constants import DEFAULT_SETTINGS, CITY_OPTIONS, ROOM_OPTIONS
from func import (
    settings_as_message,
    min_max_validator,
)
from markups import (
    create_select_city_markup,
    create_select_room_markup,
    create_settings_markup,
    create_enable_markup,
)
import json
import uuid
import logging

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
        chat_id=update.message.chat.id,
        username=username,
        name=update.message.chat.full_name,
        profile_url=f"https://t.me/{username}",
        settings=json.dumps(DEFAULT_SETTINGS),
    )
    q = text(
        """
        INSERT INTO bot_user (
            id,
            created_at,
            updated_at,
            chat_id,
            username,
            name,
            profile_url,
            settings
        ) VALUES (:id, :created_at, :updated_at, :chat_id, :username, :name, :profile_url, :settings)
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
    message = (
        f"Hi! 👋🏼 @{username}\n\n"
        "I'm your real estate bot. I'll send you new listings in your area.\n"
        "You can configure your /settings by clicking the ⚙️ button."
    )
    await update.message.reply_text(message)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Query user
    db = next(get_db())
    chat_id = str(update.message.chat.id)
    user = db.query(User).filter(User.chat_id == chat_id).first()
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
        chat_id = str(update.callback_query.message.chat.id)
        user = db.query(User).filter(User.chat_id == chat_id).first()
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

    # Handle settings callbacks
    if query.data == "configure":
        await configure_settings_command(update, context)
    elif query.data == "city":
        reply_markup = create_select_city_markup()
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
            "• Enter price range: min-max € (e.g., 150000-350000)"
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
            "• Enter apartment size range: min-max (e.g., 45-80)"
        )
        await query.edit_message_text(text=message)
        return SIZE
    elif query.data == "rooms":
        reply_markup = create_select_room_markup()
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
    elif query.data == "is_enabled":
        reply_markup = create_enable_markup()
        message = dict(
            text="*Enable or disable notifications:*",
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

    # Handle city and room selection
    if query.data in CITY_OPTIONS:
        context.user_data["settings"]["city"] = query.data
        await configure_settings_command(update, context)
        return ConversationHandler.END
    if query.data in ROOM_OPTIONS:
        context.user_data["settings"]["rooms"] = query.data
        await configure_settings_command(update, context)
        return ConversationHandler.END
    elif query.data in ["enable", "disable"]:
        context.user_data["settings"]["is_enabled"] = query.data == "enable"
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
        chat_id = str(update.callback_query.message.chat.id)
        user = db.query(User).filter(User.chat_id == chat_id).first()
        new_settings = json.dumps(context.user_data["settings"])
        is_enabled = context.user_data["settings"].get("is_enabled", True)
        if user.settings != new_settings and is_enabled:
            user.settings = new_settings
            db.commit()
            db.refresh(user)
            # send listings based on user settings changed
            cols = [
                "id",
                "url",
                "city",
                "price",
                "municipality",
                "micro_location",
                "size_m2",
                "rooms",
            ]
            q = text(
                f"""
                SELECT
                    listings.id,
                    listings.url,
                    listings.city as city,
                    listings.price as price,
                    listings.municipality,
                    listings.micro_location,
                    COALESCE(MAX(properties.size_m2), 0) AS size_m2,
                    COALESCE(MAX(properties.rooms), 0) AS rooms
                FROM listings_listing as listings
                JOIN listings_property as properties ON listings.id = properties.listing_id
                WHERE {user.settings_as_where_clause()}
                GROUP BY listings.id LIMIT 10;
                """
            )
            result = db.execute(q)
            listings = result.fetchall()
            # convert raw data into custom listings
            listings = [dict(zip(cols, listing)) for listing in listings]
            listings = [CustomListing(**item) for item in listings]
            for listing in listings:
                message = listing.as_markdown()
                await update.callback_query.message.reply_text(text=message)

    return ConversationHandler.END


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "settings" in context.user_data:
        db = next(get_db())
        chat_id = str(update.callback_query.message.chat.id)
        user = db.query(User).filter(User.chat_id == chat_id).first()
        context.user_data["settings"] = json.loads(user.settings)
    return ConversationHandler.END


# Handlers
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    try:
        await update.message.reply_text(f"Error: {context.error}")
    except Exception as e:
        await update.callback_query.message.reply_text(f"Error: {context.error}")
        logger.error(f"Error sending error message: {e}")


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
