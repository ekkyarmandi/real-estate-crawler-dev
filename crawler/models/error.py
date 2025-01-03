from sqlalchemy import Column, String, Text, DateTime, func, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class Report(Base):
    __tablename__ = "listings_report"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    source_name = Column(String(255), nullable=True)
    total_pages = Column(Integer, nullable=False, default=0)
    total_listings = Column(Integer, nullable=False, default=0)
    total_actual_listings = Column(Integer, nullable=False, default=0)
    total_new_listings = Column(Integer, nullable=False, default=0)
    total_changed_listings = Column(Integer, nullable=False, default=0)
    item_scraped_count = Column(Integer, nullable=False, default=0)
    item_dropped_count = Column(Integer, nullable=False, default=0)
    response_error_count = Column(Integer, nullable=False, default=0)
    elapsed_time_seconds = Column(Float, nullable=False, default=0)


class Error(Base):
    __tablename__ = "listings_error"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    url = Column(Text, nullable=False, default="")
    error_type = Column(String(255), nullable=False)
    error_message = Column(Text, nullable=False)
    error_traceback = Column(Text, nullable=False)
