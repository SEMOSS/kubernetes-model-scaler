from typing import Optional
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from instance_capability.capability_check import ModelCompatibilityChecker

logger = logging.getLogger(__name__)
instance_check_router = APIRouter()


class ModelCheckRequest(BaseModel):
    model_id: str
    gpu_memory_gb: Optional[float] = 16.0
    dtype: Optional[str] = "float16"


@instance_check_router.post("/can-it-run")
async def check_instance_compatibility(request: ModelCheckRequest):
    """
    Check if the model can run on the specified GPU.

    Args:
        model_id: HuggingFace model ID
        gpu_memory_gb: GPU memory in GB
        dtype: Data type for the model (e.g. 'float32', 'float16', 'bfloat16', 'int8', 'int4')

    Returns:
        Dict containing compatibility check results and model details

    Raises:
        HTTPException:
            - 401: Authentication required (gated model)
            - 400: Invalid model type or parameters
            - 404: Model not found
            - 500: Unexpected server error
    """
    try:
        checker = ModelCompatibilityChecker(
            gpu_memory_gb=request.gpu_memory_gb, dtype=request.dtype
        )

        can_run, details = checker.check_compatibility(request.model_id)

        return {
            "can_run": can_run,
            "model_id": request.model_id,
            "gpu_memory_gb": request.gpu_memory_gb,
            "dtype": request.dtype,
            **details,
        }

    except ValueError as e:
        error_msg = str(e).lower()
        logger.error(f"ValueError encountered: {error_msg}")

        if "gated" in error_msg:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Authentication required",
                    "message": "This is a gated model. Please provide an access token.",
                },
            )
        elif "not found" in error_msg:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Model not found",
                    "message": f"Model {request.model_id} was not found on HuggingFace Hub",
                },
            )
        elif any(
            phrase in error_msg
            for phrase in [
                "not compatible with the transformers library",
                "does not have any library metadata",
                "config.json not found",
                "model should be a pretrained model",
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Unsupported model type",
                    "message": "This model is not compatible with the transformers library. Only transformer-based models are supported.",
                },
            )
        else:
            raise HTTPException(
                status_code=400, detail={"error": "Invalid request", "message": str(e)}
            )

    except ImportError as e:
        logger.error(f"ImportError encountered: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unsupported model type",
                "message": "This model requires custom code or is not compatible with the transformers library. Only standard transformer-based models are supported.",
            },
        )

    except Exception as e:
        logger.error(
            f"Unexpected error checking model compatibility: {str(e)}, Type: {type(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": f"An unexpected error occurred while checking model compatibility: {str(e)}",
            },
        )
