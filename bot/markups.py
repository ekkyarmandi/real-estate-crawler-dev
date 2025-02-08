from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from constants import ROOM_OPTIONS, CITY_OPTIONS


def create_settings_markup(settings: dict) -> InlineKeyboardMarkup:
    is_enabled = "✅ Enabled" if settings.get("is_enabled", True) else "❌ Disabled"
    price = settings.get("price").split("-")
    settings_price = f"€{int(price[0]):,d}-{int(price[1]):,d}"
    rooms_value = settings.get("rooms")
    if isinstance(rooms_value, list):
        rooms = ",".join(rooms_value)
    else:
        rooms = rooms_value
    cities_value = settings.get("city")
    if isinstance(cities_value, list):
        cities = ",".join(cities_value)
    else:
        cities = cities_value
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏙 City: {cities}", callback_data="city")],
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
                    f"🏠 Rooms: {rooms}",
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


def create_select_city_markup(selected_cities=None):
    keyboard = []
    for city in CITY_OPTIONS:
        # Add checkmark if city is selected
        text = f"✅ {city}" if city in selected_cities else f"📍 {city}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"city_{city}")])
    # Add Done and Cancel buttons
    keyboard.append([InlineKeyboardButton("✔️ Done", callback_data="cities_done")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cities_cancel")])
    return InlineKeyboardMarkup(keyboard)


def create_select_room_markup(selected_rooms=None):
    if selected_rooms is None:
        selected_rooms = []
    keyboard = []
    for room in ROOM_OPTIONS:
        # Add checkmark if room is selected
        text = f"✅ {room}" if room in selected_rooms else f"🏠 {room}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"room_{room}")])
    # Add Done button
    keyboard.append([InlineKeyboardButton("✔️ Done", callback_data="rooms_done")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="rooms_cancel")])
    return InlineKeyboardMarkup(keyboard)


def create_enable_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Enable", callback_data="enable")],
            [InlineKeyboardButton("❌ Disable", callback_data="disable")],
        ]
    )
