import re


def settings_as_message(settings: dict) -> str:
    is_enabled = "✅ *Enabled*" if settings.get("is_enabled", True) else "❌ *Disabled*"
    price = settings.get("price").split("-")
    settings_price = f"€{int(price[0]):,d}-{int(price[1]):,d}"
    rooms = ",".join(settings.get("rooms"))
    message = (
        "⚙️ *Settings*\n"
        f"🏙️ *City:* {settings['city']}\n"
        f"💰 *Price:* {settings_price}\n"
        f"📐 *Size:* {settings['size']} m2\n"
        f"🏠 *Rooms:* {rooms}\n"
        f"{is_enabled}\n"
    )
    message = re.sub(r"([\-.])", r"\\\1", message)
    return message


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
