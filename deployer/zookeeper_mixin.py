import logging

logger = logging.getLogger(__name__)


class ZookeeperMixin:
    def update_zookeeper(self):
        """
        Updates Zookeeper with the mapping between model_id and the Service's ClusterIP, facilitating service discovery.
        """
        cluster_ip = self.get_service_cluster_ip()
        if cluster_ip:
            path = f"/models/{self.model_id}"
            # self.kazoo_client.ensure_path("/models")
            self.kazoo_client.ensure_path(path)
            self.kazoo_client.set(path, cluster_ip.encode("utf-8"))
            logger.info(f"Zookeeper updated at {path} with value {cluster_ip}")

    def remove_zookeeper(self):
        """
        Removes the Zookeeper entry for the model, cleaning up after the model is stopped.
        """
        path = f"/models/{self.model_id}"
        if self.kazoo_client.exists(path):
            self.kazoo_client.delete(path)
            logger.info(f"Zookeeper entry {path} deleted.")
