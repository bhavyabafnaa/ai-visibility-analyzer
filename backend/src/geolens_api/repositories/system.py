from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SystemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def database_is_ready(self) -> None:
        await self._session.execute(text("SELECT 1"))
