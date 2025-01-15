import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base, TimestampMixin


class Seller(Base, TimestampMixin):
    __tablename__ = "listings_seller"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_seller_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    seller_type = Column(String, nullable=False)
    primary_phone = Column(String, nullable=True)
    primary_email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("listings_agent.id"), nullable=True
    )

    agent = relationship("Agent", back_populates="sellers")
    # listings = relationship("Listing", back_populates="seller")

    def __repr__(self):
        return f"<Seller {self.name}>"
