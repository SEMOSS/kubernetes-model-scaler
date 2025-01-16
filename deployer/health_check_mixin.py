import logging
import asyncio
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class HealthCheckMixin:
    async def perform_health_check(self):
        try:
            logger.info(
                f"Performing health check on {self.nodeport_address}/api/health"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.nodeport_address}/api/health"
                ) as response:
                    return response.status == 200
        except aiohttp.ClientError:
            return False
        except Exception as e:
            logger.error(f"Unexpected error during health check: {str(e)}")
            return False

    async def check_until_healthy(
        self, timeout: Optional[float] = None, interval: float = 3.0
    ) -> bool:
        """
        Poll the health endpoint until we get a 200 response or timeout.
        Args:
            timeout: Maximum time to wait in seconds (if None, determined automatically)
            interval: Time between checks in seconds
        Returns:
            bool: True if service became healthy, False if timeout reached
        """
        if timeout is None:
            timeout = self.get_health_check_timeout()

        start_time = asyncio.get_event_loop().time()

        logger.info(f"Starting health check with timeout of {timeout} seconds")
        if self.requires_download:
            logger.info(
                f"Extended timeout in use as model {self.model_name} requires download"
            )

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if await self.perform_health_check():
                logger.info("Container is healthy")
                return True

            logger.info("Container not yet healthy, waiting...")
            await asyncio.sleep(interval)

        logger.error(f"Health check timed out after {timeout} seconds")
        return False
