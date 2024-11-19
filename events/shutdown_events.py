import logging
from kazoo.client import KazooClient
from config.config import ZK_HOSTS

logger = logging.getLogger(__name__)


def clean_up_zk():
    """
    Clean up the Zookeeper registration
    """
    try:
        zk = KazooClient(hosts=ZK_HOSTS)
        zk.start()

        path = "/services/kube-model-deployer"
        if zk.exists(path):
            zk.delete(path)
        zk.stop()
        logger.info("Successfully deregistered service from Zookeeper")
    except Exception as e:
        logger.error(f"Failed to deregister from Zookeeper: {str(e)}")
