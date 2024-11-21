import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from fastapi import HTTPException
from kazoo.client import KazooClient
from config.config import ZK_HOSTS, NAMESPACE, IMAGE_PULL_SECRET, DOCKER_IMAGE, DEV

logger = logging.getLogger(__name__)


class BaseDeployer:
    def __init__(
        self,
        operation,
        model="",
        model_id="",
        namespace=NAMESPACE,
        docker_image=DOCKER_IMAGE,
        zookeeper_hosts=ZK_HOSTS,
        image_pull_secret=IMAGE_PULL_SECRET,
        dev=DEV,
    ):
        # These are all environment variables
        self.namespace = namespace
        self.docker_image = docker_image
        self.zookeeper_hosts = zookeeper_hosts
        self.image_pull_secret = image_pull_secret
        # Operation is determined by the endpoint that calls the deployer
        self.operation = operation
        self.model_name = model
        self.model_id = model_id
        if dev == "true":
            logger.info("Using dev config")
            config.load_kube_config()
        else:
            logger.info("Using Incluster config")
            config.load_incluster_config()

        # Verify that model_id and model_name are provided for deployment
        # Resolve model_id and model_name if only one is provided for deletion operations
        self.resolve_ids()

        logger.info(
            f"Initializing BaseDeployer with namespace={namespace}, zookeeper_hosts={zookeeper_hosts}, image_pull_secret={image_pull_secret}"
        )
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

    def resolve_ids(self):
        logger.info("Resolving model ids")
        if self.operation == "deploy":
            if not self.model_id or not self.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="model_id, model_name are required for deployment",
                )
        elif self.operation == "delete":
            # For deletion, we only need model_id
            if not self.model_id and not self.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="Either model_id or model_name must be provided",
                )
            # If we don't have model_id but have name, get the id
            if not self.model_id and self.model_name:
                self.model_id = self.get_model_id_from_name(self.model_name)

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
