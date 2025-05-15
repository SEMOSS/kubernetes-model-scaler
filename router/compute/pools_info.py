from typing import Optional, List, Dict, Any
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from kubernetes.client.rest import ApiException
from cloud.gcp.compute.resource_analyzer import ResourceAnalyzer
from zk_manager.zk_manager import ZKManager

logger = logging.getLogger(__name__)


class ModelResources(BaseModel):
    """Representation of a model's resource consumption"""

    cpu: float
    memory_gi: float
    gpu: int = 0


class ModelResourceInfo(BaseModel):
    """Model for representing model resource usage"""

    name: str
    model_id: str
    namespace: str
    node: str
    status: str
    url: Optional[str] = None
    resources: ModelResources


class NodePoolSpec(BaseModel):
    """Specifications of a node pool"""

    machine_type: str
    gpu_type: Optional[str] = None
    gpu_count: int = 0


class NodePoolResources(BaseModel):
    """Resource allocation in a node pool"""

    cpu_total: float = Field(..., description="Total CPU cores in the pool")
    memory_total_gi: float = Field(..., description="Total memory in GiB")
    cpu_available: float = Field(..., description="Available CPU cores")
    memory_available_gi: float = Field(..., description="Available memory in GiB")
    gpu_available: int = Field(0, description="Available GPUs")


class NodePoolResponse(BaseModel):
    """Response model for node pool information"""

    name: str
    spec: NodePoolSpec
    resources: NodePoolResources
    models: List[ModelResourceInfo] = []


class DeployerStatus(BaseModel):
    """Model for representing the status of the deployer"""

    status: str
    ip_address: str
    last_updated: str


class ZKModelMetadata(BaseModel):
    """Model for representing model metadata in ZooKeeper"""

    ip: str
    model_name: str
    model_type: str
    model_repo_id: str
    deployment_type: str


class ZKModel(BaseModel):
    """Model for representing a model in ZooKeeper"""

    model_id: str
    model_name: str
    cluster_ip: str
    status: str
    last_updated: str
    metadata: ZKModelMetadata


class ZKInfo(BaseModel):
    """Model for representing ZooKeeper information"""

    active_models: List[ZKModel] = []
    warming_models: List[ZKModel] = []
    cooling_models: List[ZKModel] = []
    deployer_status: DeployerStatus


class ActiveModelsActual(BaseModel):
    """Model for representing actual active models"""

    active_models_actual: List[str] = Field(
        default_factory=list,
        description="Models marked as active in both ZK and node pool",
    )
    active_models_zk: List[str] = Field(
        default_factory=list, description="Models marked as active in ZK"
    )
    active_models_node_pool: List[str] = Field(
        default_factory=list, description="Models marked as active in in the node pool"
    )
    false_zk_models: List[str] = Field(
        default_factory=list,
        description="Models marked as active in ZK but not found in the node pool",
    )


class NodePoolsInfoResponse(BaseModel):
    """Complete response for the node pools endpoint"""

    zk_info: ZKInfo
    pools: List[NodePoolResponse]
    active_models_actual: ActiveModelsActual
    message: str


pools_info_router = APIRouter()


def determine_active_models_actual(
    zk_info: ZKInfo, formatted_pools: List[NodePoolResponse]
):
    """
    Determine the actual active models based on the node pools and ZooKeeper information.

    Args:
        zk_info (ZKInfo): The ZooKeeper information.
        formatted_pools (List[NodePoolResponse]): The formatted node pools information.

    Returns:

    """
    # All models that are marked as active in ZooKeeper
    zk_active_models = [
        zk_info.active_models[i].model_id for i in range(len(zk_info.active_models))
    ]
    # Tracking models marked as actively running in the node pool
    node_pool_active_models = []
    # Tracking models that are marked as active in both ZK and node pool
    active_models_actual = []
    # Tracking models that are marked as active in ZK but not in the node pool
    false_zk_models = []

    for pool in formatted_pools:
        for model in pool.models:
            # Found active model in the node pool
            node_pool_active_models.append(model.model_id)
            if model.model_id in zk_active_models:
                # Check if active model in Node Pool is also in ZK
                # This accounts for models that are being torn down but the pods are still running
                active_models_actual.append(model.model_id)

    for model in zk_active_models:
        if model not in node_pool_active_models:
            # This model is marked as active in ZK but not in any node pool
            false_zk_models.append(model)

    return ActiveModelsActual(
        active_models_actual=active_models_actual,
        active_models_zk=zk_active_models,
        active_models_node_pool=node_pool_active_models,
        false_zk_models=false_zk_models,
    )


@pools_info_router.get("/node-pools-info", response_model=NodePoolsInfoResponse)
async def get_pools_info():
    """
    Fetch and return information about available node pools in the cluster,
    including models running on each pool and their resource consumption.

    Returns:
        NodePoolsInfoResponse: Complete information about node pools and ZooKeeper state
    """
    try:
        resource_analyzer = ResourceAnalyzer()

        pool_resources = resource_analyzer.get_all_pool_resources()
        models_by_pool = resource_analyzer.get_models_by_node_pool()

        formatted_pools = []
        for pool_name, pool_data in pool_resources.items():
            if pool_data:
                machine_type = resource_analyzer.node_pools[pool_name].get(
                    "machine_type", "unknown"
                )
                gpu_specs = resource_analyzer.gpu_specs.get(
                    pool_name, {"type": None, "count": 0}
                )

                machine_specs = resource_analyzer.machine_specs.get(machine_type, {})
                instances = resource_analyzer.node_pools[pool_name].get("instances", 1)

                # Calculate total CPU and memory based on machine specs and instances
                cpu_total = machine_specs.get("cpu", 0) * instances
                memory_total_gi = machine_specs.get("memory_gi", 0) * instances

                # Round CPU available to 2 decimal places
                cpu_available = round(pool_data["total"]["cpu_requests_available"], 2)
                memory_available_gi = round(
                    pool_data["total"]["memory_requests_available_gi"], 2
                )

                # Get models running on this pool
                pool_models = models_by_pool.get(pool_name, [])

                # Calculate total GPU count for the pool (per instance * number of instances)
                total_gpu_count = gpu_specs.get("count", 0) * instances

                # Create models list with proper resource structure
                models_list = []
                for model_info in pool_models:
                    # Extract resources into their own model
                    resources_dict = model_info.pop("resources", {})
                    resources = ModelResources(
                        cpu=resources_dict.get("cpu_requests", 0),
                        memory_gi=resources_dict.get("memory_requests_gi", 0),
                        gpu=resources_dict.get("gpu_requests", 0),
                    )
                    # Create the model with separated resources
                    models_list.append(
                        ModelResourceInfo(**model_info, resources=resources)
                    )

                formatted_pools.append(
                    NodePoolResponse(
                        name=pool_name,
                        spec=NodePoolSpec(
                            machine_type=machine_type,
                            gpu_type=gpu_specs.get("type"),
                            gpu_count=total_gpu_count,
                        ),
                        resources=NodePoolResources(
                            cpu_total=round(cpu_total, 2),
                            memory_total_gi=round(memory_total_gi, 2),
                            cpu_available=cpu_available,
                            memory_available_gi=memory_available_gi,
                            # Ensure GPU available doesn't exceed total count
                            gpu_available=min(
                                round(pool_data["total"]["gpu_requests_available"]),
                                total_gpu_count,
                            ),
                        ),
                        models=models_list,
                    )
                )

        zk_manager = ZKManager()
        models = zk_manager.get_all_models()
        warming_models = models.get("warming", [])
        active_models = models.get("active", [])
        cooling_models = models.get("cooling", [])
        deployer_status = zk_manager.get_deployer_status()

        zk_info = ZKInfo(
            active_models=active_models,
            warming_models=warming_models,
            cooling_models=cooling_models,
            deployer_status=DeployerStatus(**deployer_status),
        )

        active_models_actual = determine_active_models_actual(zk_info, formatted_pools)

        return NodePoolsInfoResponse(
            zk_info=zk_info,
            pools=formatted_pools,
            active_models_actual=active_models_actual,
            message="Successfully retrieved node pool information",
        )

    except ApiException as e:
        logger.error(f"Kubernetes API error: {e}")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        logger.error(f"Error retrieving node pool information: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving node pool information: {str(e)}"
        )
