import logging
from instance_capability.models import ModelSpecs, NodePool
from instance_capability.config import cpu, t4, l4, approved_models

logger = logging.getLogger(__name__)


class NodePoolSelector:
    def __init__(self, model_specs: ModelSpecs, model_type: str = None):
        self.model_specs = model_specs
        self.model_type = model_type
        self.model_id = model_specs.model_id
        self.required_mem = model_specs.required_memory_gb
        self.cpu_threshold = cpu.specs.threshold_gb
        self.t4_threshold = t4.specs.threshold_gb
        self.l4_threshold = l4.specs.threshold_gb

        logger.info("Selecting Node Pool...")

    def select_node_pool(self) -> NodePool:
        """
        Select the appropriate node pool based on model specs
        """

        logger.info(
            f"Selecting node pool for model {self.model_id} with {self.required_mem} GB of memory"
        )

        if self.model_id in approved_models:
            return approved_models[self.model_id].node_pool
        # I don't want to run any text models on CPU
        if self.required_mem < self.cpu_threshold and self.model_type != "text":
            logger.info("Selected node pool: CPU")
            return cpu
        elif self.required_mem < self.t4_threshold:
            logger.info("Selected node pool: T4")
            return t4
        elif self.required_mem < self.l4_threshold:
            logger.info("Selected node pool: L4")
            return l4
        else:
            raise ValueError(
                f"No suitable node pool found for model requiring {self.required_mem} GB of memory"
            )
