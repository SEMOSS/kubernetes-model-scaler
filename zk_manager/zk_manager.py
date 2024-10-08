import logging
from kazoo.client import KazooClient
from config.config import ZK_HOSTS

logger = logging.getLogger(__name__)


class ZKManager:
    """
    This class is not being implemented by the deployer class.
    Right now this is purely for testing/admin and can be used in zk_nb.ipynb
    """

    def __init__(self, zk_hosts=ZK_HOSTS):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start()

    def register_model(self, model_id, cluster_ip):
        try:
            self.zk.create(f"/models/{model_id}", bytes(cluster_ip, "utf-8"))
            logger.info(f"Registered model {model_id} with cluster IP {cluster_ip}")
        except Exception as e:
            logger.error(
                f"Error registering model {model_id} with cluster IP {cluster_ip}: {e}"
            )

    def unregister_model(self, model_id):
        try:
            self.zk.delete(f"/models/{model_id}")
            logger.info(f"Unregistered model {model_id}")
        except Exception as e:
            logger.error(f"Error unregistering model {model_id}: {e}")

    def list_models(self):
        try:
            models = self.zk.get_children("/models")
            logger.info(f"Retrieved models: {models}")
            return models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    def stop(self):
        self.zk.stop()
