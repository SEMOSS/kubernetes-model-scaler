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
        # Load kubernetes configuration
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        # Get current pod name and log it
        pod_name = socket.gethostname()
        namespace = "semoss"
        logger.info(f"Current pod name: {pod_name}, namespace: {namespace}")

        # Get pod information
        pod = v1.read_namespaced_pod(pod_name, namespace)
        node_name = pod.spec.node_name
        logger.info(f"Pod is running on node: {node_name}")

        # Get node information and log addresses
        node = v1.read_node(node_name)
        logger.info("Node addresses:")
        for address in node.status.addresses:
            logger.info(f"  - Type: {address.type}, Address: {address.address}")

        # Get external IP from node
        external_ip = None
        for address in node.status.addresses:
            # Try ExternalIP first, fall back to InternalIP if no external IP exists
            if address.type in ["ExternalIP", "InternalIP"]:
                external_ip = address.address
                logger.info(f"Selected IP address: {address.type} - {external_ip}")
                break

        # Get nodeport from service
        services = v1.list_namespaced_service(namespace)
        nodeport = None
        logger.info("Searching for service and nodeport...")
        for svc in services.items:
            logger.info(f"Checking service: {svc.metadata.name}")
            if svc.metadata.name == "kube-model-deployer-service":
                logger.info("Found target service, checking ports:")
                if svc.spec.type != "NodePort":
                    logger.error(
                        f"Service is not of type NodePort! Current type: {svc.spec.type}"
                    )
                for port in svc.spec.ports:
                    logger.info(
                        f"  - Port: {port.port}, NodePort: {getattr(port, 'node_port', None)}"
                    )
                    if port.port == 8000:
                        nodeport = port.node_port
                        logger.info(f"Found matching nodeport: {nodeport}")
                        break
                break

        if not external_ip:
            logger.error("Failed to get node IP address")
            return None, None

        if not nodeport:
            logger.error("Failed to get nodeport")
            return None, None

        logger.info(
            f"Successfully retrieved node info - IP: {external_ip}, NodePort: {nodeport}"
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
        # Get node information
        external_ip, nodeport = get_node_info()
        if not external_ip or not nodeport:
            return False

        # Connect to ZooKeeper
        logger.info(f"Connecting to ZooKeeper hosts: {ZK_HOSTS}")
        zk = KazooClient(hosts=ZK_HOSTS)
        zk.start()

        # Create the registration data
        path = "/services/kube-model-deployer"
        data = f"{external_ip}:{nodeport}".encode()
        logger.info(f"Registering service at {path} with data: {data.decode()}")

        # Ensure path exists and set data
        zk.ensure_path(path)
        zk.set(path, data)

        # Verify registration
        stored_data, _ = zk.get(path)
        is_registered = stored_data == data

        if is_registered:
            logger.info(
                f"Successfully registered with Zookeeper at {external_ip}:{nodeport} on path {path}"
            )
        else:
            logger.error(
                f"Registration verification failed. Stored: {stored_data.decode()}, Expected: {data.decode()}"
            )

        zk.stop()
        return is_registered

    except Exception as e:
        logger.error(f"Failed to register with Zookeeper: {str(e)}", exc_info=True)
        return False
