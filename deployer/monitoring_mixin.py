from kubernetes import client
from kubernetes.client.rest import ApiException
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class MonitoringMixin:
    def create_podmonitoring(self):
        """
        Creates a PodMonitoring resource for the deployed model to enable metrics scraping by GMP.
        """
        custom_api = client.CustomObjectsApi()
        body = {
            "apiVersion": "monitoring.googleapis.com/v1",
            "kind": "PodMonitoring",
            "metadata": {
                "name": f"{self.model_name}-pod-monitoring",
                "namespace": self.namespace,
            },
            "spec": {
                "selector": {
                    "matchLabels": {
                        "model-name": self.model_name,
                        # "model-id": model_id,
                    }
                },
                "endpoints": [
                    {
                        "port": 8888,
                        "interval": "15s",
                    }
                ],
                "targetLabels": {"metadata": ["pod", "container"]},
            },
        }

        try:
            custom_api.create_namespaced_custom_object(
                group="monitoring.googleapis.com",
                version="v1",
                namespace=self.namespace,
                plural="podmonitorings",
                body=body,
            )
            logger.info(f"PodMonitoring '{self.model_name}-pod-monitoring' created.")
        except ApiException as e:
            if e.status == 409:
                logger.info(
                    f"PodMonitoring '{self.model_name}-pod-monitoring' already exists."
                )
            else:
                logger.error(f"Exception when creating PodMonitoring: {e}\n")
                raise HTTPException(
                    status_code=500, detail="Failed to create PodMonitoring"
                )

    def delete_podmonitoring(self):
        """
        Deletes the PodMonitoring resource associated with the model.
        """
        custom_api = client.CustomObjectsApi()
        try:
            custom_api.delete_namespaced_custom_object(
                group="monitoring.googleapis.com",
                version="v1",
                namespace=self.namespace,
                plural="podmonitorings",
                name=f"{self.model_name}-pod-monitoring",
                body=client.V1DeleteOptions(),
            )
            logger.info(f"PodMonitoring '{self.model_name}-pod-monitoring' deleted.")
        except ApiException as e:
            if e.status == 404:
                logger.info(
                    f"PodMonitoring '{self.model_name}-pod-monitoring' not found."
                )
            else:
                logger.error(f"Exception when deleting PodMonitoring: {e}\n")
                raise HTTPException(
                    status_code=500, detail="Failed to delete PodMonitoring"
                )
