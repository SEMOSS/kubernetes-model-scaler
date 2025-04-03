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
            # Get API client for standard cluster to fetch LoadBalancer IP
            standard_api_client = self.get_api_client(self.standard_cluster)

            # Create CoreV1Api for standard cluster operations
            standard_core_v1_api = client.CoreV1Api(standard_api_client)

            # Get the LoadBalancer IP using the standard cluster client
            external_ip = self.get_load_balancer_ip(
                standard_core_v1_api, wait=True, timeout=300
            )

            if not external_ip:
                logger.error("Failed to get LoadBalancer external IP")
                raise HTTPException(
                    status_code=500, detail="Failed to get LoadBalancer external IP"
                )

            external_name = f"{external_ip}.nip.io"
            logger.info(f"Using external name: {external_name}")

            # Get API client for autopilot cluster to create ExternalName service
            autopilot_api_client = self.get_api_client(self.autopilot_cluster)

            # Create CoreV1Api for autopilot cluster operations
            autopilot_core_v1_api = client.CoreV1Api(autopilot_api_client)

            namespace = self.namespace
            service_name = f"{self.model_name}-external"

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
                # Checking if service already exists in autopilot cluster
                existing_service = autopilot_core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(
                    f"Service {service_name} already exists in autopilot cluster, replacing it"
                )
                autopilot_core_v1_api.replace_namespaced_service(
                    name=service_name, namespace=namespace, body=service
                )
                logger.info(
                    f"Replaced ExternalName service {service_name} successfully"
                )

            except ApiException as e:
                if e.status == 404:
                    logger.info(
                        f"Service {service_name} doesn't exist in autopilot cluster, creating it"
                    )
                    autopilot_core_v1_api.create_namespaced_service(
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
            # Get API client for autopilot cluster
            autopilot_api_client = self.get_api_client(self.autopilot_cluster)

            # Create CoreV1Api for autopilot cluster operations
            autopilot_core_v1_api = client.CoreV1Api(autopilot_api_client)

            namespace = self.namespace
            service_name = f"{self.model_name}-external"

            logger.info(
                f"Removing ExternalName service {service_name} from namespace {namespace} in autopilot cluster"
            )

            try:
                # Check if the service exists before attempting to delete
                autopilot_core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                autopilot_core_v1_api.delete_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(
                    f"Successfully removed ExternalName service {service_name} from autopilot cluster"
                )
                return True

            except ApiException as e:
                if e.status == 404:
                    # Service doesn't exist which is fine for removal
                    logger.info(
                        f"ExternalName service {service_name} not found in autopilot cluster, nothing to remove"
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
