import logging
from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class LoadBalancerMixin:

    def create_load_balancer(self):
        """
        Create a LoadBalancer service for the deployed model.
        """
        try:
            namespace = self.model_namespace
            model_name = self.model_name
            service_name = f"{model_name}-lb"

            logger.info(
                f"Creating LoadBalancer service {service_name} for model {model_name}"
            )
            core_v1_api = client.CoreV1Api()

            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(name=service_name, namespace=namespace),
                spec=client.V1ServiceSpec(
                    selector={"serving.knative.dev/service": f"{model_name}-predictor"},
                    ports=[client.V1ServicePort(port=80, target_port=8080)],
                    type="LoadBalancer",
                ),
            )

            try:
                existing_service = core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(f"Service {service_name} already exists, replacing it")
                core_v1_api.replace_namespaced_service(
                    name=service_name, namespace=namespace, body=service
                )
                logger.info(f"Replaced service {service_name} successfully")

            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Service {service_name} doesn't exist, creating it")
                    core_v1_api.create_namespaced_service(
                        namespace=namespace, body=service
                    )
                    logger.info(f"Created service {service_name} successfully")
                else:
                    raise e
            return True

        except ApiException as e:
            logger.error(f"Kubernetes API exception when creating LoadBalancer: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create LoadBalancer: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error when creating LoadBalancer: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def get_load_balancer_ip(self, wait=False, timeout=300):
        """
        Get the external IP address of the LoadBalancer service.

        Args:
            wait (bool): Whether to wait for the IP to be assigned
            timeout (int): Timeout in seconds if waiting

        Returns:
            str: External IP address or None if not available
        """
        try:
            namespace = "huggingface-models"
            service_name = f"{self.model_name}-lb"

            core_v1_api = client.CoreV1Api()

            if not wait:
                # Just check once
                service = core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                if (
                    service.status
                    and service.status.load_balancer
                    and service.status.load_balancer.ingress
                ):
                    ingress = service.status.load_balancer.ingress[0]
                    if hasattr(ingress, "ip") and ingress.ip:
                        return ingress.ip
                    elif hasattr(ingress, "hostname") and ingress.hostname:
                        return ingress.hostname

                logger.info(f"LoadBalancer {service_name} external IP not assigned yet")
                return None

            else:
                # Poll with timeout
                import time

                start_time = time.time()

                while (time.time() - start_time) < timeout:
                    service = core_v1_api.read_namespaced_service(
                        name=service_name, namespace=namespace
                    )

                    if (
                        service.status
                        and service.status.load_balancer
                        and service.status.load_balancer.ingress
                    ):
                        ingress = service.status.load_balancer.ingress[0]
                        if hasattr(ingress, "ip") and ingress.ip:
                            return ingress.ip
                        elif hasattr(ingress, "hostname") and ingress.hostname:
                            return ingress.hostname

                    logger.info(
                        f"Waiting for LoadBalancer {service_name} external IP..."
                    )
                    time.sleep(5)

                logger.warning(
                    f"Timeout waiting for LoadBalancer {service_name} external IP"
                )
                return None

        except ApiException as e:
            logger.error(f"Error getting LoadBalancer IP: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting LoadBalancer IP: {e}")
            return None

    def remove_load_balancer(self):
        """
        Remove the LoadBalancer service for the deployed model.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            namespace = self.model_namespace
            model_name = self.model_name
            service_name = f"{model_name}-lb"

            logger.info(
                f"Removing LoadBalancer service {service_name} for model {model_name}"
            )
            core_v1_api = client.CoreV1Api()

            try:
                # Check if the service exists before attempting to delete
                core_v1_api.read_namespaced_service(
                    name=service_name, namespace=namespace
                )

                # Service exists delete it
                core_v1_api.delete_namespaced_service(
                    name=service_name, namespace=namespace
                )

                logger.info(f"Successfully removed LoadBalancer service {service_name}")
                return True

            except ApiException as e:
                if e.status == 404:
                    # Service doesn't exist which is fine for removal
                    logger.info(
                        f"LoadBalancer {service_name} not found, nothing to remove"
                    )
                    return True
                else:
                    logger.error(f"Kubernetes API error when checking service: {e}")
                    raise e

        except ApiException as e:
            logger.error(f"Kubernetes API exception when removing LoadBalancer: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to remove LoadBalancer: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error when removing LoadBalancer: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
