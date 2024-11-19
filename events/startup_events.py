import logging
import socket
from kazoo.client import KazooClient
from config.config import ZK_HOSTS

logger = logging.getLogger(__name__)


def register_with_zookeeper() -> bool:
    """
    Registering the deployment with ZK so that other services know where to find it.
    """
    try:
        zk = KazooClient(hosts=ZK_HOSTS)
        zk.start()

        service_ip = socket.gethostbyname(
            "kube-model-deployer-service.semoss.svc.cluster.local"
        )

        path = "/services/kube-model-deployer"
        data = f"{service_ip}:8000".encode()

        zk.ensure_path(path)
        zk.set(path, data)

        # Verifying the registration
        stored_data, _ = zk.get(path)
        is_registered = stored_data == data

        if is_registered:
            logger.info(
                f"Successfully registered with Zookeeper at {service_ip}:8000 on path {path}"
            )
        else:
            logger.error("Registration verification failed")

        zk.stop()
        return is_registered

    except Exception as e:
        logger.error(f"Failed to register with Zookeeper: {str(e)}")
        return False
