import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from auth.auth import verify_api_key
from daemon_set_deployer.daemon_set_deployer import DaemonSetDeployer

logger = logging.getLogger(__name__)
destroy_daemon_set_router = APIRouter()


@destroy_daemon_set_router.post("/destroy", dependencies=[Depends(verify_api_key)])
async def destroy_daemon_set():
    try:
        deployer = DaemonSetDeployer(docker_tag="xxxxx")

        destroyed_daemon_sets = deployer.destroy_all_daemon_sets()

        return {
            "status": "success",
            "message": "Successfully destroyed DaemonSets",
            "destroyed_daemon_sets": destroyed_daemon_sets,
        }
    except Exception as e:
        logger.error(f"Failed to destroy DaemonSets: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, detail=f"Failed to destroy DaemonSets: {str(e)}"
        )
