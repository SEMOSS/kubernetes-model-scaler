import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from fastapi import HTTPException
from kazoo.client import KazooClient
from config.config import ZK_HOSTS, NAMESPACE, IMAGE_PULL_SECRET, DOCKER_IMAGE, IS_DEV
from google.cloud import storage
from typing import Optional

logger = logging.getLogger(__name__)


class BaseDeployer:
    def __init__(
        self,
        operation,
        model,
        model_id,
        model_repo_id,
        model_type,
    ):
        """All of these variables are available to each of the mixins"""
        # These are all environment variables
        self.namespace = NAMESPACE
        self.docker_image = DOCKER_IMAGE
        self.zookeeper_hosts = ZK_HOSTS
        self.image_pull_secret = IMAGE_PULL_SECRET

        self.operation = operation  # Start or stop determined by endpoint

        self.model_name = model  # The SEMOSS short name for the model
        self.model_id = model_id  # The SEMOSS UUID for the model
        self.model_repo_id = model_repo_id  # The HuggingFace model repo ID
        self.model_type = model_type  # The model type
        if IS_DEV:
            logger.info("Using dev config")
            # If you are using this locally you will need to change this to match your kubeconfig
            config.load_kube_config(context="standard")
        else:
            logger.info("Using Incluster config")
            config.load_incluster_config()

        logger.info(
            f"Initializing BaseDeployer with namespace={self.namespace}, zookeeper_hosts={self.zookeeper_hosts}, image_pull_secret={self.image_pull_secret}"
        )
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

        self.requires_download: Optional[bool] = None
        self.storage_client = storage.Client()

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
