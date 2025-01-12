from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Property(Base):
    __tablename__ = "listings_property"

    id = Column(UUID(as_uuid=True), primary_key=True)
    listing_id = Column(
        UUID(as_uuid=True), ForeignKey("listings_listing.id"), unique=True
    )
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    property_type = Column(String)
    building_type = Column(String)
    size_m2 = Column(Float)
    floor_number = Column(String)
    total_floors = Column(Integer)
    rooms = Column(Float)
    property_state = Column(String)
