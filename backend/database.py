import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in your .env file")

# Create the SQLAlchemy engine
# pool_pre_ping=True checks connection health before using it
# pool_size=5 keeps 5 connections open at all times
# max_overflow=10 allows up to 10 extra connections under load
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False
    # Set echo=True temporarily if you want to see raw SQL in terminal
)

# SessionLocal is the factory for database sessions
# Each request gets its own session, closed after the request ends
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class that all ORM models will inherit from
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Usage in a route:
        from backend.database import get_db
        from sqlalchemy.orm import Session
        from fastapi import Depends

        @app.get("/example")
        def example_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection():
    """
    Call this on startup to verify the database is reachable.
    Prints success or raises an error with a clear message.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connection successful.")
    except Exception as e:
        raise ConnectionError(
            f"Could not connect to the database.\n"
            f"Check your DATABASE_URL in .env\n"
            f"Error: {e}"
        )