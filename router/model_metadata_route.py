import logging
import pathlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
metadata_router = APIRouter()


class MetadataRequest(BaseModel):
    model: str
    model_id: str


class ModelMetadata(BaseModel):
    usage: str
    startup_time: int


@metadata_router.post("/model-metadata")
async def get_model_metadata(request: MetadataRequest) -> ModelMetadata:
    model = request.model
    model_id = request.model_id

    logger.info(f"Received request to get metadata for model {model}")

    metadata = ModelMetadata(usage="Not available", startup_time=0)

    try:
        model_usage_path = (
            pathlib.Path(__file__).parent.parent / "resources" / "usage" / f"{model}.md"
        )
        if model_usage_path.exists():
            with open(model_usage_path, "r", encoding="utf-8") as f:
                content = f.read()
                metadata.usage = content.replace("{ENGINE_ID}", model_id)
        else:
            logger.warning(
                f"Usage documentation not found for model {model} on path {model_usage_path}"
            )
        metadata.startup_time = 0
        return metadata
    except Exception as e:
        logger.error(f"Failed to get model metadata: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get model metadata: {str(e)}"
        )
