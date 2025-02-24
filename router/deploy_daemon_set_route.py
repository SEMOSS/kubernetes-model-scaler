import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from auth.auth import verify_api_key
from daemon_set_deployer.daemon_set_deployer import DaemonSetDeployer
from pydantic import BaseModel

logger = logging.getLogger(__name__)
deploy_daemon_set_router = APIRouter()


class DaemonSetDeployRequest(BaseModel):
    docker_tag: str


@deploy_daemon_set_router.post("/deploy", dependencies=[Depends(verify_api_key)])
async def deploy_daemon_set(deploy_request: DaemonSetDeployRequest):
    try:
        deployer = DaemonSetDeployer(
            docker_tag=deploy_request.docker_tag,
        )

        deployed_daemon_sets = deployer.deploy_daemon_sets()

        return {
            "status": "success",
            "message": f"Successfully deployed DaemonSets with Docker tag {deploy_request.docker_tag}",
            "deployed_daemon_sets": deployed_daemon_sets,
            "docker_tag": deploy_request.docker_tag,
        }
    except Exception as e:
        logger.error(f"Failed to deploy DaemonSets: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, detail=f"Failed to deploy DaemonSets: {str(e)}"
        )
