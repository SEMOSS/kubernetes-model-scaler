import logging
from fastapi import APIRouter, HTTPException
from zk_manager.zk_manager import ZKManager

logger = logging.getLogger(__name__)
zk_info_router = APIRouter()


@zk_info_router.get("/zk-info")
async def zk_info():
    """
    Retrieves information about models in ZooKeeper.
    """
    zk_manager = ZKManager()
    try:
        models = zk_manager.get_all_models()
        warming_models = models.get("warming", [])
        active_models = models.get("active", [])
        cooling_models = models.get("cooling", [])
        deployer_status = zk_manager.get_deployer_status()
        return {
            "active_models": active_models,
            "warming_models": warming_models,
            "cooling_models": cooling_models,
            "deployer_status": deployer_status,
        }
    except Exception as e:
        logger.error(f"Error retrieving ZooKeeper model info: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve ZooKeeper model info"
        )
