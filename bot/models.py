from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, func, Integer, Float
import uuid
import json

Base = declarative_base()

DEFAULT_SETTINGS = {
    "city": "Beograd",
    "price": "50000-150000",
    "size": "45-120",
    "rooms": "3.0",
}


class User(Base):
    __tablename__ = "bot_user"
    # COMMENT: rooms options - 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    username = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    profile_url = Column(String(255), nullable=False)
    settings = Column(Text, nullable=False, default=json.dumps(DEFAULT_SETTINGS))

    def settings_as_where_clause(self):
        settings = json.loads(self.settings)
        city = settings["city"]
        price_min, price_max = settings["price"].split("-")
        size_min, size_max = settings["size"].split("-")
        rooms = settings["rooms"]
        return f"city = '{city}' AND price >= {price_min} AND price <= {price_max} AND size_m2 >= {size_min} AND size_m2 <= {size_max} AND rooms = {rooms}"


class Listing:
    url: str
    city: str
    price: float
    size_m2: float
    rooms: float
    municipality: str
    micro_location: str
    settings: str

    def __init__(self, **kwargs):
        self.url = kwargs.get("url", "")
        self.city = kwargs.get("city", "")
        self.price = kwargs.get("price", 0.0)
        self.size_m2 = kwargs.get("size_m2", 0.0)
        self.rooms = kwargs.get("rooms", 0.0)
        self.municipality = kwargs.get("municipality", "")
        self.micro_location = kwargs.get("micro_location", "")

    def as_markdown(self):
        publication_date = datetime.now().strftime("%Y-%m-%d")
        location = f"{self.city} - {self.municipality} - {self.micro_location}"
        return (
            f"🏢 City: {self.settings.city}\n"
            f"📍 Location: {location}\n"
            f"💰 Price: € {int(self.price):,d}\n"
            f"📏 Size: {self.size_m2:,.2f} m²\n"
            f"🏠 Rooms: {self.rooms:,.2f}\n"
            f"📅 Publication date: {publication_date}\n"
            f"🔗 Link: {self.url}"
        )
