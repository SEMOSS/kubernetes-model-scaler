from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kazoo.client import KazooClient
from fastapi import HTTPException
from config.config import ZK_HOSTS, DOCKER_IMAGE, NAMESPACE, IMAGE_PULL_SECRET, DEV
import logging

logger = logging.getLogger(__name__)


class KubernetesModelDeployer:
    def __init__(
        self,
        namespace=NAMESPACE,
        zookeeper_hosts=ZK_HOSTS,
        image_pull_secret=IMAGE_PULL_SECRET,
        dev=DEV,
    ):
        logger.info(
            f"Initializing KubernetesModelDeployer with namespace={namespace}, zookeeper_hosts={zookeeper_hosts}, image_pull_secret={image_pull_secret}"
        )
        self.namespace = namespace
        self.zookeeper_hosts = zookeeper_hosts
        self.image_pull_secret = image_pull_secret
        if dev == "true":
            config.load_kube_config()
        else:
            config.load_incluster_config()
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

    def create_deployment(
        self, model_repo_name: str, model_id: str, model_name: str, pvc_name: str
    ):
        """
        Creates a Kubernetes Deployment for the given model, setting up the necessary container specifications and environment variables.
        """

        volume = client.V1Volume(
            name="model-storage",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=pvc_name
            ),
        )

        volume_mount = client.V1VolumeMount(
            name="model-storage", mount_path="/app/model_files"
        )

        container = client.V1Container(
            name=model_name,
            image=DOCKER_IMAGE,
            env=[client.V1EnvVar(name="MODEL_REPO_NAME", value=model_repo_name)],
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

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"model-id": model_id, "model-name": model_name}
            ),
            spec=client.V1PodSpec(
                containers=[container],
                volumes=[volume],
                image_pull_secrets=(
                    [client.V1LocalObjectReference(name=self.image_pull_secret)]
                    if self.image_pull_secret
                    else None
                ),
                node_selector={"cloud.google.com/gke-accelerator": "nvidia-tesla-t4"},
            ),
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={"matchLabels": {"model-id": model_id, "model-name": model_name}},
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=model_name),
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

    def create_pvc(self, pvc_name, storage_size="50Gi"):
        """
        Checks for an existing Persistent Volume Claim (PVC) with the given name. If it doesn't exist, creates a new PVC with the specified storage size.
        """
        api_instance = client.CoreV1Api()

        # check if the PVC already exists
        try:
            existing_pvc = api_instance.read_namespaced_persistent_volume_claim(
                name=pvc_name, namespace=self.namespace
            )
            logger.info(f"PVC '{pvc_name}' already exists. Using the existing PVC.")
            return existing_pvc
        except ApiException as e:
            if e.status != 404:  # If error is not "Not Found"
                logger.error(f"Exception when checking for existing PVC: {e}\n")
                # raise

        # If PVC doesn't exist create a new one
        pvc = client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=pvc_name),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": storage_size}
                ),
            ),
        )

        try:
            api_response = api_instance.create_namespaced_persistent_volume_claim(
                namespace=self.namespace, body=pvc
            )
            print(f"PVC created. status='{str(api_response.status)}'")
            return api_response
        except ApiException as e:
            print(f"Exception when creating PVC: {e}\n")
            raise

    def create_service(self, model_id: str, model_name: str):
        """
        Creates a Kubernetes Service to expose the Deployment internally within the cluster.
        """
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": model_id, "model-name": model_name},
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

    def watch_deployment(self, model_name: str):
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
                if deployment.metadata.name == model_name:
                    status = deployment.status
                    logger.info(
                        f"Deployment {model_name} status: Available Replicas: {status.available_replicas}, Ready Replicas: {status.ready_replicas}"
                    )
                    if (
                        status.available_replicas == status.replicas
                        and status.ready_replicas == status.replicas
                    ):
                        logger.info(f"Deployment {model_name} is healthy.")
                        w.stop()
                        return True
        except ApiException as e:
            logger.error("Exception when watching deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to watch deployment")
        return False

    def get_service_cluster_ip(self, model_name: str):
        """
        Retrieves the internal ClusterIP address of the Service, which is used for internal communication within the cluster.
        """
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(
                name=model_name, namespace=self.namespace
            )
            return service.spec.cluster_ip
        except ApiException as e:
            logger.error("Exception when reading service: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get service cluster IP"
            )

    def update_zookeeper(self, model_id: str, model_name: str):
        """
        Updates Zookeeper with the mapping between model_id and the Service's ClusterIP, facilitating service discovery.
        """
        cluster_ip = self.get_service_cluster_ip(model_name)
        if cluster_ip:
            path = f"/models/{model_id}"
            # self.kazoo_client.ensure_path("/models")
            self.kazoo_client.ensure_path(path)
            self.kazoo_client.set(path, cluster_ip.encode("utf-8"))
            logger.info(f"Zookeeper updated at {path} with value {cluster_ip}")

    def delete_deployment(self, model_name: str):
        """
        Deletes the Kubernetes Deployment, effectively stopping the model.
        """
        api_instance = client.AppsV1Api()
        try:
            api_instance.delete_namespaced_deployment(
                name=model_name, namespace=self.namespace, body=client.V1DeleteOptions()
            )
            logger.info(f"Deployment {model_name} deleted.")
        except ApiException as e:
            logger.error("Exception when deleting deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete deployment")

    def delete_service(self, model_name: str):
        """
        Deletes the Kubernetes Service associated with the model.
        """
        api_instance = client.CoreV1Api()
        try:
            api_instance.delete_namespaced_service(
                name=model_name, namespace=self.namespace
            )
            logger.info(f"Service {model_name} deleted.")
        except ApiException as e:
            logger.error("Exception when deleting service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete service")

    def remove_zookeeper(self, model_id: str):
        """
        Removes the Zookeeper entry for the model, cleaning up after the model is stopped.
        """
        path = f"/models/{model_id}"
        if self.kazoo_client.exists(path):
            self.kazoo_client.delete(path)
            logger.info(f"Zookeeper entry {path} deleted.")

    def get_model_name_from_id(self, model_id: str) -> str:
        """
        Given a model_id, retrieve the model_name by querying Kubernetes deployments labeled with model-id.
        """
        api_instance = client.AppsV1Api()
        try:
            deployments = api_instance.list_namespaced_deployment(
                namespace=self.namespace, label_selector=f"model-id={model_id}"
            )
            if deployments.items:
                # Assume only one deployment per model id??
                deployment = deployments.items[0]
                model_name = deployment.metadata.labels.get("model-name")
                return model_name
            else:
                logger.error(f"No deployments found with model-id {model_id}")
                raise Exception(f"No deployments found with model-id {model_id}")
        except ApiException as e:
            logger.error("Exception when listing deployments: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get model name from model id"
            )

    def get_model_id_from_name(self, model_name: str) -> str:
        """
        Given a model_name, retrieve the model_id by querying Kubernetes deployments labeled with model-name.
        """
        api_instance = client.AppsV1Api()
        try:
            deployments = api_instance.list_namespaced_deployment(
                namespace=self.namespace, label_selector=f"model-name={model_name}"
            )
            if deployments.items:
                # Assume only one deployment per model name??
                deployment = deployments.items[0]
                model_id = deployment.metadata.labels.get("model-id")
                return model_id
            else:
                logger.error(f"No deployments found with model-name {model_name}")
                raise Exception(f"No deployments found with model-name {model_name}")
        except ApiException as e:
            logger.error("Exception when listing deployments: %s\n" % e)
            raise HTTPException(
                status_code=500, detail="Failed to get model id from model name"
            )
