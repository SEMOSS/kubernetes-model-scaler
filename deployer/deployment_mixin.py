import logging
from kubernetes import client, watch
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DeploymentMixin:

    def create_deployment(self):
        app_container = client.V1Container(
            name=self.model_name,
            image=self.docker_image,
            env=[
                client.V1EnvVar(name="MODEL", value=self.model_name),
                client.V1EnvVar(name="MODEL_REPO_ID", value=self.model_repo_id),
                client.V1EnvVar(name="MODEL_TYPE", value=self.model_type),
            ],
            ports=[client.V1ContainerPort(container_port=8888)],
            volume_mounts=[
                client.V1VolumeMount(
                    name="gcs-fuse-csi-ephemeral",
                    mount_path="/app/model_files",
                    mount_propagation="HostToContainer",
                )
            ],
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
            security_context=client.V1SecurityContext(
                privileged=True, capabilities=client.V1Capabilities(add=["SYS_ADMIN"])
            ),
        )

        # Configuring the CSI volume
        volume = client.V1Volume(
            name="gcs-fuse-csi-ephemeral",
            csi=client.V1CSIVolumeSource(
                driver="gcsfuse.csi.storage.gke.io",
                volume_attributes={
                    "bucketName": "semoss-model-files",
                    "gcsfuseLoggingSeverity": "warning",
                    "mountOptions": "implicit-dirs",
                },
            ),
        )

        labels = {"model-id": self.model_id, "model-name": self.model_name}

        node_selector = {
            "cloud.google.com/gke-accelerator": "nvidia-tesla-t4",
            "cloud.google.com/gke-nodepool": "gpu-node-pool-a",
        }

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels=labels, annotations={"gke-gcsfuse/volumes": "true"}
            ),
            spec=client.V1PodSpec(
                containers=[app_container],
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
                service_account_name="fuse-ksa",
            ),
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={"matchLabels": labels},
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
            # Add debug logging
            logger.info(
                f"Attempting to delete deployment {self.model_name} in namespace {self.namespace}"
            )

            # List deployments in namespace first
            deployments = api_instance.list_namespaced_deployment(
                namespace=self.namespace
            )
            logger.info(
                f"Current deployments in namespace {self.namespace}: {[dep.metadata.name for dep in deployments.items]}"
            )

            api_instance.delete_namespaced_deployment(
                name=self.model_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(),
            )
            logger.info(f"Deployment {self.model_name} deleted.")
        except ApiException as e:
            logger.error(
                f"Exception when deleting deployment: %s\nNamespace: {self.namespace}\nName: {self.model_name}"
                % e
            )
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
