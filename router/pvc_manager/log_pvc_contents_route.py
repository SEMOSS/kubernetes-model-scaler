import logging
from fastapi import APIRouter
from pvc_manager.pvc_manager import PVCManager

logger = logging.getLogger(__name__)

pvc_contents_router = APIRouter()


@pvc_contents_router.get("/log-pvc-contents")
async def get_pvc_contents():
    logger.info("Getting PVC contents")
    pvc_manager = PVCManager()
    pvcs = pvc_manager.pvcs
    for pvc in pvcs:
        pvc_manager.log_directory_tree(pvc)
    return "PVC contents logged"
