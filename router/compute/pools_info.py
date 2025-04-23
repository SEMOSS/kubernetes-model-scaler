from typing import Optional
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from kubernetes.client.rest import ApiException
from cloud.gcp.compute.resource_analyzer import ResourceAnalyzer

logger = logging.getLogger(__name__)


class NodePoolResponse(BaseModel):
    """Response model for node pool information"""

    name: str
    machine_type: str
    gpu_type: Optional[str] = None
    gpu_count: int = 0
    cpu_total: float
    memory_total_gi: float
    cpu_available: float
    memory_available_gi: float
    gpu_available: int


pools_info_router = APIRouter()


@pools_info_router.get("/node-pools-info")
async def get_pools_info():
    """
    Fetch and return information about available node pools in the cluster.

    Returns:
        dict: Dictionary containing node pool information and resource availability
    """
    try:
        resource_analyzer = ResourceAnalyzer()

        pool_resources = resource_analyzer.get_all_pool_resources()

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
                cpu_total = machine_specs.get("cpu", 0) * resource_analyzer.node_pools[
                    pool_name
                ].get("instances", 1)
                memory_total_gi = machine_specs.get(
                    "memory_gi", 0
                ) * resource_analyzer.node_pools[pool_name].get("instances", 1)

                cpu_available = round(pool_data["total"]["cpu_requests_available"], 2)
                memory_available_gi = round(
                    pool_data["total"]["memory_requests_available_gi"], 2
                )

                formatted_pools.append(
                    NodePoolResponse(
                        name=pool_name,
                        machine_type=machine_type,
                        gpu_type=gpu_specs.get("type"),
                        gpu_count=gpu_specs.get("count", 0),
                        cpu_total=round(cpu_total, 2),
                        memory_total_gi=round(memory_total_gi, 2),
                        cpu_available=cpu_available,
                        memory_available_gi=memory_available_gi,
                        gpu_available=pool_data["total"]["gpu_requests_available"],
                    )
                )

        return {
            "pools": [pool.dict() for pool in formatted_pools],
            "message": "Successfully retrieved node pool information",
        }

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
