from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import dotenv

DATABASE_URL = dotenv.get_key(dotenv.find_dotenv(), "DATABASE_URL")

# Create engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

def get_session():
    """Return a new SQLAlchemy session."""
    return SessionLocal()
