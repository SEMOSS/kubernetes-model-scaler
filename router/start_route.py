import logging
from fastapi import APIRouter, HTTPException
from pydantic_models.models import ModelRequest
from deployer.kubernetes_deployer import KubernetesModelDeployer


logger = logging.getLogger(__name__)

start_router = APIRouter()


@start_router.post("/start")
def start_model(request: ModelRequest):
    """
    1. Creates a deployment and service using KubernetesModelDeployer.
    2. Watches the deployment until it's ready.
    3. Updates Zookeeper with the model's ClusterIP.
    """

    deployer = KubernetesModelDeployer()
    try:
        deployer.create_deployment(
            request.model_repo_name, request.model_id, request.model_name
        )
    except Exception as e:
        logger.error(f"Error creating deployment for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Model deployment failed for {request.model_name}"
        )

    try:
        deployer.create_service(request.model_id, request.model_name)
    except Exception as e:
        logger.error(f"Error creating service for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model service creation failed for {request.model_name}",
        )

    if deployer.watch_deployment(request.model_name):
        deployer.update_zookeeper(request.model_id, request.model_name)
        return {"status": "Model deployed and registered successfully"}
    else:
        logger.error(
            f"The deployment and service for {request.model_name} were likely successful but failed to monitor deployment."
        )
        raise HTTPException(
            status_code=500, detail="Model deployment failed due to monitoring failure"
        )
