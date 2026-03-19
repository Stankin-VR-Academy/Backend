from typing import Optional

import redis.asyncio as redis

from core.config import settings
from core.logger import logger


class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Подключение к Redis"""
        try:
            self.redis = await redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis:
            try:
                await self.redis.close()
                logger.info("Redis disconnected successfully")
            except Exception as e:
                logger.error(f"Error during Redis disconnect: {e}")

    async def ping(self) -> bool:
        """Проверка соединения с Redis"""
        if self.redis:
            return await self.redis.ping()
        return False


# Глобальный экземпляр Redis клиента
redis_client = RedisClient()
