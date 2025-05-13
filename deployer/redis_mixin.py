# import logging
# import pendulum
# from redis_manager.redis_manager import RedisManager

# logger = logging.getLogger(__name__)


# class RedisMixin:
#     async def update_deployment_status(self):
#         """
#         Updates the deployment status in Redis.
#         Converts all values to strings to ensure compatibility with Redis storage.
#         """
#         redis_manager = RedisManager()
#         deployment_key = f"{self.model_id}:deployment"

#         mapping = {
#             "model_name": str(self.model_name),
#             "model_repo_id": str(self.model_repo_id),
#             "model_type": str(self.model_type),
#             "semoss_id": str(self.model_id),
#             "address": str(self.address),
#             "start_time": pendulum.now("America/New_York").isoformat(),
#             "last_request": pendulum.now("America/New_York").isoformat(),
#             "generations": "0",
#             "shutdown_lock": "false",
#         }

#         try:
#             if not redis_manager.is_connected:
#                 await redis_manager.connect()

#             string_mapping = {k: str(v) for k, v in mapping.items()}
#             await redis_manager._redis.hset(deployment_key, mapping=string_mapping)
#             logger.info(f"Successfully updated deployment status for {self.model_id}")
#         except ConnectionError as e:
#             logger.error(f"Failed to connect to Redis: {e}")
#             raise
#         except Exception as e:
#             logger.error(f"Error updating deployment status in Redis: {e}")
#             raise

#     async def delete_deployment_status(self):
#         """
#         Deletes the deployment status from Redis.
#         """
#         redis_manager = RedisManager()
#         deployment_key = f"{self.model_id}:deployment"

#         try:
#             if not redis_manager.is_connected:
#                 await redis_manager.connect()

#             await redis_manager._redis.delete(deployment_key)
#             logger.info(f"Successfully deleted deployment status for {self.model_id}")
#         except ConnectionError as e:
#             logger.error(f"Failed to connect to Redis: {e}")
#             raise
#         except Exception as e:
#             logger.error(f"Error deleting deployment status from Redis: {e}")
#             raise
