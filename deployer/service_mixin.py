from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class ServiceMixin:
    def create_service(self):
        """
        Creates a Kubernetes Service to expose the Deployment internally within the cluster.
        """
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=self.model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": self.model_id, "model-name": self.model_name},
                ports=[client.V1ServicePort(port=8888, target_port=8888)],
                type="ClusterIP",
            ),
        )

        api_instance = client.CoreV1Api()
        try:
            api_response = api_instance.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            logger.info("Service created. status='%s'" % str(api_response.status))
        except ApiException as e:
            logger.error("Exception when creating service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to create service")

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
