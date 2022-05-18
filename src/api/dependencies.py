from typing import AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session
from httpx_client import async_client


def get_async_client() -> httpx.AsyncClient:
    return async_client


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
