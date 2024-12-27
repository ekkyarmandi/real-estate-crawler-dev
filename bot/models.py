from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, func, Integer, Float
from constants import DEFAULT_SETTINGS
import uuid
import json

Base = declarative_base()


class User(Base):
    __tablename__ = "bot_user"
    # COMMENT: rooms options -

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    chat_id = Column(String(255), unique=True, nullable=False)
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


class CustomListing:
    url: str
    city: str
    price: float
    size_m2: float
    rooms: float
    municipality: str
    micro_location: str

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
            f"🏢 City: {self.city}\n"
            f"📍 Location: {location}\n"
            f"💰 Price: € {int(self.price):,d}\n"
            f"📏 Size: {self.size_m2:,.2f} m²\n"
            f"🏠 Rooms: {self.rooms:,.2f}\n"
            f"📅 Publication date: {publication_date}\n"
            f"🔗 Link: {self.url}"
        )
