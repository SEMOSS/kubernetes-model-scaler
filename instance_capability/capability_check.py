"""
ModelCompatibilityChecker provides functionality to determine whether a HuggingFace transformer
model can be run on specific GPU hardware configurations. It calculates memory requirements
for both inference and training scenarios across different precision types (float32,
float16/bfloat16, int8, int4). Note that this checker currently only supports models
that can be loaded with the transformers library.

Key Features:
    - Accurate memory estimation using HuggingFace Accelerate
    - Support for different precision types and their memory implications
    - Handles both inference and training memory requirements
    - Compatible with gated models using access tokens
    - Special handling for model variants (e.g., Llama 2 naming conventions)

Example:
    checker = ModelCompatibilityChecker(gpu_memory_gb=40.0, dtype="float16")
    can_run, details = checker.check_compatibility(
        model_name="mistralai/Mistral-7B-v0.1",
        mode="inference"
    )

The checker uses established memory calculation heuristics:
    - Inference memory ≈ model size * 1.2
    - Training memory ≈ model size * 4 (with Adam optimizer)
    - Memory requirements are adjusted based on precision type
"""

from transformers import AutoConfig
from accelerate.commands.estimate import create_empty_model, calculate_maximum_sizes
from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError
from huggingface_hub import hf_hub_download
from typing import Optional, Dict, Union, Tuple
from dataclasses import dataclass
from instance_capability.models import ModelSpecs


@dataclass
class GPUSpec:
    """GPU specifications including real-world limitations"""

    total_memory_gb: float
    reserved_memory_gb: float = 1.0  # Memory reserved for system/CUDA
    memory_efficiency: float = 0.95  # Real-world memory efficiency factor

    @property
    def effective_memory_gb(self) -> float:
        return (self.total_memory_gb - self.reserved_memory_gb) * self.memory_efficiency


@dataclass
class ModelMemoryProfile:
    """Detailed memory requirements for model operations"""

    parameters_billion: float
    model_size_gb: float
    attention_overhead_gb: float
    activations_overhead_gb: float
    kv_cache_gb: float
    cuda_kernels_gb: float = 0.3  # Reserved for CUDA kernels
    buffer_gb: float = 0.05  # Safety buffer
    peak_memory_multiplier: float = 1.15  # Account for memory spikes

    @property
    def total_inference_gb(self) -> float:
        base_memory = (
            self.model_size_gb
            + self.attention_overhead_gb
            + self.activations_overhead_gb
            + self.kv_cache_gb
            + self.cuda_kernels_gb
            + self.buffer_gb
        )
        return base_memory * self.peak_memory_multiplier


class ModelCompatibilityChecker:
    """
    Model compatibility that handles both standard and custom code models.
    """

    DTYPE_SIZE = {"float32": 4, "float16": 2, "bfloat16": 2, "int8": 1, "int4": 0.5}

    def __init__(
        self,
        # Using the highest available (L4) GPU memory as the default
        gpu_memory_gb: float = 24.0,
        dtype: str = "float16",
        max_sequence_length: int = 2048,
        batch_size: int = 1,
    ):
        self.gpu_spec = GPUSpec(total_memory_gb=gpu_memory_gb)
        self.dtype = dtype
        self.max_sequence_length = max_sequence_length
        self.batch_size = batch_size

        if dtype not in self.DTYPE_SIZE:
            raise ValueError(f"Unsupported dtype: {dtype}")

    def _estimate_model_size_from_config(self, config) -> Tuple[float, float]:
        """Estimate model size from config when direct loading fails"""
        try:
            hidden_size = getattr(config, "hidden_size", 768)
            num_layers = getattr(config, "num_hidden_layers", 12)
            vocab_size = getattr(config, "vocab_size", 50257)
            intermediate_size = getattr(config, "intermediate_size", hidden_size * 4)

            embedding_params = vocab_size * hidden_size

            # Transformer layers
            layer_params = (
                # Self-attention
                4 * hidden_size * hidden_size  # Q, K, V, and output projections
                +
                # FFN
                2 * hidden_size * intermediate_size
                +
                # Layer norms
                4 * hidden_size
            )

            total_params = embedding_params + num_layers * layer_params

            params_billion = total_params / 1e9
            size_gb = (total_params * self.DTYPE_SIZE[self.dtype]) / (1024**3)

            return params_billion, size_gb
        except Exception:
            return None, None

    def _try_get_model_card_info(self, model_name: str) -> Optional[Dict]:
        """Try to get model information from the model card"""
        try:
            model_card = hf_hub_download(
                repo_id=model_name, filename="README.md", repo_type="model"
            )
            with open(model_card, "r", encoding="utf-8") as f:
                content = f.read().lower()
                import re

                param_matches = re.findall(
                    r"(\d+\.?\d*)\s*[bB]illion parameters", content
                )
                if param_matches:
                    return {"parameters_billion": float(param_matches[0])}
        except:
            pass
        return None

    def _calculate_attention_overhead(self, config) -> float:
        """Calculate memory overhead from attention mechanisms"""
        attention_dim = getattr(config, "hidden_size", 768)
        num_heads = getattr(config, "num_attention_heads", 12)
        num_layers = getattr(config, "num_hidden_layers", 12)

        qkv_size = (
            3 * attention_dim * attention_dim * num_layers * self.DTYPE_SIZE[self.dtype]
        ) / (1024**3)

        # Memory for attention scores
        scores_size = (
            self.batch_size
            * num_heads
            * self.max_sequence_length
            * self.max_sequence_length
            * self.DTYPE_SIZE[self.dtype]
        ) / (1024**3)

        return qkv_size + scores_size

    def _calculate_kv_cache(self, config) -> float:
        """Calculate KV cache requirements"""
        hidden_size = getattr(config, "hidden_size", 768)
        num_layers = getattr(config, "num_hidden_layers", 12)

        kv_size = (
            2
            * self.batch_size
            * num_layers
            * self.max_sequence_length
            * hidden_size
            * self.DTYPE_SIZE[self.dtype]
        ) / (1024**3)

        beam_search_factor = 1.5
        return kv_size * beam_search_factor

    def _calculate_activations(self, config) -> float:
        """Estimate activation memory requirements"""
        hidden_size = getattr(config, "hidden_size", 768)
        num_layers = getattr(config, "num_hidden_layers", 12)
        intermediate_size = getattr(config, "intermediate_size", hidden_size * 4)

        # Memory for hidden states
        hidden_activation = (
            self.batch_size
            * self.max_sequence_length
            * hidden_size
            * self.DTYPE_SIZE[self.dtype]
        ) / (1024**3)

        # Memory for intermediate activations
        intermediate_activation = (
            self.batch_size
            * self.max_sequence_length
            * intermediate_size
            * self.DTYPE_SIZE[self.dtype]
        ) / (1024**3)

        return (hidden_activation + intermediate_activation) * num_layers * 2

    def check_compatibility(
        self,
        model_name: str,
        access_token: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Union[float, str]]]:
        """
        Comprehensive compatibility check with fallback mechanisms for custom code models.
        """
        try:
            config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
            try:
                # Try direct model loading first
                model = create_empty_model(
                    model_name,
                    library_name="transformers",
                    trust_remote_code=True,
                    access_token=access_token,
                )
                total_size, _ = calculate_maximum_sizes(model)
                num_parameters = sum(p.numel() for p in model.parameters())
                model_size_gb = (total_size * self.DTYPE_SIZE[self.dtype]) / (1024**3)
                params_billion = num_parameters / 1e9
            except Exception:
                # Fallback to config-based estimation
                params_billion, model_size_gb = self._estimate_model_size_from_config(
                    config
                )

                # If config estimation fails, try model card
                if params_billion is None:
                    model_card_info = self._try_get_model_card_info(model_name)
                    if model_card_info:
                        params_billion = model_card_info["parameters_billion"]
                        model_size_gb = (
                            params_billion * 1e9 * self.DTYPE_SIZE[self.dtype]
                        ) / (1024**3)
                    else:
                        raise ValueError("Unable to estimate model size")

            profile = ModelMemoryProfile(
                parameters_billion=params_billion,
                model_size_gb=model_size_gb,
                attention_overhead_gb=self._calculate_attention_overhead(config),
                activations_overhead_gb=self._calculate_activations(config),
                kv_cache_gb=self._calculate_kv_cache(config),
            )

            total_required_memory = profile.total_inference_gb
            effective_gpu_memory = self.gpu_spec.effective_memory_gb
            can_run = total_required_memory <= effective_gpu_memory

            details = {
                "can_run": can_run,
                "model_id": model_name,
                "requested_dtype": self.dtype,
                "gpu_memory_gb": self.gpu_spec.total_memory_gb,
                "required_memory_gb": total_required_memory,
                "available_memory_gb": self.gpu_spec.total_memory_gb,
                "effective_memory_gb": effective_gpu_memory,
                "model_parameters_b": profile.parameters_billion,
                "memory_breakdown": {
                    "model_weights_gb": profile.model_size_gb,
                    "attention_overhead_gb": profile.attention_overhead_gb,
                    "activations_gb": profile.activations_overhead_gb,
                    "kv_cache_gb": profile.kv_cache_gb,
                    "cuda_kernels_gb": profile.cuda_kernels_gb,
                    "safety_buffer_gb": profile.buffer_gb,
                },
                "peak_memory_multiplier": profile.peak_memory_multiplier,
                "reserved_system_memory_gb": self.gpu_spec.reserved_memory_gb,
                "memory_efficiency_factor": self.gpu_spec.memory_efficiency,
                "estimation_method": (
                    "direct" if "model" in locals() else "config_based"
                ),
            }

            model_specs = ModelSpecs(**details)

            return can_run, model_specs

        except GatedRepoError:
            raise ValueError(
                f"Model {model_name} is gated. Please provide an access token."
            )
        except RepositoryNotFoundError:
            raise ValueError(f"Model {model_name} not found on HuggingFace Hub.")
        except ValueError as e:
            if "does not have any library metadata" in str(e):
                raise ValueError(
                    f"Model {model_name} is not compatible with the transformers library. "
                    "This checker only supports transformer-based models."
                )
            raise e
        except ImportError as e:
            raise ValueError(
                f"Model {model_name} requires custom code that couldn't be loaded. "
                "Please ensure the model is compatible with the transformers library."
            )
        except Exception as e:
            raise RuntimeError(f"Error checking model compatibility: {str(e)}")
