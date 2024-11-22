import logging
from fastapi import APIRouter
from pvc_manager.pvc_manager import PVCManager
from pydantic import BaseModel

logger = logging.getLogger(__name__)

remove_model_router = APIRouter()


class RemoveModelRequest(BaseModel):
    model: str


class ResponseModel(BaseModel):
    success: bool
    message: str


@remove_model_router.post("/remove-model", response_model=ResponseModel)
async def remove_model(request: RemoveModelRequest):
    logger.info(f"Recieved request to remove model {request.model}")
    pvc_manager = PVCManager()
    response = pvc_manager.remove_model_dir(request.model)
    return {"success": response[0], "message": response[1]}
