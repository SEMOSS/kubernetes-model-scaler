from instance_capability.models import (
    NodePoolSpec,
    NodePoolTier,
    NodePool,
    ApprovedModel,
)

cpu = NodePool(
    name=NodePoolTier.CPU,
    node_pool_name="cpu-sapphire-pool",
    specs=NodePoolSpec(
        memory_gb=6, vcpus=2, cpu_platform="Intel Sapphire Rapids", threshold_gb=3.0
    ),
)

t4 = NodePool(
    name=NodePoolTier.T4,
    node_pool_name="t4-gpu-pool",
    specs=NodePoolSpec(
        memory_gb=48,
        vcpus=14,
        gpu_type="nvidia-tesla-t4",
        gpu_memory_gb=14,
        cpu_platform="Intel Broadwell",
        threshold_gb=15.0,
    ),
)

l4 = NodePool(
    name=NodePoolTier.L4,
    node_pool_name="l4-gpu-pool",
    specs=NodePoolSpec(
        memory_gb=40,
        vcpus=10,
        gpu_type="nvidia-l4",
        gpu_memory_gb=22,
        cpu_platform="Intel Cascade Lake",
        threshold_gb=24.0,
    ),
)

# preapproved models that I can't run through the capability check
approved_models = {
    "urchade/gliner_multi-v2.1": ApprovedModel(can_run=True, node_pool=cpu),
    "urchade/gliner_large-v2": ApprovedModel(can_run=True, node_pool=cpu),
    "urchade/gliner_medium-v2": ApprovedModel(can_run=True, node_pool=cpu),
}
