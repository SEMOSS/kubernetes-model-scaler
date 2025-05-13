import logging
import json
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class ZookeeperMixin:
    def get_inference_service_endpoint(self):
        """
        Get the endpoint information from the KServe InferenceService.

        Returns:
            tuple: (host, port) for the InferenceService
        """
        try:
            namespace = self.model_namespace
            model_name = self.model_name

            # Get the InferenceService status to extract endpoints
            custom_api = client.CustomObjectsApi()

            # KServe API version and kind
            group = "serving.kserve.io"
            version = "v1beta1"
            plural = "inferenceservices"

            try:
                inference_service = custom_api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=model_name,
                )

                # Extract URL from status
                if (
                    "status" in inference_service
                    and "url" in inference_service["status"]
                ):
                    url = inference_service["status"]["url"]
                    logger.info(f"Found InferenceService URL: {url}")

                    # Parse URL to get host and port
                    # URL format is typically http://model-name.namespace.svc.cluster.local
                    import urllib.parse

                    parsed_url = urllib.parse.urlparse(url)
                    host = parsed_url.hostname
                    port = parsed_url.port or 80  # Default to 80 if port not specified

                    logger.info(f"Extracted host: {host}, port: {port}")
                    return host, port

                # If LoadBalancer is used, get its IP instead
                if self.get_load_balancer_ip():
                    lb_ip = self.get_load_balancer_ip()
                    return lb_ip, 80

                logger.error(
                    f"InferenceService {model_name} does not have URL in status"
                )
                return None, None

            except ApiException as e:
                logger.error(f"Failed to get InferenceService {model_name}: {e}")
                return None, None

        except Exception as e:
            logger.error(f"Unexpected error getting InferenceService endpoint: {e}")
            return None, None

    def _create_zk_data(self, stage: str) -> bytes:
        """
        Creates a JSON object containing the endpoint address and model name.
        For KServe, we use the LoadBalancer IP for cross-cluster communication.
        Raises an exception if no cross-cluster compatible endpoint is available.
        """
        if stage == "active":
            lb_ip = self.get_load_balancer_ip(wait=True, timeout=180)

            if not lb_ip:
                error_msg = f"No LoadBalancer IP found for model {self.model_name}. Cannot register model for cross-cluster access."
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            endpoint = f"{lb_ip}:80"
            logger.info(f"Using LoadBalancer endpoint for ZooKeeper: {endpoint}")

            self.address = endpoint
        elif stage == "warming":
            endpoint = "WARMING"
        elif stage == "cooling":
            endpoint = "COOLING"
        else:
            raise ValueError(f"Invalid stage: {stage}")

        data = {
            "ip": endpoint,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "model_repo_id": self.model_repo_id,
            "deployment_type": "kserve",
        }

        return json.dumps(data).encode("utf-8")

    def _get_zk_data(self, path: str) -> dict:
        """Retrieves and parses the data stored in Zookeeper. Handles both JSON and legacy formats."""
        try:
            if self.kazoo_client.exists(path):
                data = self.kazoo_client.get(path)[0]
                try:
                    return json.loads(data.decode("utf-8"))
                except json.JSONDecodeError:
                    # Legacy format - just IP address
                    ip = data.decode("utf-8").strip()
                    logger.info(f"Found legacy format data for {path}: {ip}")
                    return {
                        "ip": ip,
                        "model_name": (
                            self.model_name
                            if hasattr(self, "model_name")
                            else "unknown"
                        ),
                        "deployment_type": "legacy",
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting data from {path}: {str(e)}")
            return None

    def register_warming_model(self):
        """
        Registers the model in Zookeeper under the /models/warming path.
        """
        try:
            path = f"/models/warming/{self.model_id}"
            self.kazoo_client.ensure_path(path)
            zk_data = self._create_zk_data("warming")
            self.kazoo_client.set(path, zk_data)
            logger.info(
                f"Zookeeper is tracking warming model {self.model_id} ({self.model_name}) at {path}"
            )
        except Exception as e:
            logger.error(
                f"Failed to register warming model {self.model_id} ({self.model_name}): {str(e)}"
            )
            raise

    def register_active_model(self):
        """
        Unregister the model from the warming state and registers the model in Zookeeper under the /models/active path.
        """
        # UNREGISTER MODEL AS WARMING
        warming_model_path = f"/models/warming/{self.model_id}"
        if self.kazoo_client.exists(warming_model_path):
            self.kazoo_client.delete(warming_model_path)
            logger.info(
                f"Zookeeper entry {warming_model_path} deleted for warming model {self.model_id} ({self.model_name})"
            )
        else:
            logger.info(
                f"Zookeeper entry {warming_model_path} not found for warming model {self.model_id} ({self.model_name})"
            )

        # REGISTER MODEL AS ACTIVE
        try:
            path = f"/models/active/{self.model_id}"
            self.kazoo_client.ensure_path(path)
            zk_data = self._create_zk_data("active")
            self.kazoo_client.set(path, zk_data)
            logger.info(
                f"Zookeeper is tracking active model {self.model_id} ({self.model_name}) at {path}"
            )
        except Exception as e:
            logger.error(
                f"Failed to register active model {self.model_id} ({self.model_name}): {str(e)}"
            )
            raise

    def unregister_warming_model(self):
        """
        Unregisters the model from Zookeeper under the /models/warming path.
        """
        path = f"/models/warming/{self.model_id}"
        if self.kazoo_client.exists(path):
            model_data = self._get_zk_data(path)
            self.kazoo_client.delete(path)
            logger.info(
                f"Zookeeper entry {path} deleted for warming model {self.model_id} ({model_data.get('model_name', self.model_name)})"
            )
        else:
            logger.info(f"Zookeeper entry {path} not found")

    def unregister_active_model(self):
        """
        Unregisters the model from Zookeeper under the /models/active path.
        """
        path = f"/models/active/{self.model_id}"
        if self.kazoo_client.exists(path):
            try:
                model_data = self._get_zk_data(path)
                # Even if we can't get the data, we still want to delete the node
                self.kazoo_client.delete(path)

                if model_data:
                    logger.info(
                        f"Zookeeper entry {path} deleted for active model {self.model_id} ({model_data.get('model_name', self.model_name)})"
                    )
                else:
                    logger.info(
                        f"Zookeeper entry {path} deleted for active model {self.model_id}"
                    )

            except Exception as e:
                logger.error(f"Error while deleting Zookeeper entry {path}: {str(e)}")
                raise
        else:
            logger.info(f"Zookeeper entry {path} not found")

    def register_cooling_model(self):
        """
        Determines the current state of the model and registers it as cooling.
        Stores the original state for potential recovery.
        Returns: The original state of the model ("active", "warming", or None)
        """
        try:
            # Check if the model exists in either active or warming paths
            active_path = f"/models/active/{self.model_id}"
            warming_path = f"/models/warming/{self.model_id}"

            # Store original state and data for recovery if needed
            self.original_state = None
            self.original_data = None

            if self.kazoo_client.exists(active_path):
                self.original_state = "active"
                self.original_data = self.kazoo_client.get(active_path)[0]
                logger.info(
                    f"Found model {self.model_id} in active state, storing for recovery"
                )
            elif self.kazoo_client.exists(warming_path):
                self.original_state = "warming"
                self.original_data = self.kazoo_client.get(warming_path)[0]
                logger.info(
                    f"Found model {self.model_id} in warming state, storing for recovery"
                )
            else:
                logger.info(
                    f"Model {self.model_id} not found in active or warming state"
                )

            # Create cooling path
            cooling_path = f"/models/cooling/{self.model_id}"
            self.kazoo_client.ensure_path(cooling_path)
            zk_data = self._create_zk_data("cooling")
            self.kazoo_client.set(cooling_path, zk_data)
            logger.info(
                f"Zookeeper is tracking cooling model {self.model_id} ({self.model_name}) at {cooling_path}"
            )

            return self.original_state
        except Exception as e:
            logger.error(
                f"Failed to register cooling model {self.model_id} ({self.model_name}): {str(e)}"
            )
            raise

    def unregister_cooling_model(self):
        """
        Unregisters the model from Zookeeper under the /models/cooling path.
        """
        path = f"/models/cooling/{self.model_id}"
        if self.kazoo_client.exists(path):
            model_data = self._get_zk_data(path)
            self.kazoo_client.delete(path)
            logger.info(
                f"Zookeeper entry {path} deleted for cooling model {self.model_id} ({model_data.get('model_name', self.model_name) if model_data else self.model_name})"
            )
        else:
            logger.info(f"Zookeeper entry {path} not found")

    def restore_original_state(self):
        """
        Restores the model to its original state if an operation fails.
        Returns: True if restoration succeeded, False otherwise
        """
        if (
            not hasattr(self, "original_state")
            or not self.original_state
            or not self.original_data
        ):
            logger.info(f"No original state found for model {self.model_id} to restore")
            return False

        # First remove from cooling path
        self.unregister_cooling_model()

        # Restore to original state
        try:
            if self.original_state == "active":
                path = f"/models/active/{self.model_id}"
                self.kazoo_client.ensure_path(path)
                self.kazoo_client.set(path, self.original_data)
                logger.info(f"Restored model {self.model_id} to active state")
            elif self.original_state == "warming":
                path = f"/models/warming/{self.model_id}"
                self.kazoo_client.ensure_path(path)
                self.kazoo_client.set(path, self.original_data)
                logger.info(f"Restored model {self.model_id} to warming state")

            return True
        except Exception as e:
            logger.error(
                f"Failed to restore model {self.model_id} to original state: {str(e)}"
            )
            return False

    def get_model_endpoint(self, model_id):
        """
        Gets the endpoint for a specific model by its ID.

        Args:
            model_id (str): The model ID to look up

        Returns:
            dict: Model data including endpoint or None if not found
        """
        path = f"/models/active/{model_id}"
        return self._get_zk_data(path)
