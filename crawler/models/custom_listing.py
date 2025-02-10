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
        price_min, price_max = settings["price"].split("-")
        size_min, size_max = settings["size"].split("-")
        rooms = settings["rooms"].split(",")
        rooms = [float(room) for room in rooms]
        cities = settings["city"].split(",")
        is_enabled = settings.get("is_enabled", True)
        if not is_enabled:
            return False
        # is listing.city is contain settings.city?
        if self.city and not any(city in self.city for city in cities):
            return False
        # is listing.rooms is equal to settings.rooms?
        elif self.rooms and float(self.rooms) not in [float(room) for room in rooms]:
            return False
        # is listing.price is between price min and price max?
        elif self.price and not (
            float(price_min) < float(self.price) < float(price_max)
        ):
            return False
        # is listing.size is between size min and size max?
        elif (
            self.size_m2
            and size_min
            and size_max
            and not (float(size_min) < float(self.size_m2) < float(size_max))
        ):
            return False
        return True

    def as_markdown(self):
        # replace the missings value with empty strings
        if not self.size_m2:
            size = "N/A"
        else:
            size = f"{self.size_m2:,.2f}"
        if not self.rooms:
            rooms = "N/A"
        else:
            rooms = f"{self.rooms:,.2f}"
        if not self.price:
            price = -1
        else:
            price = self.price
        if not self.city:
            city = "N/A"
        else:
            city = self.city
        if not self.municipality:
            municipality = "N/A"
        else:
            municipality = self.municipality
        if not self.micro_location:
            micro_location = "N/A"
        else:
            micro_location = self.micro_location
        # format publication date and location
        publication_date = self.first_seen_at.strftime("%Y-%m-%d")
        if city == "N/A" and municipality == "N/A" and micro_location == "N/A":
            location = "N/A"
        else:
            location = f"{city} - {municipality} - {micro_location}"
        return (
            f"🏢 City: {city}\n"
            f"📍 Location: {location}\n"
            f"💰 Price: € {int(price):,d}\n"
            f"📏 Size: {size} m²\n"
            f"🏠 Rooms: {rooms}\n"
            f"📅 Publication date: {publication_date}\n"
            f"🔗 Link: {self.url}"
        )
