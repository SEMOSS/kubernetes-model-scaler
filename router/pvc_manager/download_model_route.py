import logging
from fastapi import APIRouter
from pvc_manager.pvc_manager import PVCManager
from pydantic import BaseModel

logger = logging.getLogger(__name__)

download_model_router = APIRouter()


class DownloadModelRequest(BaseModel):
    model_path: str
    repo_id: str


class ResponseModel(BaseModel):
    success: bool
    message: str


@download_model_router.post("/download-model", response_model=ResponseModel)
async def download_model(request: DownloadModelRequest):
    logger.info(f"Recieved request to download model {request.model_path}")
    pvc_manager = PVCManager()
    response = pvc_manager.download_manager.download_model(
        request.model_path, request.repo_id
    )
    return {"success": response[0], "message": response[1]}
