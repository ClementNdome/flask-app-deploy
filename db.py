from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Database configuration
# Using credentials provided: user=postgres password=password_0323
DATABASE_URL = "postgresql://postgres:0323@localhost:5432/schools_ke"

# Create engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

def get_session():
    """Return a new SQLAlchemy session."""
    return SessionLocal()
