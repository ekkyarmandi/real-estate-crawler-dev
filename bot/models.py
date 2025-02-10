from datetime import datetime as dt
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, func, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
import uuid
import json

from constants import DEFAULT_SETTINGS

Base = declarative_base()


class User(Base):
    __tablename__ = "bot_user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    chat_id = Column(String(255), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    profile_url = Column(String(255), nullable=False)
    settings = Column(Text, nullable=False, default=json.dumps(DEFAULT_SETTINGS))

    queues = relationship("Queue", back_populates="user")

    def settings_as_where_clause(self):
        settings = json.loads(self.settings)
        city = settings["city"]
        price_min, price_max = settings["price"].split("-")
        size_min, size_max = settings["size"].split("-")
        # city clause
        cities = settings["city"].split(",")
        if len(cities) > 1:
            city_clause = " OR ".join([f"city = '{city}'" for city in cities])
            city_clause = f"({city_clause})"
        else:
            city_clause = f"city = '{cities[0]}'"
        # rooms clause
        rooms = settings["rooms"].split(",")
        if len(rooms) > 1:
            rooms_clause = " OR ".join([f"rooms = {room}" for room in rooms])
            rooms_clause = f"({rooms_clause})"
        else:
            rooms_clause = f"rooms = {rooms[0]}"
        # rules
        rules = [
            f"{city_clause}",
            f"price >= {price_min}",
            f"price <= {price_max}",
            f"size_m2 >= {size_min}",
            f"size_m2 <= {size_max}",
            f"{rooms_clause}",
        ]
        return " AND ".join(rules)


class Queue(Base):
    __tablename__ = "listings_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    listing_id = Column(
        UUID(as_uuid=True), ForeignKey("listings_listing.id"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("bot_user.id"), nullable=False)
    is_sent = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="queues")
    listing = relationship("Listing", back_populates="queues")


class Listing(Base):
    __tablename__ = "listings_listing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    url = Column(String(255), nullable=False)
    city = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    municipality = Column(String(255), nullable=False)
    micro_location = Column(String(255), nullable=False)
    first_seen_at = Column(DateTime, nullable=False)

    queues = relationship("Queue", back_populates="listing")
    property = relationship("Property", back_populates="listing")


class Property(Base):
    __tablename__ = "listings_property"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True), ForeignKey("listings_listing.id"), nullable=False
    )
    size_m2 = Column(Float, nullable=False)
    rooms = Column(Float, nullable=False)

    listing = relationship("Listing", back_populates="property")


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
        self.first_seen_at = kwargs.get("first_seen_at", dt.now())

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

    def has_missings(self):
        return not self.city or not self.price or not self.size_m2 or not self.rooms

    def as_markdown(self):
        publication_date = self.first_seen_at.strftime("%Y-%m-%d")
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
