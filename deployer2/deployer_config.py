import logging
import pathlib
import os
from kubernetes import config
from kazoo.client import KazooClient
from config.config import (
    ZK_HOSTS,
    NAMESPACE,
    IMAGE_PULL_SECRET,
    DOCKER_IMAGE,
    IS_DEV,
    MODEL_NAMESPACE,
    STANDARD_CLUSTER,
    AUTOPILOT_CLUSTER,
    KUBECONFIG_PATH,
)
from cloud import get_cloud_manager

logger = logging.getLogger(__name__)


class DeployerConfig:
    def __init__(
        self,
        operation,
        model,
        model_id,
        model_repo_id,
        model_type,
        cluster_context=None,
    ):
        """
        Initialize the deployer configuration.

        Args:
            operation (str): Operation to perform ('deploy', 'status', etc.)
            model (str): The SEMOSS short name for the model
            model_id (str): The SEMOSS UUID for the model
            model_repo_id (str): The HuggingFace model repo ID
            model_type (str): The model type
            cluster_context (str, optional): Kubernetes cluster context to use
        """
        # These are all environment variables
        self.namespace = NAMESPACE
        self.model_namespace = MODEL_NAMESPACE
        self.docker_image = DOCKER_IMAGE
        self.zookeeper_hosts = ZK_HOSTS
        self.image_pull_secret = IMAGE_PULL_SECRET
        self.standard_cluster = STANDARD_CLUSTER
        self.autopilot_cluster = AUTOPILOT_CLUSTER
        self.kubeconfig_path = (
            KUBECONFIG_PATH  # Path to mounted kubeconfig in production
        )

        self.resources_path = (
            pathlib.Path(__file__).parent.parent / "resources" / "models"
        )

        self.operation = operation  # Start or stop determined by endpoint

        self.model_name = model  # The SEMOSS short name for the model
        self.model_id = model_id  # The SEMOSS UUID for the model
        self.model_repo_id = model_repo_id  # The HuggingFace model repo ID
        self.model_type = model_type  # The model type

        # Use provided context or default to standard cluster
        self.cluster_context = cluster_context or self.standard_cluster

        # Initialize Kubernetes client based on environment and provided context
        self.initialize_kubernetes_client(self.cluster_context)

        logger.info(
            f"Initializing BaseDeployer with namespace={self.namespace}, "
            f"model_namespace={self.model_namespace}, "
            f"zookeeper_hosts={self.zookeeper_hosts}, "
            f"image_pull_secret={self.image_pull_secret}, "
            f"cluster_context={self.cluster_context}"
        )

        # Initialize ZooKeeper connection
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

        # Initialize cloud manager based on the configured provider
        self.cloud_manager = get_cloud_manager()

    def initialize_kubernetes_client(self, cluster_context=None):
        """
        Initialize Kubernetes client with the appropriate configuration.

        Args:
            cluster_context (str, optional): Kubernetes cluster context to use
        """
        if IS_DEV:
            # Development mode - use local kubeconfig
            logger.info("Using dev config")

            try:
                # Checking if the requested context exists
                if cluster_context:
                    self._validate_context_exists(cluster_context)

                    logger.info(f"Using specified context: {cluster_context}")
                    config.load_kube_config(context=cluster_context)
                else:
                    # Using default context from kubeconfig
                    logger.info("Using default context from kubeconfig")
                    config.load_kube_config()

                # Logging the active context for confirmation
                current_context = config.list_kube_config_contexts()[1]
                logger.info(f"Active Kubernetes context: {current_context['name']}")

            except Exception as e:
                logger.error(f"Error loading kubeconfig: {e}")
                raise RuntimeError(f"Failed to initialize Kubernetes client: {e}")

        else:
            # Production mode - try mounted kubeconfig first then fall back to in-cluster config
            # if self.kubeconfig_path and os.path.exists(self.kubeconfig_path):
            #     # Use mounted kubeconfig for multi-cluster support
            #     logger.info(f"Using mounted kubeconfig at {self.kubeconfig_path}")

            #     try:
            #         if cluster_context:
            #             # Validating the context exists
            #             self._validate_context_exists(
            #                 cluster_context, self.kubeconfig_path
            #             )

            #             # Load specific context from the kubeconfig
            #             logger.info(
            #                 f"Using context {cluster_context} from mounted kubeconfig"
            #             )
            #             config.load_kube_config(
            #                 config_file=self.kubeconfig_path, context=cluster_context
            #             )
            #         else:
            #             # Using default context from the kubeconfig
            #             logger.info("Using default context from mounted kubeconfig")
            #             config.load_kube_config(config_file=self.kubeconfig_path)

            #         # Log the active context
            #         contexts, active = config.list_kube_config_contexts(
            #             config_file=self.kubeconfig_path
            #         )
            #         logger.info(f"Active Kubernetes context: {active['name']}")
            #         logger.info(
            #             f"Available contexts: {[ctx['name'] for ctx in contexts]}"
            #         )

            #     except Exception as e:
            #         logger.error(f"Error loading mounted kubeconfig: {e}")
            #         logger.info("Falling back to in-cluster config")
            #         self._load_incluster_config()
            # else:
            #     # No mounted kubeconfig use in-cluster config
            #     logger.info("No mounted kubeconfig found, using in-cluster config")
            #     self._load_incluster_config()
            try:
                config.load_incluster_config()
                logger.info("Successfully loaded in-cluster config")
            except Exception as e:
                logger.error(f"Failed to load in-cluster config: {e}")
                raise

    def _load_incluster_config(self):
        """Helper method to load in-cluster config with proper error handling"""
        try:
            config.load_incluster_config()
            logger.info("Successfully loaded in-cluster config")
        except Exception as e:
            logger.error(f"Error loading in-cluster config: {e}")
            raise RuntimeError(
                f"Failed to initialize in-cluster Kubernetes client: {e}"
            )

    def _validate_context_exists(self, context_name, config_file=None):
        """
        Check if a context exists in the kubeconfig before attempting to use it.

        Args:
            context_name (str): Name of the context to validate
            config_file (str, optional): Path to kubeconfig file

        Raises:
            ValueError: If the context doesn't exist
        """
        try:
            contexts, _ = config.list_kube_config_contexts(config_file=config_file)
            available_contexts = [ctx["name"] for ctx in contexts]

            if context_name not in available_contexts:
                logger.error(f"Context '{context_name}' not found in kubeconfig")
                logger.info(f"Available contexts: {available_contexts}")
                raise ValueError(
                    f"Context '{context_name}' not found in kubeconfig. Available contexts: {available_contexts}"
                )

            logger.info(f"Context '{context_name}' found in kubeconfig")

        except Exception as e:
            if "list_kube_config_contexts" in str(e):
                logger.error("Could not read kubeconfig contexts")
                raise RuntimeError(
                    "Could not read kubeconfig contexts. Make sure your kubeconfig file is valid."
                )
            else:
                raise

    def switch_cluster(self, cluster_context):
        """
        Switch to a different Kubernetes cluster context.

        Args:
            cluster_context (str): Kubernetes cluster context to use

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Switching to cluster context: {cluster_context}")

            # For production with mounted kubeconfig, validate the context exists
            if (
                not IS_DEV
                and self.kubeconfig_path
                and os.path.exists(self.kubeconfig_path)
            ):
                self._validate_context_exists(cluster_context, self.kubeconfig_path)

            self.cluster_context = cluster_context

            # Reinitializing the Kubernetes client with the new context
            self.initialize_kubernetes_client(cluster_context)

            return True
        except Exception as e:
            logger.error(f"Failed to switch cluster context: {e}")
            return False

    def list_available_contexts(self):
        """
        List all available Kubernetes contexts in the kubeconfig.

        Returns:
            dict: Dictionary with available contexts and active context
        """
        try:
            # For production with mounted kubeconfig
            if (
                not IS_DEV
                and self.kubeconfig_path
                and os.path.exists(self.kubeconfig_path)
            ):
                contexts, active_context = config.list_kube_config_contexts(
                    config_file=self.kubeconfig_path
                )
            else:
                # Development or no mounted kubeconfig
                contexts, active_context = config.list_kube_config_contexts()

            return {
                "available_contexts": [ctx["name"] for ctx in contexts],
                "active_context": active_context["name"],
            }
        except Exception as e:
            logger.error(f"Error listing Kubernetes contexts: {e}")
            return {"error": str(e)}
