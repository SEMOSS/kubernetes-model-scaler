from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class ServiceMixin:
    def create_service(self, node_port=None):
        """Creates a Kubernetes Service to expose the Deployment externally via NodePort."""
        service_port = client.V1ServicePort(
            port=8888, target_port=8888, node_port=node_port
        )

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=self.model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": self.model_id, "model-name": self.model_name},
                ports=[service_port],
                type="NodePort",
            ),
        )

        api_instance = client.CoreV1Api()
        try:
            api_response = api_instance.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            logger.info("Service created. status='%s'" % str(api_response.status))

            node_ip, node_port = self.get_service_endpoint()
            self.nodeport_address = f"{node_ip}:{node_port}"
            logger.info(f"Stored nodeport address: {self.nodeport_address}")
        except ApiException as e:
            logger.error("Exception when creating service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to create service")

    def get_service_endpoint(self):
        """
        Retrieves the endpoint for accessing the service via NodePort.
        This includes getting one of the node IPs and the assigned node port.
        """
        api_instance = client.CoreV1Api()
        try:
            # Get the service to get the node port
            service = api_instance.read_namespaced_service(
                name=self.model_name, namespace=self.namespace
            )
            node_port = service.spec.ports[0].node_port

            # Get list of nodes to get an external IP
            nodes = api_instance.list_node()
            node_ip = None

            # Try to get external IP first
            for node in nodes.items:
                for addr in node.status.addresses:
                    if addr.type == "ExternalIP":
                        node_ip = addr.address
                        break
                if node_ip:
                    break

            # If no external IP, fall back to internal IP
            if not node_ip:
                for node in nodes.items:
                    for addr in node.status.addresses:
                        if addr.type == "InternalIP":
                            node_ip = addr.address
                            break
                    if node_ip:
                        break

            if not node_ip:
                raise HTTPException(
                    status_code=500, detail="Could not find any node IP addresses"
                )

            return (node_ip, node_port)
        except ApiException as e:
            logger.error("Exception when getting service endpoint: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get service endpoint"
            )

    def delete_service(self):
        """
        Deletes the Kubernetes Service associated with the model.
        """
        api_instance = client.CoreV1Api()
        try:
            api_instance.delete_namespaced_service(
                name=self.model_name, namespace=self.namespace
            )
            logger.info(f"Service {self.model_name} deleted.")
        except ApiException as e:
            logger.error("Exception when deleting service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete service")

    def get_service_node_port(self):
        """
        Retrieves the NodePort number assigned to the service.

        Returns:
            int: The node port number assigned to the service.
        """
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(
                name=self.model_name, namespace=self.namespace
            )
            return service.spec.ports[0].node_port
        except ApiException as e:
            logger.error("Exception when reading service: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get service node port"
            )

    def get_service_cluster_ip(self):
        """
        Retrieves the internal ClusterIP address of the Service, which is used for internal communication within the cluster.
        """
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(
                name=self.model_name, namespace=self.namespace
            )
            return service.spec.cluster_ip
        except ApiException as e:
            logger.error("Exception when reading service: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get service cluster IP"
            )
