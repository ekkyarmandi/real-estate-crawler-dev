from models.base import Base, TimestampMixin
from models.agent import Agent
from models.seller import Seller
from models.property import Property

# Import other models here...

# This ensures all models are registered with SQLAlchemy
__all__ = ["Base", "TimestampMixin", "Agent", "Seller", "Property"]
