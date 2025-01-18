from redis import asyncio as aioredis
import logging
import os
from typing import Optional


class RedisManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not RedisManager._initialized:
            self._redis: Optional[aioredis.Redis] = None
            self._host = os.getenv("REDIS_HOST", "redis.semoss.svc.cluster.local")
            self._port = int(os.getenv("REDIS_PORT", "6379"))
            self.logger = logging.getLogger(__name__)
            RedisManager._initialized = True

    async def connect(self) -> None:
        if self._redis is not None:
            self.logger.warning("Redis connection already exists")
            return

        try:
            self.logger.info(f"Connecting to Redis at {self._host}:{self._port}")
            self._redis = await aioredis.from_url(
                f"redis://{self._host}:{self._port}",
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self._redis.ping()
            self.logger.info("Successfully connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            self._redis = None
            raise ConnectionError(f"Could not connect to Redis: {str(e)}")

    async def disconnect(self) -> None:
        if self._redis is not None:
            try:
                self.logger.info("Closing Redis connection")
                await self._redis.aclose()
                self.logger.info("Redis connection closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing Redis connection: {str(e)}")
            finally:
                self._redis = None
                RedisManager._initialized = False

    @property
    def is_connected(self) -> bool:
        return self._redis is not None and self._redis.connection is not None

    async def update_model_lock(self, model_id: str, lock: str) -> None:
        deployment_key = f"{model_id}:deployment"

        if not self.is_connected:
            await self.connect()

        try:
            if not await self._redis.exists(deployment_key):
                raise KeyError(f"No deployment found for model {model_id}")

            await self._redis.hset(deployment_key, "shutdown_lock", lock)
            self.logger.info(
                f"Successfully updated shutdown_lock to {lock} for model {model_id}"
            )
        except ConnectionError as e:
            self.logger.error(
                f"Failed to connect to Redis while updating model lock: {e}"
            )
            raise
        except Exception as e:
            self.logger.error(f"Error updating model lock in Redis: {e}")
            raise
