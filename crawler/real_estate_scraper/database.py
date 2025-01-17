from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decouple import config

engine = create_engine(
    config("DB_URL"),
    pool_size=5,  # Maximum number of connections
    max_overflow=10,  # Maximum number of connections that can be created beyond pool_size
    pool_timeout=30,  # Seconds to wait before timing out
    pool_recycle=1800,  # Recycle connections after 1800 seconds
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
