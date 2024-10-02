import logging
from fastapi import APIRouter, HTTPException
from pydantic_models.models import ModelRequest
from deployer.kubernetes_deployer import KubernetesModelDeployer


logger = logging.getLogger(__name__)

start_router = APIRouter()


@start_router.post("/start")
def start_model(request: ModelRequest):
    """
    1. Create or find an existing persistent volume claim (PVC) for the model.
    2. Creates a deployment and service using KubernetesModelDeployer.
    3. Watches the deployment until it's ready.
    4. Updates Zookeeper with the model's ClusterIP.
    """

    deployer = KubernetesModelDeployer()

    # Create or find an existing persistent volume claim (PVC) for the model
    try:
        pvc_name = f"{request.model_name}-pvc"
        deployer.create_pvc()
    except Exception as e:
        logger.error(f"Error finding or creating PVC for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model PVC creation failed for {request.model_name}",
        )

    # Create a deployment for the model
    try:
        deployer.create_deployment(
            request.model_repo_name, request.model_id, request.model_name, pvc_name
        )
    except Exception as e:
        logger.error(f"Error creating deployment for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Model deployment failed for {request.model_name}"
        )

    # Create a service for the model
    try:
        deployer.create_service(request.model_id, request.model_name)
    except Exception as e:
        logger.error(f"Error creating service for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model service creation failed for {request.model_name}",
        )

    try:
        deployer.create_podmonitoring(request.model_id, request.model_name)
    except Exception as e:
        logger.error(f"Error creating pod monitoring for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model pod monitoring creation failed for {request.model_name}",
        )

    # Update Zookeeper with the model's ClusterIP
    if deployer.watch_deployment(request.model_name):
        deployer.update_zookeeper(request.model_id, request.model_name)
    else:
        logger.error(
            f"The deployment and service for {request.model_name} were likely successful but failed to monitor deployment."
        )
        raise HTTPException(
            status_code=500, detail="Model deployment failed due to monitoring failure"
        )

    return {"status": "Model deployed and registered successfully"}
