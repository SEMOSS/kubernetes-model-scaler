import os
import json
import logging
from typing import Dict, List
from datetime import datetime
from kazoo.client import KazooClient
from kazoo.exceptions import KazooException, NoNodeError


class ZKManager:
    """
    Singleton class to manage ZooKeeper operations for the Kubernetes Model Service.
    Handles model data retrieval, deletion, and service discovery.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger(__name__)
            self.zk_hosts = os.getenv("ZK_HOSTS")
            self.zk_client = None
            self._initialized = True
            self._connect()

    def _connect(self) -> None:
        """Establish connection to ZooKeeper"""
        try:
            self.zk_client = KazooClient(hosts=self.zk_hosts)
            self.zk_client.start()
            self.logger.info(f"Connected to ZooKeeper at {self.zk_hosts}")
        except Exception as e:
            self.logger.error(f"Failed to connect to ZooKeeper: {e}")
            raise

    def _ensure_connected(self) -> None:
        """Ensure ZooKeeper connection is active"""
        if not self.zk_client or not self.zk_client.connected:
            self._connect()

    def get_model_info(self, path: str) -> List[Dict]:
        """
        Retrieve model information from a specific ZooKeeper path.
        Args:
            path: ZooKeeper path to check (e.g., "/models/warming" or "/models/active")
        Returns:
            List of dictionaries containing model information
        """
        self._ensure_connected()
        models = []
        try:
            if not self.zk_client.exists(path):
                self.logger.warning(f"Path {path} does not exist")
                return models

            model_ids = self.zk_client.get_children(path)
            for model_id in model_ids:
                full_path = f"{path}/{model_id}"
                try:
                    data, stat = self.zk_client.get(full_path)
                    try:
                        model_data = json.loads(data.decode("utf-8"))
                        models.append(
                            {
                                "model_id": model_id,
                                "model_name": model_data.get(
                                    "model_name", "Unknown Model"
                                ),
                                "cluster_ip": model_data.get("ip", "N/A"),
                                "status": "active" if "active" in path else "warming",
                                "last_updated": datetime.fromtimestamp(
                                    stat.mtime / 1000
                                ).isoformat(),
                                "metadata": model_data,
                            }
                        )
                    except json.JSONDecodeError:
                        # Handle legacy format
                        models.append(
                            {
                                "model_id": model_id,
                                "model_name": "Unknown Model",
                                "cluster_ip": data.decode("utf-8"),
                                "status": "active" if "active" in path else "warming",
                                "last_updated": datetime.fromtimestamp(
                                    stat.mtime / 1000
                                ).isoformat(),
                            }
                        )
                except NoNodeError:
                    self.logger.warning(
                        f"Node {full_path} was deleted during retrieval"
                    )
                    continue

        except KazooException as e:
            self.logger.error(f"Error retrieving models from {path}: {e}")
            raise

        return models

    def get_all_models(self) -> Dict[str, List[Dict]]:
        """
        Retrieve all models from both warming and active paths.
        Returns:
            Dictionary with 'warming' and 'active' keys containing model lists
        """
        return {
            "warming": self.get_model_info("/models/warming"),
            "active": self.get_model_info("/models/active"),
        }

    def delete_model(self, model_id: str, status: str) -> bool:
        """
        Delete a model from ZooKeeper.
        Args:
            model_id: ID of the model to delete
            status: Status path ('warming' or 'active')
        Returns:
            bool: True if deletion was successful
        """
        self._ensure_connected()
        path = f"/models/{status}/{model_id}"

        try:
            if self.zk_client.exists(path):
                self.zk_client.delete(path)
                self.logger.info(f"Successfully deleted model {model_id} from {status}")
                return True
            else:
                self.logger.warning(f"Model {model_id} not found in {status}")
                return False
        except KazooException as e:
            self.logger.error(f"Error deleting model {model_id}: {e}")
            return False

    def get_deployer_status(self) -> Dict:
        """
        Get the status of the model deployer service.
        Returns:
            Dictionary containing deployer status information
        """
        self._ensure_connected()
        deployer_path = "/services/kube-model-deployer"

        try:
            if self.zk_client.exists(deployer_path):
                data, stat = self.zk_client.get(deployer_path)
                return {
                    "status": "active",
                    "ip_address": data.decode("utf-8"),
                    "last_updated": datetime.fromtimestamp(
                        stat.mtime / 1000
                    ).isoformat(),
                }
            return {"status": "not_found", "ip_address": None, "last_updated": None}
        except KazooException as e:
            self.logger.error(f"Error getting deployer status: {e}")
            return {"status": "error", "ip_address": None, "last_updated": None}

    def close(self) -> None:
        """Close ZooKeeper connection"""
        if self.zk_client:
            self.zk_client.stop()
            self.zk_client = None
            self._initialized = False
            self.logger.info("ZooKeeper connection closed")

    def __del__(self):
        """Ensure connection is closed on deletion"""
        self.close()
