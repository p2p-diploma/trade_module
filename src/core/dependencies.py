from functools import lru_cache
from typing import AsyncGenerator

import httpx
import jwt
from fastapi import Depends, HTTPException
from httpx import AsyncClient
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.requests import Request

from core import broker_config
from core.config import app_settings
from db.session import async_session
from httpx_client import async_client


def get_async_client() -> httpx.AsyncClient:
    return async_client


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def get_current_user(request: Request) -> dict:
    unauthorized_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    raw_jwt = request.cookies.get("jwt-access")

    if raw_jwt is None:
        raise unauthorized_exc
    try:
        payload = jwt.decode(
            raw_jwt,
            app_settings.SECRET_KEY,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as e:
        raise unauthorized_exc from e

    return payload


async def get_current_user_wallet(
    request: Request,
    client: AsyncClient = Depends(get_async_client),
) -> tuple[str, str]:
    # user_data = get_current_user(request)
    # response = await client.get(
    #     urljoin(
    #         app_settings.CRYPTO_SERVICE_API,
    #         f"/wallets/ethereum/email/{user_data['email']}/p2p",
    #     ),
    # )
    # response.raise_for_status()
    #
    # response_data = response.json()
    response_data = {"id": "hello", "address": "someaddress"}

    return response_data["id"], response_data["address"]


@lru_cache
def get_redis() -> aioredis.Redis:
    return broker_config.redis_client