"""
Database connection and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from typing import AsyncGenerator
from .config import settings

# Convert postgresql:// to postgresql+asyncpg:// for async support
async_database_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

# Create async SQLAlchemy engine
engine = create_async_engine(
    async_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug,  # Log SQL queries in debug mode
)

# Create async SessionLocal class
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions
    Usage: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
