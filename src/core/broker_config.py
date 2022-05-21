from redis import asyncio as aioredis

from core.config import app_settings

redis_client = aioredis.Redis(host=app_settings.REDIS_HOST, port=6379)  # type: ignore
