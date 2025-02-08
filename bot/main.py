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
    # load user settings as dictionary
    user_settings = json.loads(user.settings)
    # convert rooms to list
    settings_rooms = user_settings["rooms"]
    if isinstance(settings_rooms, str):
        user_settings["rooms"] = settings_rooms.split(",")
    # convert city to list
    settings_cities = user_settings["city"]
    if isinstance(settings_cities, str):
        user_settings["city"] = settings_cities.split(",")
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
        if "temp_rooms" not in context.user_data:
            context.user_data["temp_rooms"] = list(settings["rooms"])
        if "temp_city" not in context.user_data:
            context.user_data["temp_city"] = list(settings["city"])
    else:
        db = next(get_db())
        chat_id = str(update.callback_query.message.chat.id)
        user = db.query(User).filter(User.chat_id == chat_id).first()
        settings = json.loads(user.settings)
        if isinstance(settings["rooms"], str):
            settings["rooms"] = settings["rooms"].split(",")
        if isinstance(settings["city"], str):
            settings["city"] = settings["city"].split(",")
        context.user_data["settings"] = settings
        context.user_data["temp_rooms"] = list(settings["rooms"])
        context.user_data["temp_city"] = list(settings["city"])
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
        selected_city = context.user_data.get("temp_city", [])
        reply_markup = create_select_city_markup(selected_city)
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
        # Use temporary rooms for initial selection
        selected_rooms = context.user_data.get("temp_rooms", [])
        reply_markup = create_select_room_markup(selected_rooms)
        message = dict(
            text="*Select number of rooms \(multi\-select\):*",
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

    # Handle city selection
    if query.data.startswith("city_"):
        city = query.data[5:]
        selected_cities = context.user_data.get("temp_city", [])
        if city in selected_cities:
            selected_cities.remove(city)
        else:
            selected_cities.append(city)
        context.user_data["temp_city"] = selected_cities
        reply_markup = create_select_city_markup(selected_cities)
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
    elif query.data == "cities_done":
        temp_city = context.user_data["temp_city"]
        if len(temp_city) == 0:
            temp_city = [CITY_OPTIONS[0]]
            context.user_data["temp_city"] = [CITY_OPTIONS[0]]
        context.user_data["settings"]["city"] = list(temp_city)
        await configure_settings_command(update, context)
        return ConversationHandler.END
    elif query.data == "cities_cancel":
        if "temp_city" in context.user_data:
            del context.user_data["temp_city"]
        await configure_settings_command(update, context)
        return ConversationHandler.END

    # Handle room selection
    if query.data.startswith("room_"):
        room = query.data[5:]
        # Get current selected rooms from temporary storage
        selected_rooms = context.user_data.get("temp_rooms", [])
        # Toggle selection
        if room in selected_rooms:
            selected_rooms.remove(room)
        else:
            selected_rooms.append(room)
        # Update temporary storage
        context.user_data["temp_rooms"] = selected_rooms
        # Update the markup with new selection
        reply_markup = create_select_room_markup(selected_rooms)
        await query.edit_message_text(
            text="*Select number of rooms \(multi\-select\):*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END
    elif query.data == "rooms_done":
        temp_rooms = sorted(context.user_data["temp_rooms"])
        context.user_data["settings"]["rooms"] = list(temp_rooms)
        await configure_settings_command(update, context)
        return ConversationHandler.END
    elif query.data == "rooms_cancel":
        if "temp_rooms" in context.user_data:
            del context.user_data["temp_rooms"]
        await configure_settings_command(update, context)
        return ConversationHandler.END

    # Handle enable/disable selection
    if query.data in ["enable", "disable"]:
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
        settings = context.user_data.get("settings")
        # stringify settings rooms
        if isinstance(settings["rooms"], list):
            rooms = list(map(str, settings["rooms"]))
            settings["rooms"] = ",".join(rooms)
        if isinstance(settings["city"], list):
            cities = list(map(str, settings["city"]))
            settings["city"] = ",".join(cities)
        new_settings = json.dumps(settings)
        is_enabled = settings.get("is_enabled", True)
        if user.settings != new_settings and is_enabled:
            user.settings = new_settings
            db.commit()
            db.refresh(user)
        # send listings after user save the settings
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
        # split the rooms
        settings_rooms = context.user_data["settings"]["rooms"]
        settings_rooms = settings_rooms.split(",")
        context.user_data["settings"]["rooms"] = settings_rooms
        # reset the rooms
        context.user_data["temp_rooms"] = context.user_data["settings"]["rooms"]
        # reset the city
        context.user_data["temp_city"] = context.user_data["settings"]["city"]
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
