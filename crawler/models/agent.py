from sqlalchemy import Column, String, Boolean, Date, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from models.base import Base, TimestampMixin


class Agent(Base, TimestampMixin):
    __tablename__ = "listings_agent"

    id = Column(UUID(as_uuid=True), primary_key=True)
    agent_id = Column(String)
    business_site_address = Column(String)
    company_manager = Column(String)
    company_owners = Column(String)
    company_type_id = Column(String)
    company_type_name = Column(String)
    email = Column(String)
    formal_owners_full_name = Column(String)
    hq_address = Column(String)
    identification_number = Column(String)
    insurance_contract_expiry_date = Column(Date)
    insurance_expiry = Column(Boolean, default=False)
    insurance_expiry_within_month = Column(Boolean, default=False)
    main_activity = Column(String)
    name = Column(String)
    owner_full_name = Column(String)
    owner_national_number = Column(String)
    registry_date = Column(Date)
    registry_number = Column(String, index=True)
    registry_statement_date = Column(Date)
    registry_statement_number = Column(String)
    representatives_full_name = Column(String)
    tax_number = Column(String)
    web_page = Column(String)

    sellers = relationship("Seller", back_populates="agent")

    # Create index on registry_number
    __table_args__ = (Index("ix_listings_agent_registry_number", "registry_number"),)

    def __repr__(self):
        return f"<Agent {self.name}>"
