from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from constants import ROOM_OPTIONS, CITY_OPTIONS


def create_settings_markup(settings: dict) -> InlineKeyboardMarkup:
    is_enabled = "✅ Enabled" if settings.get("is_enabled", True) else "❌ Disabled"
    price = settings.get("price").split("-")
    settings_price = f"€{int(price[0]):,d}-{int(price[1]):,d}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏙 City: {settings['city']}", callback_data="city")],
            [
                InlineKeyboardButton(
                    f"💰 Price: {settings_price}",
                    callback_data="price",
                )
            ],
            [
                InlineKeyboardButton(
                    f"📐 Size: {settings['size']}",
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
                InlineKeyboardButton(
                    is_enabled,
                    callback_data="is_enabled",
                )
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                InlineKeyboardButton("💾 Save", callback_data="save"),
            ],
        ]
    )


def create_select_city_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"📍 {city}", callback_data=city)]
            for city in CITY_OPTIONS
        ]
    )


def create_select_room_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏠 {room}", callback_data=room)]
            for room in ROOM_OPTIONS
        ]
    )


def create_enable_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Enable", callback_data="enable")],
            [InlineKeyboardButton("❌ Disable", callback_data="disable")],
        ]
    )
