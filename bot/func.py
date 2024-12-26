from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from constants import ROOM_OPTIONS, CITY_OPTIONS
import re


def settings_as_message(settings: dict) -> str:
    message = (
        "⚙️ *Settings*\n"
        f"🏢 *City:* {settings['city']}\n"
        f"💰 *Price:* {settings['price']} €\n"
        f"📏 *Size:* {settings['size']} m2\n"
        f"🏠 *Rooms:* {settings['rooms']}\n"
        f"✅ *Enabled*\n"
    )
    message = re.sub(r"([\-.])", r"\\\1", message)
    return message


def create_settings_markup(settings: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🏢 City: {settings['city']}", callback_data="city"
                )
            ],
            [
                InlineKeyboardButton(
                    f"💰 Price: {settings['price']}",
                    callback_data="price",
                )
            ],
            [
                InlineKeyboardButton(
                    f"📏 Size: {settings['size']}",
                    callback_data="size",
                )
            ],
            [
                InlineKeyboardButton(
                    f"🏠 Rooms: {settings['rooms']}",
                    callback_data="rooms",
                )
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                InlineKeyboardButton("💾 Save", callback_data="save"),
            ],
        ]
    )


def create_select_city_options():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"📍 {city}", callback_data=city)]
            for city in CITY_OPTIONS
        ]
    )


def create_select_room_options():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏠 {room}", callback_data=room)]
            for room in ROOM_OPTIONS
        ]
    )


def dint(value):
    try:
        return int(value)
    except Exception:
        return 0


def min_max_validator(value: str) -> str | None:
    # Should only one hyphens
    hyphens = re.findall(r"-", value)
    if len(hyphens) > 1:
        return "Too much hyphens"
    elif len(hyphens) == 0:
        return "Should include hyphen"
    elif re.search(r"^\d", value) and re.search(r"-", value):
        # Split value
        min_value, max_value = list(map(dint, value.split("-")))
        if min_value < 1:
            return "X should more than 0"
        if min_value > max_value:
            return "X should less than Y value"
    elif not re.search(r"\d", value):
        return "Must include number"
    elif not re.search(r"^\d", value):
        return "X should not be empty"
