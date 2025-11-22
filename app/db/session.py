"""
Database session management and initialization.
Provides async database sessions with connection pooling.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        """Initialize database manager."""
        self.engine = None
        self.async_session_factory = None
        
    def init_db(self):
        """Initialize database engine and session factory."""
        # Build engine kwargs, excluding pool parameters for SQLite
        engine_kwargs = {
            "echo": settings.debug,
        }
        
        # Only add pool parameters for non-SQLite databases
        if not str(settings.database_url).startswith("sqlite"):
            engine_kwargs.update({
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_pre_ping": True,  # Verify connections before using
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            })
        
        # Create async engine with connection pooling
        self.engine = create_async_engine(
            str(settings.database_url),
            **engine_kwargs
        )
        
        # Create async session factory
        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
        logger.info("Database engine initialized successfully")
    
    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    
    async def drop_tables(self):
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session.
        
        Yields:
            AsyncSession: Database session
        """
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def session_context(self) -> AsyncSession:
        """
        Context manager for database sessions.
        
        Returns:
            AsyncSession: Database session
        """
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    async def health_check(self) -> bool:
        """
        Check database health.
        
        Returns:
            bool: True if database is healthy
        """
        try:
            from sqlalchemy import text
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async for session in db_manager.get_session():
        yield session


async def init_database():
    """Initialize database on application startup."""
    db_manager.init_db()
    await db_manager.create_tables()
    logger.info("Database initialized successfully")


async def close_database():
    """Close database connections on application shutdown."""
    await db_manager.close()
