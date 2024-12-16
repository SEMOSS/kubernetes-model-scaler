import logging
import socket
from typing import Tuple, Optional
from kazoo.client import KazooClient
from kubernetes import client, config
from config.config import ZK_HOSTS

logger = logging.getLogger(__name__)


def get_node_info() -> Tuple[Optional[str], Optional[int]]:
    """
    Get the node's external IP and nodeport for the current pod.

    Returns:
        Tuple[Optional[str], Optional[int]]: External IP and nodeport
    """
    try:
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        pod_name = socket.gethostname()
        namespace = "semoss"

        pod = v1.read_namespaced_pod(pod_name, namespace)
        node_name = pod.spec.node_name

        node = v1.read_node(node_name)

        external_ip = None
        for address in node.status.addresses:
            if address.type == "ExternalIP":
                external_ip = address.address
                break

        services = v1.list_namespaced_service(namespace)
        nodeport = None
        for svc in services.items:
            if svc.metadata.name == "kube-model-deployer-service":
                for port in svc.spec.ports:
                    if port.port == 8000:
                        nodeport = port.node_port
                        break
                break

        if not external_ip or not nodeport:
            logger.error("Failed to get node external IP or nodeport")
            return None, None

        return external_ip, nodeport

    except Exception as e:
        logger.error(f"Error getting node info: {str(e)}")
        return None, None


def register_with_zookeeper() -> bool:
    """
    Register the deployment with ZK using the node's external IP and nodeport.
    """
    try:
        external_ip, nodeport = get_node_info()
        if not external_ip or not nodeport:
            return False

        zk = KazooClient(hosts=ZK_HOSTS)
        zk.start()

        path = "/services/kube-model-deployer"
        data = f"{external_ip}:{nodeport}".encode()

        zk.ensure_path(path)
        zk.set(path, data)

        stored_data, _ = zk.get(path)
        is_registered = stored_data == data

        if is_registered:
            logger.info(
                f"Successfully registered with Zookeeper at {external_ip}:{nodeport} on path {path}"
            )
        else:
            logger.error("Registration verification failed")

        zk.stop()
        return is_registered

    except Exception as e:
        logger.error(f"Failed to register with Zookeeper: {str(e)}")
        return False
