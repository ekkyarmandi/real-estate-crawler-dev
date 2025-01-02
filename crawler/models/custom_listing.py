from datetime import datetime
import json
from sqlalchemy.dialects.postgresql import UUID


class CustomListing:
    id: str | UUID
    url: str
    city: str
    price: float
    size_m2: float
    rooms: float
    municipality: str
    micro_location: str

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.url = kwargs.get("url", "")
        self.city = kwargs.get("city", "")
        self.price = kwargs.get("price", 0.0)
        self.size_m2 = kwargs.get("size_m2", 0.0)
        self.rooms = kwargs.get("rooms", 0.0)
        self.municipality = kwargs.get("municipality", "")
        self.micro_location = kwargs.get("micro_location", "")

    def validate_settings(self, settings):
        settings = json.loads(settings)
        city = settings["city"]
        price_min, price_max = settings["price"].split("-")
        size_min, size_max = settings["size"].split("-")
        rooms = settings["rooms"]
        is_enabled = settings.get("is_enabled", True)
        if not is_enabled:
            return False
        # is listing.city is contain settings.city?
        if self.city and not city in self.city:
            return False
        # is listing.rooms is equal to settings.rooms?
        elif float(self.rooms) != float(rooms):
            return False
        # is listing.price is between price min and price max?
        elif not (float(price_min) < float(self.price) < float(price_max)):
            return False
        # is listing.size is between size min and size max?
        elif not (float(size_min) < float(self.size_m2) < float(size_max)):
            return False
        return True

    def as_markdown(self):
        publication_date = datetime.now().strftime("%Y-%m-%d")
        location = f"{self.city} - {self.municipality} - {self.micro_location}"
        return (
            f"🏢 City: {self.city}\n"
            f"📍 Location: {location}\n"
            f"💰 Price: € {int(self.price):,d}\n"
            f"📏 Size: {self.size_m2:,.2f} m²\n"
            f"🏠 Rooms: {self.rooms:,.2f}\n"
            f"📅 Publication date: {publication_date}\n"
            f"🔗 Link: {self.url}"
        )
