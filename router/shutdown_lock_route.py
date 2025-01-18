import logging
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, HTTPException
from redis_manager.redis_manager import RedisManager

logger = logging.getLogger(__name__)
shutdown_lock_router = APIRouter()


class ShutdownLockRequest(BaseModel):
    model_id: str
    lock: str

    @field_validator("lock")
    def validate_lock(cls, value):
        value = value.lower()
        if value not in {"true", "false"}:
            raise ValueError("lock must be 'true' or 'false'")
        return value


@shutdown_lock_router.post("/shutdown-lock")
async def shutdown_lock(request: ShutdownLockRequest):
    """
    Locks or unlocks the shutdown state for a model.
    """
    redis_manager = RedisManager()
    try:
        await redis_manager.update_model_lock(request.model_id, request.lock)
        return {
            "message": f"Successfully updated shutdown lock for model {request.model_id}"
        }
    except KeyError as e:
        logger.error(f"Model not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Redis service unavailable")
    except Exception as e:
        logger.error(f"Error updating shutdown lock: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update shutdown lock")
