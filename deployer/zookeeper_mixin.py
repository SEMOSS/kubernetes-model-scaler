import logging

logger = logging.getLogger(__name__)


class ZookeeperMixin:
    def register_warming_model(self):
        """
        Registers the model in Zookeeper under the /models/warming path.
        """
        cluster_ip = self.get_service_cluster_ip()
        if cluster_ip:
            path = f"/models/warming/{self.model_id}"
            self.kazoo_client.ensure_path(path)
            self.kazoo_client.set(path, cluster_ip.encode("utf-8"))
            logger.info(
                f"Zookeeper is tracking warming model {self.model_id}  at {path}"
            )
        else:
            logger.error(f"Could not find cluster IP for model {self.model_id}")

    def register_active_model(self):
        """
        Unregister the model from the warming state and registers the model in Zookeeper under the /models/active path.
        """
        # UNREGISTER MODEL AS WARMING
        warming_model_path = f"/models/warming/{self.model_id}"
        if self.kazoo_client.exists(warming_model_path):
            self.kazoo_client.delete(warming_model_path)
            logger.info(
                f"Zookeeper entry {warming_model_path} deleted for warming model {self.model_id}."
            )
        else:
            logger.error(
                f"Zookeeper entry {warming_model_path} not found for warming model {self.model_id}."
            )

        # REGISTER MODEL AS ACTIVE
        cluster_ip = self.get_service_cluster_ip()
        if cluster_ip:
            path = f"/models/active/{self.model_id}"
            self.kazoo_client.ensure_path(path)
            self.kazoo_client.set(path, cluster_ip.encode("utf-8"))
            logger.info(f"Zookeeper is tracking active model {self.model_id} at {path}")
        else:
            logger.error(f"Could not find cluster IP for model {self.model_id}")

    def unregister_warming_model(self):
        """
        Unregisters the model from Zookeeper under the /models/warming path.
        """
        path = f"/models/warming/{self.model_id}"
        if self.kazoo_client.exists(path):
            self.kazoo_client.delete(path)
            logger.info(f"Zookeeper entry {path} deleted.")
        else:
            logger.error(f"Zookeeper entry {path} not found.")

    def unregister_active_model(self):
        """
        Unregisters the model from Zookeeper under the /models/active path.
        """
        path = f"/models/active/{self.model_id}"
        if self.kazoo_client.exists(path):
            self.kazoo_client.delete(path)
            logger.info(f"Zookeeper entry {path} deleted.")
        else:
            logger.error(f"Zookeeper entry {path} not found.")
