from pydantic import BaseModel
from typing import Dict, Optional, Union
from enum import Enum


class NodePoolTier(Enum):
    CPU = "cpu"
    T4 = "t4"
    L4 = "l4"


class MemoryBreakdown(BaseModel):
    model_weights_gb: float
    attention_overhead_gb: float
    activations_gb: float
    kv_cache_gb: float
    cuda_kernels_gb: float
    safety_buffer_gb: float


class ModelSpecs(BaseModel):
    can_run: bool
    model_id: str
    requested_dtype: str
    required_memory_gb: float
    available_memory_gb: float
    effective_memory_gb: float
    model_parameters_b: float
    memory_breakdown: Union[MemoryBreakdown, Dict[str, float]]
    peak_memory_multiplier: float
    reserved_system_memory_gb: float
    memory_efficiency_factor: float
    estimation_method: str


class NodePoolSpec(BaseModel):
    memory_gb: float
    vcpus: int
    gpu_type: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    cpu_platform: str
    threshold_gb: float


class NodePool(BaseModel):
    name: NodePoolTier
    node_pool_name: str
    specs: NodePoolSpec


class ApprovedModel(BaseModel):
    can_run: bool
    node_pool: NodePool
