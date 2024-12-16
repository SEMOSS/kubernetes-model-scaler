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
    """
    try:
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        pod_name = socket.gethostname()
        namespace = "semoss"
        logger.info(f"Current pod name: {pod_name}, namespace: {namespace}")

        service = v1.read_namespaced_service(
            "kube-model-deployer-service-nodeport", namespace
        )
        logger.info(f"Found service type: {service.spec.type}")

        nodeport = None
        for port in service.spec.ports:
            logger.info(
                f"Checking port: {port.port}, nodePort: {getattr(port, 'node_port', None)}"
            )
            if port.port == 8000:
                nodeport = port.node_port
                logger.info(f"Found nodeport: {nodeport}")
                break

        if not nodeport:
            logger.error("Could not find nodeport in service configuration")
            return None, None

        pod = v1.read_namespaced_pod(pod_name, namespace)
        node_name = pod.spec.node_name
        logger.info(f"Pod is running on node: {node_name}")

        node = v1.read_node(node_name)

        external_ip = None
        for address in node.status.addresses:
            logger.info(
                f"Found node address - Type: {address.type}, Address: {address.address}"
            )
            if address.type == "ExternalIP":
                external_ip = address.address
                logger.info(f"Found external IP: {external_ip}")
                break

        if not external_ip:
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    external_ip = address.address
                    logger.info(
                        f"No external IP found, using internal IP: {external_ip}"
                    )
                    break

        if not external_ip:
            logger.error("Could not find any valid IP address for the node")
            return None, None

        logger.info(
            f"Successfully found node info - IP: {external_ip}, NodePort: {nodeport}"
        )
        return external_ip, nodeport

    except Exception as e:
        logger.error(f"Error getting node info: {str(e)}", exc_info=True)
        return None, None


def register_with_zookeeper() -> bool:
    """
    Register the deployment with ZK using the node's external IP and nodeport.
    """
    try:
        external_ip, nodeport = get_node_info()
        if not external_ip or not nodeport:
            logger.error("Failed to get required node information")
            return False

        logger.info(f"Connecting to ZooKeeper hosts: {ZK_HOSTS}")
        zk = KazooClient(hosts=ZK_HOSTS)
        zk.start()

        path = "/services/kube-model-deployer"
        data = f"{external_ip}:{nodeport}".encode()
        logger.info(f"Registering service at {path} with data: {data.decode()}")

        zk.ensure_path(path)
        zk.set(path, data)

        stored_data, _ = zk.get(path)
        is_registered = stored_data == data

        if is_registered:
            logger.info(
                f"Successfully registered with Zookeeper at {external_ip}:{nodeport}"
            )
        else:
            logger.error(
                f"Registration verification failed. Stored: {stored_data.decode()}"
            )

        zk.stop()
        return is_registered

    except Exception as e:
        logger.error(f"Failed to register with Zookeeper: {str(e)}", exc_info=True)
        return False
