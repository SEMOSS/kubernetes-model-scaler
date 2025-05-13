# import logging
# import json

# logger = logging.getLogger(__name__)


# class ZookeeperMixin:
#     def _create_zk_data(self) -> bytes:
#         """
#         Creates a JSON object containing the endpoint address and model name.
#         The endpoint combines node IP and port into a single address string.
#         """
#         node_ip, node_port = self.get_service_endpoint()
#         endpoint = f"{node_ip}:{node_port}"
#         self.address = endpoint
#         data = {"ip": endpoint, "model_name": self.model_name}
#         return json.dumps(data).encode("utf-8")

#     def _get_zk_data(self, path: str) -> dict:
#         """Retrieves and parses the data stored in Zookeeper. Handles both JSON and legacy formats."""
#         try:
#             if self.kazoo_client.exists(path):
#                 data = self.kazoo_client.get(path)[0]
#                 try:
#                     return json.loads(data.decode("utf-8"))
#                 except json.JSONDecodeError:
#                     # Legacy format - just IP address
#                     ip = data.decode("utf-8").strip()
#                     logger.info(f"Found legacy format data for {path}: {ip}")
#                     return {
#                         "ip": ip,
#                         "model_name": self.model_name if self.model_name else "unknown",
#                     }
#             return None
#         except Exception as e:
#             logger.error(f"Error getting data from {path}: {str(e)}")
#             return None

#     def register_warming_model(self):
#         """
#         Registers the model in Zookeeper under the /models/warming path.
#         """
#         try:
#             path = f"/models/warming/{self.model_id}"
#             self.kazoo_client.ensure_path(path)
#             zk_data = self._create_zk_data()
#             self.kazoo_client.set(path, zk_data)
#             logger.info(
#                 f"Zookeeper is tracking warming model {self.model_id} ({self.model_name}) at {path}"
#             )
#         except Exception as e:
#             logger.error(
#                 f"Failed to register warming model {self.model_id} ({self.model_name}): {str(e)}"
#             )
#             raise

#     def register_active_model(self):
#         """
#         Unregister the model from the warming state and registers the model in Zookeeper under the /models/active path.
#         """
#         # UNREGISTER MODEL AS WARMING
#         warming_model_path = f"/models/warming/{self.model_id}"
#         if self.kazoo_client.exists(warming_model_path):
#             self.kazoo_client.delete(warming_model_path)
#             logger.info(
#                 f"Zookeeper entry {warming_model_path} deleted for warming model {self.model_id} ({self.model_name})"
#             )
#         else:
#             logger.error(
#                 f"Zookeeper entry {warming_model_path} not found for warming model {self.model_id} ({self.model_name})"
#             )

#         # REGISTER MODEL AS ACTIVE
#         try:
#             path = f"/models/active/{self.model_id}"
#             self.kazoo_client.ensure_path(path)
#             zk_data = self._create_zk_data()
#             self.kazoo_client.set(path, zk_data)
#             logger.info(
#                 f"Zookeeper is tracking active model {self.model_id} ({self.model_name}) at {path}"
#             )
#         except Exception as e:
#             logger.error(
#                 f"Failed to register active model {self.model_id} ({self.model_name}): {str(e)}"
#             )
#             raise

#     def unregister_warming_model(self):
#         """
#         Unregisters the model from Zookeeper under the /models/warming path.
#         """
#         path = f"/models/warming/{self.model_id}"
#         if self.kazoo_client.exists(path):
#             model_data = self._get_zk_data(path)
#             self.kazoo_client.delete(path)
#             logger.info(
#                 f"Zookeeper entry {path} deleted for warming model {self.model_id} ({model_data.get('model_name', self.model_name)})"
#             )
#         else:
#             logger.error(f"Zookeeper entry {path} not found")

#     def unregister_active_model(self):
#         """
#         Unregisters the model from Zookeeper under the /models/active path.
#         """
#         path = f"/models/active/{self.model_id}"
#         if self.kazoo_client.exists(path):
#             try:
#                 model_data = self._get_zk_data(path)
#                 # Even if we can't get the data, we still want to delete the node
#                 self.kazoo_client.delete(path)

#                 if model_data:
#                     logger.info(
#                         f"Zookeeper entry {path} deleted for active model {self.model_id} ({model_data.get('model_name', self.model_name)})"
#                     )
#                 else:
#                     logger.info(
#                         f"Zookeeper entry {path} deleted for active model {self.model_id}"
#                     )

#             except Exception as e:
#                 logger.error(f"Error while deleting Zookeeper entry {path}: {str(e)}")
#                 raise
#         else:
#             logger.error(f"Zookeeper entry {path} not found")
