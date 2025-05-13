# import logging
# import asyncio
# import aiohttp

# logger = logging.getLogger(__name__)


# class ModelLoadMixin:
#     async def perform_load_check(self):
#         try:
#             logger.info(
#                 f"Performing model load check on {self.nodeport_address}/api/model-loaded"
#             )
#             async with aiohttp.ClientSession() as session:
#                 async with session.get(
#                     f"http://{self.nodeport_address}/api/model-loaded"
#                 ) as response:
#                     model_loaded = await response.json()
#                     logger.info(model_loaded)
#                     return model_loaded
#         except aiohttp.ClientError:
#             return False
#         except Exception as e:
#             logger.error(f"Unexpected error during model load check: {str(e)}")
#             return False

#     async def check_until_model_loaded(
#         self, timeout: float = 450.0, interval: float = 3.0
#     ) -> bool:
#         """
#         Poll the model loaded endpoint until we get a True response or timeout.
#         Args:
#             timeout: Maximum time to wait in seconds
#             interval: Time between checks in seconds
#         Returns:
#             bool: True if model is loaded, False if timeout reached
#         """
#         start_time = asyncio.get_event_loop().time()

#         while (asyncio.get_event_loop().time() - start_time) < timeout:
#             if await self.perform_load_check():
#                 logger.info("Model is loaded..")
#                 return True

#             logger.info("Model is not yet loaded, waiting...")
#             await asyncio.sleep(interval)

#         logger.error(f"Model loaded check timed out after {timeout} seconds")
#         return False
