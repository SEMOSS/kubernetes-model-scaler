import logging
from kazoo.client import KazooClient
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

ZK_HOSTS = os.getenv("ZK_HOSTS")


class ZKManager:
    """
    This class is not being implemented by the deployer class.
    Right now this is purely for testing/admin and can be used in zk_nb.ipynb
    """

    def __init__(self, zk_hosts=ZK_HOSTS):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start()

    def register_warming_model(self, model_id, cluster_ip):
        try:
            self.zk.create(f"/models/warming/{model_id}", bytes(cluster_ip, "utf-8"))
            logger.info(f"Registered model {model_id} with cluster IP {cluster_ip}")
        except Exception as e:
            logger.error(
                f"Error registering model {model_id} with cluster IP {cluster_ip}: {e}"
            )
            raise

    def unregister_warming_model(self, model_id):
        try:
            self.zk.delete(f"/models/warming/{model_id}")
            logger.info(f"Unregistered model {model_id}")
        except Exception as e:
            logger.error(f"Error unregistering model {model_id}: {e}")
            raise

    def register_active_model(self, model_id, cluster_ip):
        try:
            self.zk.create(f"/models/active/{model_id}", bytes(cluster_ip, "utf-8"))
            logger.info(f"Registered model {model_id} with cluster IP {cluster_ip}")
        except Exception as e:
            logger.error(
                f"Error registering model {model_id} with cluster IP {cluster_ip}: {e}"
            )

    def unregister_active_model(self, model_id):
        try:
            self.zk.delete(f"/models/active/{model_id}")
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


if __name__ == "__main__":
    host = os.getenv("ZK_HOSTS")
    print(host)
    zk = ZKManager()
    models = zk.list_models()
    print(models)
