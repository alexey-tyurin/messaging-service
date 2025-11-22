"""Test configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi.testclient import TestClient
import redis.asyncio as redis

from app.main import app
from app.models.database import Base
from app.db.session import get_db
from app.core.config import settings
from app.providers.base import ProviderFactory


# Override settings for testing
settings.database_url = "sqlite+aiosqlite:///:memory:"
settings.redis_url = "redis://localhost:6379/15"  # Use different DB for tests


# Initialize providers once at module load
@pytest.fixture(scope="session", autouse=True)
def initialize_providers():
    """Initialize providers for all tests synchronously."""
    # Use asyncio.run to initialize providers
    asyncio.run(ProviderFactory.init_providers())
    yield
    # Clean up providers
    try:
        asyncio.run(ProviderFactory.close_providers())
    except Exception:
        pass


@pytest.fixture(scope="function")
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        # Clean up after test
        try:
            await session.rollback()
        except Exception:
            pass
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def redis_client() -> AsyncGenerator:
    """Create Redis client for tests."""
    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    
    # Clear test database
    await client.flushdb()
    
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture(scope="function")
def client(async_db: AsyncSession) -> TestClient:
    """Create test client with overridden dependencies."""
    
    async def override_get_db():
        yield async_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_message_data():
    """Sample message data for tests."""
    return {
        "from": "+15551234567",
        "to": "+15559876543",
        "type": "sms",
        "body": "Test message",
    }


@pytest.fixture
def sample_email_data():
    """Sample email data for tests."""
    return {
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "type": "email",
        "body": "<p>Test email</p>",
        "attachments": [],
    }


@pytest.fixture
def sample_conversation_data():
    """Sample conversation data for tests."""
    return {
        "participant_from": "+15551234567",
        "participant_to": "+15559876543",
        "channel_type": "sms",
        "status": "active",
    }
