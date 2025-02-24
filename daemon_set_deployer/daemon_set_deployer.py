import logging
import os
import yaml
from typing import List
from fastapi import APIRouter, HTTPException
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)
deploy_daemon_set_router = APIRouter()

DAEMON_SET_PATH = "resources/daemon_sets"
DAEMON_SET_FILES = ["cpu-ds.yml", "l4-ds.yml", "t4-ds.yml"]


class DaemonSetDeployer:
    def __init__(self, docker_tag: str):
        self.docker_tag = docker_tag
        image_pull_secret = os.getenv("IMAGE_PULL_SECRET")
        self.image_pull_secret = image_pull_secret
        self.base_image = "docker.semoss.org/genai/remote-client-server"
        self.full_image = f"{self.base_image}:{self.docker_tag}"

        try:
            if os.getenv("IS_DEV") == "true":
                logger.info("Using dev config")
                config.load_kube_config(context="standard")
            else:
                logger.info("Using Incluster config")
                config.load_incluster_config()

            self.apps_v1_api = client.AppsV1Api()
            logger.info("Kubernetes client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Kubernetes client: {str(e)}",
            )

    def update_daemon_set_yaml(self, file_path: str) -> dict:
        """
        Update the DaemonSet YAML file with the new Docker tag and image pull secret.
        """
        try:
            with open(file_path, "r") as file:
                daemon_set = yaml.safe_load(file)

            # Update image tag
            for container in daemon_set["spec"]["template"]["spec"]["containers"]:
                if container["name"] == "rcs-image-puller":
                    container["image"] = self.full_image
                    logger.info(f"Updated image to {self.full_image} in {file_path}")

            # Update image pull secret
            for idx, secret in enumerate(
                daemon_set["spec"]["template"]["spec"]["imagePullSecrets"]
            ):
                if "name" in secret and secret["name"] == "CHANGE-ME":
                    daemon_set["spec"]["template"]["spec"]["imagePullSecrets"][idx][
                        "name"
                    ] = self.image_pull_secret
                    logger.info(
                        f"Updated imagePullSecret to {self.image_pull_secret} in {file_path}"
                    )

            return daemon_set
        except Exception as e:
            logger.error(f"Failed to update YAML {file_path}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update YAML {file_path}: {str(e)}"
            )

    def delete_if_exists(self, daemon_set_name: str, namespace: str = "semoss") -> bool:
        """
        Delete the DaemonSet if it exists in the cluster.
        """
        try:
            self.apps_v1_api.delete_namespaced_daemon_set(
                name=daemon_set_name,
                namespace=namespace,
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground", grace_period_seconds=5
                ),
            )
            logger.info(
                f"Successfully deleted DaemonSet {daemon_set_name} in namespace {namespace}"
            )
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(
                    f"DaemonSet {daemon_set_name} not found in namespace {namespace}, nothing to delete"
                )
                return False
            else:
                logger.error(f"Failed to delete DaemonSet {daemon_set_name}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete DaemonSet {daemon_set_name}: {str(e)}",
                )

    def create_daemon_set(
        self, daemon_set_dict: dict, namespace: str = "semoss"
    ) -> str:
        """
        Create a DaemonSet in the Kubernetes cluster.
        """
        try:
            response = self.apps_v1_api.create_namespaced_daemon_set(
                namespace=namespace, body=daemon_set_dict
            )
            daemon_set_name = response.metadata.name
            logger.info(
                f"Successfully created DaemonSet {daemon_set_name} in namespace {namespace}"
            )
            return daemon_set_name
        except ApiException as e:
            logger.error(f"Failed to create DaemonSet: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create DaemonSet: {str(e)}"
            )

    def deploy_daemon_sets(self) -> List[str]:
        """
        Deploy all DaemonSets with updated tag and image pull secret.
        """
        deployed_daemon_sets = []

        for file_name in DAEMON_SET_FILES:
            file_path = os.path.join(DAEMON_SET_PATH, file_name)

            if not os.path.exists(file_path):
                logger.error(f"DaemonSet file not found: {file_path}")
                raise HTTPException(
                    status_code=404, detail=f"DaemonSet file not found: {file_path}"
                )

            daemon_set_dict = self.update_daemon_set_yaml(file_path)
            daemon_set_name = daemon_set_dict["metadata"]["name"]
            namespace = daemon_set_dict["metadata"]["namespace"]

            self.delete_if_exists(daemon_set_name, namespace)

            created_name = self.create_daemon_set(daemon_set_dict, namespace)
            deployed_daemon_sets.append(created_name)

        return deployed_daemon_sets

    def destroy_all_daemon_sets(self) -> List[str]:
        """
        Destroy all DaemonSets defined in DAEMON_SET_FILES if they exist.

        Returns:
            List[str]: Names of the DaemonSets that were successfully destroyed
        """
        destroyed_daemon_sets = []

        for file_name in DAEMON_SET_FILES:
            file_path = os.path.join(DAEMON_SET_PATH, file_name)

            if not os.path.exists(file_path):
                logger.warning(f"DaemonSet file not found: {file_path}, skipping")
                continue

            try:
                with open(file_path, "r") as file:
                    daemon_set = yaml.safe_load(file)

                daemon_set_name = daemon_set["metadata"]["name"]
                namespace = daemon_set["metadata"]["namespace"]

                is_deleted = self.delete_if_exists(daemon_set_name, namespace)

                if is_deleted:
                    destroyed_daemon_sets.append(daemon_set_name)
                    logger.info(f"Successfully destroyed DaemonSet {daemon_set_name}")
                else:
                    logger.info(
                        f"DaemonSet {daemon_set_name} not found, nothing to destroy"
                    )

            except Exception as e:
                logger.error(
                    f"Error while trying to destroy DaemonSet from {file_path}: {e}"
                )
                continue

        return destroyed_daemon_sets
