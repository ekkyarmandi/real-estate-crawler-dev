from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, func
import uuid
import json

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
    settings = Column(Text, nullable=False, default="{}")

    def settings_as_where_clause(self):
        settings = json.loads(self.settings)
        city = settings["city"]
        price_min, price_max = settings["price"].split("-")
        size_min, size_max = settings["size"].split("-")
        rooms = settings["rooms"]
        return f"city = '{city}' AND price >= {price_min} AND price <= {price_max} AND size_m2 >= {size_min} AND size_m2 <= {size_max} AND rooms = {rooms}"
