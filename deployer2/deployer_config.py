import logging
import os
from kubernetes import config, client
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

        self.operation = operation  # Start or stop determined by endpoint

        self.model_name = model  # The SEMOSS short name for the model
        self.model_id = model_id  # The SEMOSS UUID for the model
        self.model_repo_id = model_repo_id  # The HuggingFace model repo ID
        self.model_type = model_type  # The model type

        # We create a client for each cluster context
        self.clients = {}
        self.current_context = self.standard_cluster
        # Initialize Kubernetes clients for both standard and autopilot clusters
        self.initialize_kubernetes_clients()

        logger.info(
            f"Initializing BaseDeployer with namespace={self.namespace}, "
            f"model_namespace={self.model_namespace}, "
            f"zookeeper_hosts={self.zookeeper_hosts}, "
            f"image_pull_secret={self.image_pull_secret}, "
            f"current_context={self.current_context}"
        )

        # Initialize ZooKeeper connection
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

        # Initialize cloud manager based on the configured provider
        self.cloud_manager = get_cloud_manager()

    def initialize_kubernetes_clients(self):
        """Initialize separate K8s client instances for each cluster"""
        if IS_DEV:
            # Development mode - use local kubeconfig
            logger.info("Using dev config for client initialization")
            try:
                contexts, _ = config.list_kube_config_contexts()
                available_contexts = [ctx["name"] for ctx in contexts]

                for context_name in [self.standard_cluster, self.autopilot_cluster]:
                    if context_name in available_contexts:
                        # Create client configuration for this context
                        client_config = client.Configuration()
                        config.load_kube_config(
                            client_configuration=client_config, context=context_name
                        )
                        # Store the client configuration
                        self.clients[context_name] = client_config
                        logger.info(
                            f"Successfully created client for context: {context_name}"
                        )
                    else:
                        logger.warning(
                            f"Context {context_name} not found in local kubeconfig"
                        )
            except Exception as e:
                logger.error(f"Error loading kubeconfig: {e}")
                raise RuntimeError(f"Failed to initialize Kubernetes clients: {e}")
        else:
            # Production mode with mounted kubeconfig
            if self.kubeconfig_path and os.path.exists(self.kubeconfig_path):
                logger.info(f"Using mounted kubeconfig at {self.kubeconfig_path}")
                try:
                    contexts, _ = config.list_kube_config_contexts(
                        config_file=self.kubeconfig_path
                    )
                    available_contexts = [ctx["name"] for ctx in contexts]

                    for context_name in [self.standard_cluster, self.autopilot_cluster]:
                        if context_name in available_contexts:
                            # Create client configuration for this context
                            client_config = client.Configuration()
                            config.load_kube_config(
                                client_configuration=client_config,
                                config_file=self.kubeconfig_path,
                                context=context_name,
                            )
                            # Store the client configuration
                            self.clients[context_name] = client_config
                            logger.info(
                                f"Successfully created client for context: {context_name}"
                            )
                        else:
                            logger.warning(
                                f"Context {context_name} not found in mounted kubeconfig"
                            )
                except Exception as e:
                    logger.error(f"Error loading mounted kubeconfig: {e}")
                    logger.info("Falling back to in-cluster config")
                    self._load_incluster_config()
            else:
                # No mounted kubeconfig, use in-cluster config
                self._load_incluster_config()

    def get_api_client(self, context_name=None):
        """
        Get API client for the specified context or current context
        """
        ctx = context_name or self.current_context

        # If accessing autopilot cluster, use token-based auth
        if ctx == self.autopilot_cluster and not IS_DEV:
            # Get the API server URL from environment or config
            autopilot_api_server = os.environ.get("AUTOPILOT_API_SERVER", None)
            autopilot_token = os.environ.get("AUTOPILOT_TOKEN", "")

            if not autopilot_token:
                logger.error("No token provided for autopilot cluster authentication")
                raise ValueError("Missing AUTOPILOT_TOKEN environment variable")

            # Configure API client with token auth to autopilot cluster
            configuration = client.Configuration()
            configuration.host = autopilot_api_server
            configuration.verify_ssl = False  # For testing only, enable in production
            configuration.api_key = {"authorization": f"Bearer {autopilot_token}"}
            configuration.api_key_prefix = {"authorization": "Bearer"}

            logger.info(
                f"Created API client for autopilot cluster using token authentication"
            )
            return client.ApiClient(configuration)

        # Otherwise use the existing approach for standard cluster
        elif ctx in self.clients:
            return client.ApiClient(self.clients[ctx])
        else:
            logger.error(f"No client configuration found for context: {ctx}")
            raise ValueError(f"No client configuration available for {ctx}")

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
