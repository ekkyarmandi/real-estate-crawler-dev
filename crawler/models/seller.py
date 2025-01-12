from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, DateTime, func, Boolean, String, ForeignKey
import uuid
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Seller(Base):
    __tablename__ = "listings_seller"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    source_seller_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    seller_type = Column(String, nullable=False)
    primary_phone = Column(String, nullable=True)
    primary_email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("listings_agent.id"), nullable=True
    )

    def __repr__(self):
        return f"<Seller {self.name}>"
