import logging
import os
import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DeploymentMixin:

    def apply_yaml(self):
        try:
            namespace = self.model_namespace
            yaml_path = self.resources_path / f"{self.model_name}.yaml"

            if not os.path.exists(yaml_path):
                raise FileNotFoundError(f"YAML file {yaml_path} not found")

            with open(yaml_path, "r") as file:
                resource_dict = yaml.safe_load(file)

            api_version = resource_dict.get("apiVersion")
            kind = resource_dict.get("kind")

            logger.info(f"Deploying {api_version}/{kind} for model {self.model_name}")

            custom_api = client.CustomObjectsApi()

            if "/" in api_version:
                group, version = api_version.split("/")
            else:
                group, version = "", api_version

            name = resource_dict.get("metadata", {}).get("name")

            try:
                existing_resource = custom_api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=self._get_plural_name(kind).lower(),
                    name=name,
                )

                logger.info(f"Resource {kind}/{name} already exists, patching it")
                custom_api.patch_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=self._get_plural_name(kind).lower(),
                    name=name,
                    body=resource_dict,
                    _content_type="application/strategic-merge-patch+json",
                )
                logger.info(f"Patched {kind}/{name} successfully")
            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Resource {kind}/{name} doesn't exist, creating it")
                    custom_api.create_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=self._get_plural_name(kind).lower(),
                        body=resource_dict,
                    )
                    logger.info(f"Created {kind}/{name} successfully")
                else:
                    raise e

            return True
        except ApiException as e:
            logger.error(f"Kubernetes API exception when applying YAML: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to apply YAML: {str(e)}"
            )
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {yaml_path}: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error when applying YAML: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def _get_plural_name(self, kind):
        """Convert CRD kind to plural form for API calls"""
        plural_map = {
            "InferenceService": "inferenceservices",
        }
        return plural_map.get(kind, f"{kind.lower()}s")

    def remove_inference_service(self):
        """
        Remove the InferenceService resource for the model.
        Equivalent to 'kubectl delete inferenceservice <model_name> -n <namespace>'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            namespace = self.model_namespace
            model_name = self.model_name

            logger.info(
                f"Removing InferenceService {model_name} from namespace {namespace}"
            )

            custom_api = client.CustomObjectsApi()

            api_version = "serving.kserve.io/v1beta1"
            kind = "InferenceService"
            plural = self._get_plural_name(kind).lower()

            # Split API version into group and version
            if "/" in api_version:
                group, version = api_version.split("/")
            else:
                group, version = "", api_version

            try:
                # Check if the resource exists before attempting to delete
                custom_api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=model_name,
                )

                # Resource exists delete it
                custom_api.delete_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=model_name,
                )

                logger.info(f"Successfully removed InferenceService {model_name}")
                return True

            except ApiException as e:
                if e.status == 404:
                    # Resource doesn't exist which is fine for removal
                    logger.info(
                        f"InferenceService {model_name} not found, nothing to remove"
                    )
                    return True
                else:
                    logger.error(
                        f"Kubernetes API error when checking InferenceService: {e}"
                    )
                    raise e

        except ApiException as e:
            logger.error(
                f"Kubernetes API exception when removing InferenceService: {e}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to remove InferenceService: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error when removing InferenceService: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
