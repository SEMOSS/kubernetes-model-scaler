import logging
from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class IngressMixin:
    """
    Mixin class to create Ingress resources for models in the autopilot cluster.
    """

    def create_ingress(
        self, host="workshop.cfg.deloitte.com", tls_secret_name="workshop-tls"
    ):
        """
        Create an Ingress resource in the autopilot cluster that points to the ExternalName service.
        Args:
            host (str): The hostname for the ingress rule
            tls_secret_name (str): The name of the TLS secret
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Switch to autopilot cluster where the Ingress should be deployed
            api_client = self.get_api_client(self.autopilot_cluster)

            namespace = self.namespace
            model_name = self.model_name
            ingress_name = f"{model_name}-ingress"
            service_name = f"{model_name}-external"
            path_prefix = f"/{model_name}"

            logger.info(f"Creating Ingress {ingress_name} in namespace {namespace}")

            networking_v1_api = client.NetworkingV1Api(api_client)

            path = client.V1HTTPIngressPath(
                path=f"{path_prefix}/(.*)",
                path_type="ImplementationSpecific",
                backend=client.V1IngressBackend(
                    service=client.V1IngressServiceBackend(
                        name=service_name, port=client.V1ServiceBackendPort(number=80)
                    )
                ),
            )

            http_rule = client.V1HTTPIngressRuleValue(paths=[path])
            rule = client.V1IngressRule(host=host, http=http_rule)
            tls = client.V1IngressTLS(hosts=[host], secret_name=tls_secret_name)
            ingress_spec = client.V1IngressSpec(
                ingress_class_name="nginx", rules=[rule], tls=[tls]
            )
            annotations = {"nginx.ingress.kubernetes.io/rewrite-target": "/$1"}

            ingress = client.V1Ingress(
                api_version="networking.k8s.io/v1",
                kind="Ingress",
                metadata=client.V1ObjectMeta(
                    name=ingress_name, namespace=namespace, annotations=annotations
                ),
                spec=ingress_spec,
            )

            try:
                # Checking if ingress already exists
                existing_ingress = networking_v1_api.read_namespaced_ingress(
                    name=ingress_name, namespace=namespace
                )

                logger.info(f"Ingress {ingress_name} already exists, replacing it")
                networking_v1_api.replace_namespaced_ingress(
                    name=ingress_name, namespace=namespace, body=ingress
                )
                logger.info(f"Replaced Ingress {ingress_name} successfully")

            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Ingress {ingress_name} doesn't exist, creating it")
                    networking_v1_api.create_namespaced_ingress(
                        namespace=namespace, body=ingress
                    )
                    logger.info(f"Created Ingress {ingress_name} successfully")
                else:
                    raise e

            return True

        except ApiException as e:
            logger.error(f"Kubernetes API exception when creating Ingress: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create Ingress: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error when creating Ingress: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def remove_ingress(self):
        """
        Remove the Ingress resource from the autopilot cluster.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Switch to autopilot cluster where the Ingress is deployed
            api_client = self.get_api_client(self.autopilot_cluster)

            namespace = self.namespace
            ingress_name = f"{self.model_name}-ingress"

            logger.info(f"Removing Ingress {ingress_name} from namespace {namespace}")

            networking_v1_api = client.NetworkingV1Api(api_client)

            try:
                # Checking if the ingress exists before attempting to delete
                networking_v1_api.read_namespaced_ingress(
                    name=ingress_name, namespace=namespace
                )

                # Ingress exists delete it
                networking_v1_api.delete_namespaced_ingress(
                    name=ingress_name, namespace=namespace
                )

                logger.info(f"Successfully removed Ingress {ingress_name}")
                return True

            except ApiException as e:
                if e.status == 404:
                    # Ingress doesn't exist which is fine for removal
                    logger.info(f"Ingress {ingress_name} not found, nothing to remove")
                    return True
                else:
                    logger.error(f"Kubernetes API error when checking ingress: {e}")
                    raise e

        except ApiException as e:
            logger.error(f"Kubernetes API exception when removing Ingress: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to remove Ingress: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error when removing Ingress: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
