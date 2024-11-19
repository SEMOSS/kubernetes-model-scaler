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
            env=[
                client.V1EnvVar(name="MODEL", value=self.model_name),
            ],
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
        )

        labels = {"model-id": self.model_id, "model-name": self.model_name}

        node_selector = {
            "cloud.google.com/gke-accelerator": "nvidia-tesla-t4",
            "cloud.google.com/gke-nodepool": "gpu-node-pool-c",
        }

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
                node_selector=node_selector,
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
        Monitors the Deployment until it reaches the desired state (all replicas are available and ready).
        Uses Kubernetes' watch API to stream events.
        """
        api_instance = client.AppsV1Api()
        w = watch.Watch()
        try:
            for event in w.stream(
                api_instance.list_namespaced_deployment,
                namespace=self.namespace,
                timeout_seconds=6000,
            ):
                deployment = event["object"]
                if deployment.metadata.name == self.model_name:
                    status = deployment.status

                    logger.info(
                        f"Deployment {self.model_name} status: "
                        f"Spec Replicas: {deployment.spec.replicas}, "
                        f"Available: {status.available_replicas}, "
                        f"Ready: {status.ready_replicas}, "
                        f"Updated: {status.updated_replicas}"
                    )

                    if status.conditions:
                        for condition in status.conditions:
                            if (
                                condition.type == "Failed"
                                and condition.status == "True"
                            ):
                                logger.error(f"Deployment failed: {condition.message}")
                                w.stop()
                                return False

                    if (
                        status.available_replicas is not None
                        and status.ready_replicas is not None
                        and deployment.spec.replicas is not None
                    ):

                        if (
                            status.available_replicas == deployment.spec.replicas
                            and status.ready_replicas == deployment.spec.replicas
                        ):

                            # Double check pod status
                            core_v1 = client.CoreV1Api()
                            pods = core_v1.list_namespaced_pod(
                                namespace=self.namespace,
                                label_selector=f"model-name={self.model_name}",
                            )

                            all_pods_ready = True
                            for pod in pods.items:
                                if pod.status.phase != "Running":
                                    all_pods_ready = False
                                    logger.info(
                                        f"Pod {pod.metadata.name} is in {pod.status.phase} state"
                                    )
                                elif pod.status.container_statuses:
                                    for container in pod.status.container_statuses:
                                        if not container.ready:
                                            all_pods_ready = False
                                            if container.state.waiting:
                                                logger.info(
                                                    f"Container {container.name} is waiting: "
                                                    f"{container.state.waiting.reason}"
                                                )

                            if all_pods_ready:
                                logger.info(f"Deployment {self.model_name} is healthy.")
                                w.stop()
                                return True
                            else:
                                logger.info("Pods are not all ready yet")

                    elif deployment.spec.replicas is None:
                        logger.error("Deployment spec replicas is None!")
                        w.stop()
                        return False

            logger.error(
                f"Watch timeout - deployment {self.model_name} did not become ready"
            )
            return False

        except ApiException as e:
            logger.error("Exception when watching deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to watch deployment")
        finally:
            w.stop()
