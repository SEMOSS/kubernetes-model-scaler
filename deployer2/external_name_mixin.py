import logging
from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ExternalNameMixin:
    """
    Mixin class to create ExternalName service resources for models.
    """

    def create_external_name_service(self):
        """
        Create an ExternalName service in the autopilot cluster that points to the
        LoadBalancer's external IP with .nip.io suffix.
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Getting the IP from the standard cluster first
            self.switch_cluster(self.standard_cluster)

            # Get the LoadBalancer IP
            external_ip = self.get_load_balancer_ip(wait=True, timeout=300)

            if not external_ip:
                logger.error("Failed to get LoadBalancer external IP")
                raise HTTPException(
                    status_code=500, detail="Failed to get LoadBalancer external IP"
                )

            external_name = f"{external_ip}.nip.io"
            logger.info(f"Using external name: {external_name}")

            # Switch to autopilot cluster to deploy resource
            self.switch_cluster(self.autopilot_cluster)

            namespace = self.namespace
            service_name = f"{self.model_name}-external"
            core_v1_api = client.CoreV1Api()
            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(name=service_name, namespace=namespace),
                spec=client.V1ServiceSpec(
                    type="ExternalName",
                    external_name=external_name,
                ),
            )

            try:
                # Checking if service already exists
                existing_service = core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(f"Service {service_name} already exists, replacing it")
                core_v1_api.replace_namespaced_service(
                    name=service_name, namespace=namespace, body=service
                )
                logger.info(
                    f"Replaced ExternalName service {service_name} successfully"
                )

            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Service {service_name} doesn't exist, creating it")
                    core_v1_api.create_namespaced_service(
                        namespace=namespace, body=service
                    )
                    logger.info(
                        f"Created ExternalName service {service_name} successfully"
                    )
                else:
                    raise e

            return True

        except ApiException as e:
            logger.error(
                f"Kubernetes API exception when creating ExternalName service: {e}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create ExternalName service: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error when creating ExternalName service: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def remove_external_name_service(self):
        """
        Remove the ExternalName service from the autopilot cluster.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Switching to autopilot cluster where the ExternalName service is deployed
            self.switch_cluster(self.autopilot_cluster)

            namespace = self.namespace
            service_name = f"{self.model_name}-external"

            logger.info(
                f"Removing ExternalName service {service_name} from namespace {namespace}"
            )

            core_v1_api = client.CoreV1Api()

            try:
                # Check if the service exists before attempting to delete
                core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                core_v1_api.delete_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(f"Successfully removed ExternalName service {service_name}")
                return True

            except ApiException as e:
                if e.status == 404:
                    # Service doesn't exist which is fine for removal
                    logger.info(
                        f"ExternalName service {service_name} not found, nothing to remove"
                    )
                    return True
                else:
                    logger.error(f"Kubernetes API error when checking service: {e}")
                    raise e

        except ApiException as e:
            logger.error(
                f"Kubernetes API exception when removing ExternalName service: {e}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to remove ExternalName service: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error when removing ExternalName service: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
