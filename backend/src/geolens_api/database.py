from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from geolens_api.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url_string,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one database session for an HTTP request."""
    async with async_session_factory() as session:
        yield session
