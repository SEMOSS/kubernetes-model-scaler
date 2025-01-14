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

import torch
from accelerate.commands.estimate import create_empty_model, calculate_maximum_sizes
from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError
from typing import Optional, Dict, Union, Tuple
from urllib.parse import urlparse


class ModelCompatibilityChecker:
    """
    Class to check if a HuggingFace model can run on given GPU infrastructure.
    """

    # Memory multipliers for different precision types
    DTYPE_MODIFIER = {"float32": 1, "float16": 2, "bfloat16": 2, "int8": 4, "int4": 8}

    def __init__(self, gpu_memory_gb: float = 16.0, dtype: str = "float16"):
        """
        Initialize the checker with GPU specifications.
        Args:
            gpu_memory_gb: Available GPU memory in GB
            dtype: Model precision type (float32, float16, bfloat16, int8, int4)
        """
        self.gpu_memory_gb = gpu_memory_gb
        if dtype not in self.DTYPE_MODIFIER:
            raise ValueError(
                f"Unsupported dtype: {dtype}. Must be one of {list(self.DTYPE_MODIFIER.keys())}"
            )
        self.dtype = dtype

    def _extract_model_name(self, name: str) -> str:
        """Extract model name from URL if needed."""
        try:
            result = urlparse(name)
            if all([result.scheme, result.netloc]):
                return result.path[1:]
        except Exception:
            pass
        return name

    def _translate_llama2_name(self, name: str) -> str:
        """Translate Llama 2 model names to HF format if needed."""
        if "meta-llama" in name and "Llama-2" in name and not name.endswith("-hf"):
            return name + "-hf"
        return name

    def _calculate_memory_requirements(
        self, model: torch.nn.Module
    ) -> Dict[str, float]:
        """
        Calculate memory requirements for the model.
        Returns:
            Dict with memory requirements in GB for different operations
        """
        total_size, largest_layer = calculate_maximum_sizes(model)
        num_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)

        # Apply dtype modifier
        modifier = self.DTYPE_MODIFIER[self.dtype]
        total_size = total_size / modifier

        total_size_gb = total_size / (1024**3)

        return {
            "total_size_gb": total_size_gb,
            "inference_gb": total_size_gb * 1.2,
            "training_gb": total_size_gb * 4,
            "parameters_billion": num_parameters / 1e9,
        }

    def check_compatibility(
        self,
        model_name: str,
        access_token: Optional[str] = None,
        mode: str = "inference",
    ) -> Tuple[bool, Dict[str, Union[float, str]]]:
        """
        Check if the model can run on the specified GPU.

        Args:
            model_name: HuggingFace model name or URL
            access_token: HF access token for gated models
            mode: Operation mode ('inference' or 'training')

        Returns:
            Tuple of (can_run: bool, details: Dict)
        """
        model_name = self._extract_model_name(model_name)
        model_name = self._translate_llama2_name(model_name)

        try:
            model = create_empty_model(
                model_name,
                library_name="transformers",
                trust_remote_code=True,
                access_token=access_token,
            )

            # Calculate memory requirements
            memory_req = self._calculate_memory_requirements(model)

            required_memory = (
                memory_req["training_gb"]
                if mode == "training"
                else memory_req["inference_gb"]
            )

            can_run = required_memory <= self.gpu_memory_gb

            details = {
                "can_run": can_run,
                "required_memory_gb": required_memory,
                "available_memory_gb": self.gpu_memory_gb,
                "mode": mode,
                "dtype": self.dtype,
                "model_parameters_b": memory_req["parameters_billion"],
            }

            return can_run, details

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


if __name__ == "__main__":
    checker = ModelCompatibilityChecker(gpu_memory_gb=16.0, dtype="float16")

    can_run, details = checker.check_compatibility(
        model_name="microsoft/Phi-3.5-mini-instruct", mode="inference"
    )

    print(f"Can run: {can_run}")
    print(f"Details: {details}")
