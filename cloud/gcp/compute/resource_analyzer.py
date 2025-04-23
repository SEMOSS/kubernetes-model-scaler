from kubernetes import client, config
import yaml
import logging
from typing import Dict, List, Tuple
from cloud.gcp.storage.storage_manager import StorageManager

logger = logging.getLogger(__name__)


class ResourceAnalyzer:

    def __init__(self):
        """
        Initialize the Kubernetes resource checker.
        Loads configuration from GCS bucket using StorageManager.
        """
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("Loaded kubeconfig from default location")
            except config.ConfigException:
                logger.error("Could not load Kubernetes configuration")
                raise

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

        self.storage_manager = StorageManager()

        # Load node pool configuration from GCS
        self._initialize_from_cloud()

    def _initialize_from_cloud(self):
        """
        Initialize node pools and machine specifications from GCS bucket.
        """
        try:
            # Get node pool configuration from storage
            node_pool_config = self.storage_manager.get_node_pool_config(
                "node_pools.json"
            )

            self.node_pools = {}
            self.machine_specs = {}
            self.gpu_specs = {}

            # Extract node_pools from config
            if "node_pools" in node_pool_config:
                self.node_pools = node_pool_config["node_pools"]

                # Extract GPU specs from node pools
                for pool_name, pool_info in self.node_pools.items():
                    if "gpu" in pool_info:
                        self.gpu_specs[pool_name] = pool_info["gpu"]

            # Extract machine_specs from config
            if "machine_specs" in node_pool_config:
                self.machine_specs = node_pool_config["machine_specs"]

            logger.info(
                f"Initialized ResourceAnalyzer with {len(self.node_pools)} node pools from cloud config"
            )
        except Exception as e:
            logger.error(f"Failed to initialize from cloud config: {e}")
            raise

    def get_nodes_by_pool(self) -> Dict[str, List[str]]:
        """
        Get nodes grouped by node pool.
        Returns:
            Dictionary with node pool names as keys and lists of node names as values
        """
        nodes_by_pool = {pool: [] for pool in self.node_pools}

        # Listing all nodes in the cluster
        nodes = self.core_v1.list_node().items

        for node in nodes:
            # Checking which node pool this node belongs to based on labels
            for pool_name, pool_info in self.node_pools.items():
                matches_pool = True
                for label_key, label_value in pool_info.get("labels", {}).items():
                    if (
                        label_key not in node.metadata.labels
                        or node.metadata.labels[label_key] != label_value
                    ):
                        matches_pool = False
                        break

                if matches_pool:
                    nodes_by_pool[pool_name].append(node.metadata.name)
                    break

        return nodes_by_pool

    def get_node_resource_usage(self, node_name: str) -> Dict:
        """
        Get resource usage for a specific node.
        Args:
            node_name: Name of the node

        Returns:
            Dictionary with resource usage information
        """
        # Get node object to check capacity
        node = self.core_v1.read_node(node_name)
        capacity = node.status.capacity
        allocatable = node.status.allocatable

        # Getting pods on this node to calculate used resources
        field_selector = (
            f"spec.nodeName={node_name},status.phase!=Failed,status.phase!=Succeeded"
        )
        pods = self.core_v1.list_pod_for_all_namespaces(
            field_selector=field_selector
        ).items

        used_resources = {
            "cpu_requests": 0,
            "cpu_limits": 0,
            "memory_requests_bytes": 0,
            "memory_limits_bytes": 0,
            "gpu_requests": 0,
            "gpu_limits": 0,
        }

        # Calculate resources used by pods
        for pod in pods:
            for container in pod.spec.containers:
                if container.resources and container.resources.requests:
                    requests = container.resources.requests
                    if "cpu" in requests:
                        used_resources["cpu_requests"] += self._parse_cpu(
                            requests["cpu"]
                        )
                    if "memory" in requests:
                        used_resources["memory_requests_bytes"] += self._parse_memory(
                            requests["memory"]
                        )
                    # Check for GPU requests dynamically for any GPU type
                    for resource_name in requests:
                        if resource_name.endswith("/gpu"):
                            used_resources["gpu_requests"] += int(
                                requests[resource_name]
                            )

                if container.resources and container.resources.limits:
                    limits = container.resources.limits
                    if "cpu" in limits:
                        used_resources["cpu_limits"] += self._parse_cpu(limits["cpu"])
                    if "memory" in limits:
                        used_resources["memory_limits_bytes"] += self._parse_memory(
                            limits["memory"]
                        )
                    # Check for GPU limits dynamically for any GPU type
                    for resource_name in limits:
                        if resource_name.endswith("/gpu"):
                            used_resources["gpu_limits"] += int(limits[resource_name])

        available = {
            "cpu_allocatable": self._parse_cpu(allocatable["cpu"]),
            "memory_allocatable_bytes": self._parse_memory(allocatable["memory"]),
            "cpu_available_requests": self._parse_cpu(allocatable["cpu"])
            - used_resources["cpu_requests"],
            "memory_available_requests_bytes": self._parse_memory(allocatable["memory"])
            - used_resources["memory_requests_bytes"],
            "cpu_available_limits": self._parse_cpu(allocatable["cpu"])
            - used_resources["cpu_limits"],
            "memory_available_limits_bytes": self._parse_memory(allocatable["memory"])
            - used_resources["memory_limits_bytes"],
        }

        # Adding GPU information if present - check for any GPU type
        gpu_found = False
        for resource_name in allocatable:
            if resource_name.endswith("/gpu"):
                gpu_allocatable = int(allocatable[resource_name])
                available["gpu_allocatable"] = gpu_allocatable
                available["gpu_available_requests"] = (
                    gpu_allocatable - used_resources["gpu_requests"]
                )
                available["gpu_available_limits"] = (
                    gpu_allocatable - used_resources["gpu_limits"]
                )
                gpu_found = True
                break

        # If no GPU found, set GPU values to 0
        if not gpu_found:
            available["gpu_allocatable"] = 0
            available["gpu_available_requests"] = 0
            available["gpu_available_limits"] = 0

        return {
            "capacity": capacity,
            "allocatable": allocatable,
            "used": used_resources,
            "available": available,
        }

    def get_pool_resources(self, pool_name: str) -> Dict:
        """
        Get resource information for an entire node pool.
        Args:
            pool_name: Name of the node pool
        Returns:
            Dictionary with pool resource information
        """
        nodes_by_pool = self.get_nodes_by_pool()

        if pool_name not in nodes_by_pool:
            logger.warning(f"Node pool {pool_name} not found in cluster")
            return None

        nodes = nodes_by_pool[pool_name]

        if not nodes:
            logger.warning(f"No nodes found for pool {pool_name}")
            return {
                "nodes": [],
                "total": {
                    "cpu_requests_available": 0,
                    "memory_requests_available_gi": 0,
                    "gpu_requests_available": 0,
                    "cpu_limits_available": 0,
                    "memory_limits_available_gi": 0,
                    "gpu_limits_available": 0,
                },
            }

        # Get resource information for each node
        node_resources = {}
        total_resources = {
            "cpu_requests_available": 0,
            "memory_requests_available_gi": 0,
            "gpu_requests_available": 0,
            "cpu_limits_available": 0,
            "memory_limits_available_gi": 0,
            "gpu_limits_available": 0,
        }

        for node_name in nodes:
            node_resources[node_name] = self.get_node_resource_usage(node_name)

            # Sum up available resources across the pool
            total_resources["cpu_requests_available"] += node_resources[node_name][
                "available"
            ]["cpu_available_requests"]
            total_resources["memory_requests_available_gi"] += node_resources[
                node_name
            ]["available"]["memory_available_requests_bytes"] / (1024**3)
            total_resources["gpu_requests_available"] += node_resources[node_name][
                "available"
            ]["gpu_available_requests"]

            total_resources["cpu_limits_available"] += node_resources[node_name][
                "available"
            ]["cpu_available_limits"]
            total_resources["memory_limits_available_gi"] += node_resources[node_name][
                "available"
            ]["memory_available_limits_bytes"] / (1024**3)
            total_resources["gpu_limits_available"] += node_resources[node_name][
                "available"
            ]["gpu_available_limits"]

        return {"nodes": node_resources, "total": total_resources}

    def get_all_pool_resources(self) -> Dict[str, Dict]:
        """
        Get resource information for all node pools.
        Returns:
            Dictionary with pool names as keys and resource information as values
        """
        all_resources = {}

        for pool_name in self.node_pools:
            all_resources[pool_name] = self.get_pool_resources(pool_name)

        return all_resources

    def parse_deployment_resources(self, deployment_yaml: str) -> Dict:
        """
        Parse resource requirements from a deployment YAML.

        Args:
            deployment_yaml: String containing deployment YAML

        Returns:
            Dictionary with resource requirements
        """
        try:
            deployment_dict = yaml.safe_load(deployment_yaml)

            # Extract resource requirements
            resources = {}

            # For KServe InferenceService
            if deployment_dict.get("kind") == "InferenceService":
                containers = (
                    deployment_dict.get("spec", {})
                    .get("predictor", {})
                    .get("containers", [])
                )
                if containers:
                    container_resources = containers[0].get("resources", {})

                    # Get requests
                    requests = container_resources.get("requests", {})
                    resources["cpu_requests"] = (
                        self._parse_cpu(requests.get("cpu", "0"))
                        if "cpu" in requests
                        else 0
                    )
                    resources["memory_requests_gi"] = (
                        self._parse_memory(requests.get("memory", "0")) / (1024**3)
                        if "memory" in requests
                        else 0
                    )

                    # Check for GPU requests dynamically for any GPU type
                    resources["gpu_requests"] = 0
                    for resource_name, value in requests.items():
                        if resource_name.endswith("/gpu"):
                            resources["gpu_requests"] = int(value)
                            break

                    # Get limits
                    limits = container_resources.get("limits", {})
                    resources["cpu_limits"] = (
                        self._parse_cpu(limits.get("cpu", "0"))
                        if "cpu" in limits
                        else 0
                    )
                    resources["memory_limits_gi"] = (
                        self._parse_memory(limits.get("memory", "0")) / (1024**3)
                        if "memory" in limits
                        else 0
                    )

                    # Check for GPU limits dynamically for any GPU type
                    resources["gpu_limits"] = 0
                    for resource_name, value in limits.items():
                        if resource_name.endswith("/gpu"):
                            resources["gpu_limits"] = int(value)
                            break

            # For regular Deployment
            elif deployment_dict.get("kind") == "Deployment":
                containers = (
                    deployment_dict.get("spec", {})
                    .get("template", {})
                    .get("spec", {})
                    .get("containers", [])
                )

                if containers:
                    # Sum up resources from all containers
                    cpu_requests = 0
                    memory_requests_bytes = 0
                    gpu_requests = 0
                    cpu_limits = 0
                    memory_limits_bytes = 0
                    gpu_limits = 0

                    for container in containers:
                        container_resources = container.get("resources", {})

                        # Get requests
                        requests = container_resources.get("requests", {})
                        cpu_requests += (
                            self._parse_cpu(requests.get("cpu", "0"))
                            if "cpu" in requests
                            else 0
                        )
                        memory_requests_bytes += (
                            self._parse_memory(requests.get("memory", "0"))
                            if "memory" in requests
                            else 0
                        )

                        # Check for GPU requests dynamically for any GPU type
                        for resource_name, value in requests.items():
                            if resource_name.endswith("/gpu"):
                                gpu_requests += int(value)

                        # Get limits
                        limits = container_resources.get("limits", {})
                        cpu_limits += (
                            self._parse_cpu(limits.get("cpu", "0"))
                            if "cpu" in limits
                            else 0
                        )
                        memory_limits_bytes += (
                            self._parse_memory(limits.get("memory", "0"))
                            if "memory" in limits
                            else 0
                        )

                        # Check for GPU limits dynamically for any GPU type
                        for resource_name, value in limits.items():
                            if resource_name.endswith("/gpu"):
                                gpu_limits += int(value)

                    resources["cpu_requests"] = cpu_requests
                    resources["memory_requests_gi"] = memory_requests_bytes / (1024**3)
                    resources["gpu_requests"] = gpu_requests
                    resources["cpu_limits"] = cpu_limits
                    resources["memory_limits_gi"] = memory_limits_bytes / (1024**3)
                    resources["gpu_limits"] = gpu_limits

            return resources

        except Exception as e:
            logger.error(f"Error parsing deployment YAML: {e}")
            return None

    def find_suitable_pool(
        self, deployment_yaml: str, use_limits: bool = True
    ) -> Tuple[str, bool]:
        """
        Find a suitable node pool for deployment.

        Args:
            deployment_yaml: String containing deployment YAML
            use_limits: Whether to check against limits (True) or requests (False)

        Returns:
            Tuple of (pool_name, can_deploy)
            pool_name is None if no suitable pool is found
        """
        resources = self.parse_deployment_resources(deployment_yaml)
        if not resources:
            return None, False

        # Get available resources in each pool
        pool_resources = self.get_all_pool_resources()

        # Determine which pool to use based on resource requirements
        gpu_requirement = (
            resources["gpu_limits"] if use_limits else resources["gpu_requests"]
        )
        memory_requirement = (
            resources["memory_limits_gi"]
            if use_limits
            else resources["memory_requests_gi"]
        )
        cpu_requirement = (
            resources["cpu_limits"] if use_limits else resources["cpu_requests"]
        )

        # First, try to find a suitable pool that meets all requirements
        for pool_name, pool_data in pool_resources.items():
            if pool_data is None:
                continue

            # Check if this pool has GPU if required
            has_gpu = False
            if pool_name in self.gpu_specs:
                has_gpu = self.gpu_specs[pool_name]["count"] > 0

            # Skip this pool if it doesn't have GPU but we need it
            if gpu_requirement > 0 and not has_gpu:
                continue

            # Check if the pool has enough resources
            gpu_available = (
                pool_data["total"]["gpu_limits_available"]
                if use_limits
                else pool_data["total"]["gpu_requests_available"]
            )
            memory_available = (
                pool_data["total"]["memory_limits_available_gi"]
                if use_limits
                else pool_data["total"]["memory_requests_available_gi"]
            )
            cpu_available = (
                pool_data["total"]["cpu_limits_available"]
                if use_limits
                else pool_data["total"]["cpu_requests_available"]
            )

            if (
                gpu_available >= gpu_requirement
                and memory_available >= memory_requirement
                and cpu_available >= cpu_requirement
            ):
                return pool_name, True

        # No suitable pool found
        return None, False

    def can_deploy(
        self, deployment_yaml: str, use_limits: bool = True
    ) -> Tuple[bool, Dict]:
        """
        Check if the deployment can be accommodated in the cluster.
        Args:
            deployment_yaml: String containing deployment YAML
            use_limits: Whether to check against limits (True) or requests (False)
        Returns:
            Tuple of (can_deploy, details)
        """
        pool_name, can_deploy = self.find_suitable_pool(deployment_yaml, use_limits)

        if can_deploy:
            return True, {
                "suitable_pool": pool_name,
                "message": f"Deployment can be accommodated in {pool_name}",
            }
        else:
            # Get more details about why it can't be deployed
            resources = self.parse_deployment_resources(deployment_yaml)
            pool_resources = self.get_all_pool_resources()

            # Prepare detailed response
            details = {
                "suitable_pool": None,
                "message": "Deployment cannot be accommodated",
                "requested_resources": resources,
                "available_resources": {},
            }

            for pool_name, pool_data in pool_resources.items():
                if pool_data:
                    details["available_resources"][pool_name] = pool_data["total"]

            return False, details

    def _parse_cpu(self, cpu_str: str) -> float:
        """
        Parse CPU resource string to a float value.

        Args:
            cpu_str: CPU resource string (e.g., '100m', '0.1', '1')

        Returns:
            CPU value as a float
        """
        if not cpu_str:
            return 0

        if isinstance(cpu_str, (int, float)):
            return float(cpu_str)

        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1000
        else:
            return float(cpu_str)

    def _parse_memory(self, memory_str: str) -> int:
        """
        Parse memory resource string to bytes.
        Args:
            memory_str: Memory resource string (e.g., '100Mi', '1Gi')
        Returns:
            Memory value in bytes
        """
        if not memory_str:
            return 0

        if isinstance(memory_str, (int, float)):
            return int(memory_str)

        memory_str = str(memory_str)

        # Convert to bytes
        if memory_str.endswith("Ki"):
            return int(float(memory_str[:-2]) * 1024)
        elif memory_str.endswith("Mi"):
            return int(float(memory_str[:-2]) * 1024 * 1024)
        elif memory_str.endswith("Gi"):
            return int(float(memory_str[:-2]) * 1024 * 1024 * 1024)
        elif memory_str.endswith("Ti"):
            return int(float(memory_str[:-2]) * 1024 * 1024 * 1024 * 1024)
        elif memory_str.endswith("Pi"):
            return int(float(memory_str[:-2]) * 1024 * 1024 * 1024 * 1024 * 1024)
        elif memory_str.endswith("Ei"):
            return int(float(memory_str[:-2]) * 1024 * 1024 * 1024 * 1024 * 1024 * 1024)
        elif memory_str.endswith("K") or memory_str.endswith("k"):
            return int(float(memory_str[:-1]) * 1000)
        elif memory_str.endswith("M"):
            return int(float(memory_str[:-1]) * 1000 * 1000)
        elif memory_str.endswith("G"):
            return int(float(memory_str[:-1]) * 1000 * 1000 * 1000)
        elif memory_str.endswith("T"):
            return int(float(memory_str[:-1]) * 1000 * 1000 * 1000 * 1000)
        elif memory_str.endswith("P"):
            return int(float(memory_str[:-1]) * 1000 * 1000 * 1000 * 1000 * 1000)
        elif memory_str.endswith("E"):
            return int(float(memory_str[:-1]) * 1000 * 1000 * 1000 * 1000 * 1000 * 1000)
        else:
            try:
                return int(float(memory_str))
            except ValueError:
                logger.error(f"Could not parse memory string: {memory_str}")
                return 0
