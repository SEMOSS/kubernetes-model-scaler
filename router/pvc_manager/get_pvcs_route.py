import logging
from fastapi import APIRouter
from pvc_manager.pvc_manager import PVCManager

logger = logging.getLogger(__name__)

get_pvc_router = APIRouter()


@get_pvc_router.get("/get-pvcs")
async def get_pvcs():
    logger.info("Getting PVCs")
    pvc_manager = PVCManager()
    return pvc_manager.pvc_config
