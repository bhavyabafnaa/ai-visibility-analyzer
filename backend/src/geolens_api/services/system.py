from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.repositories.system import SystemRepository


class SystemService:
    def __init__(self, session: AsyncSession) -> None:
        self._system = SystemRepository(session)

    async def database_is_ready(self) -> bool:
        try:
            await self._system.database_is_ready()
        except SQLAlchemyError:
            return False
        return True
