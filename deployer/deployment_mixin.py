import logging
from kubernetes import client, watch
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DeploymentMixin:
    def create_deployment(self):
        """
        Creates a Kubernetes Deployment for the given model, setting up the necessary container specifications and environment variables.
        """

        volume = client.V1Volume(
            name="model-storage",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=f"filestore-cfg-pv-rwm"
            ),
        )

        volume_mount = client.V1VolumeMount(
            name="model-storage", mount_path="/app/model_files"
        )

        container = client.V1Container(
            name=self.model_name,
            image=self.docker_image,
            env=[client.V1EnvVar(name="MODEL_REPO_NAME", value=self.model_repo_name)],
            ports=[client.V1ContainerPort(container_port=8888)],
            volume_mounts=[volume_mount],
            resources=client.V1ResourceRequirements(
                limits={
                    "nvidia.com/gpu": "1",
                    "cpu": "4",
                    "memory": "16Gi",
                },
                requests={
                    "nvidia.com/gpu": "1",
                    "cpu": "4",
                    "memory": "16Gi",
                },
            ),
            command=["/bin/bash", "-c"],
            args=["-e", f"MODEL={self.model_name}"],
        )

        labels = {"model-id": self.model_id, "model-name": self.model_name}

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=labels),
            spec=client.V1PodSpec(
                containers=[container],
                volumes=[volume],
                image_pull_secrets=(
                    [client.V1LocalObjectReference(name=self.image_pull_secret)]
                    if self.image_pull_secret
                    else None
                ),
                node_selector={"cloud.google.com/gke-accelerator": "nvidia-tesla-t4"},
                tolerations=[
                    client.V1Toleration(
                        key="nvidia.com/gpu", operator="Exists", effect="NoSchedule"
                    )
                ],
            ),
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={
                "matchLabels": {
                    "model-id": self.model_id,
                    "model-name": self.model_name,
                }
            },
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=self.model_name, labels=labels),
            spec=spec,
        )

        api_instance = client.AppsV1Api()
        try:
            api_response = api_instance.create_namespaced_deployment(
                namespace=self.namespace, body=deployment
            )
            logger.info("Deployment created. status='%s'" % str(api_response.status))
        except ApiException as e:
            logger.error("Exception when creating deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to create deployment")

    def delete_deployment(self):
        """
        Deletes the Kubernetes Deployment, effectively stopping the model.
        """
        api_instance = client.AppsV1Api()
        try:
            api_instance.delete_namespaced_deployment(
                name=self.model_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(),
            )
            logger.info(f"Deployment {self.model_name} deleted.")
        except ApiException as e:
            logger.error("Exception when deleting deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete deployment")

    def watch_deployment(self):
        """
        Monitors the Deployment until it reaches the desired state (all replicas are available and ready). Uses Kubernetes' watch API to stream events.
        """
        api_instance = client.AppsV1Api()
        w = watch.Watch()
        try:
            for event in w.stream(
                api_instance.list_namespaced_deployment,
                namespace=self.namespace,
                timeout_seconds=600,
            ):
                deployment = event["object"]
                if deployment.metadata.name == self.model_name:
                    status = deployment.status
                    logger.info(
                        f"Deployment {self.model_name} status: Available Replicas: {status.available_replicas}, Ready Replicas: {status.ready_replicas}"
                    )
                    if (
                        status.available_replicas == status.replicas
                        and status.ready_replicas == status.replicas
                    ):
                        logger.info(f"Deployment {self.model_name} is healthy.")
                        w.stop()
                        return True
        except ApiException as e:
            logger.error("Exception when watching deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to watch deployment")
        return False
