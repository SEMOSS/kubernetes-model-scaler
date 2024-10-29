import logging
from fastapi import APIRouter, HTTPException
from pydantic_models.models import ModelRequest
from deployer.model_deployer import KubernetesModelDeployer

logger = logging.getLogger(__name__)
start_router = APIRouter()


@start_router.post("/start")
def start_model(request: ModelRequest):
    deployer = KubernetesModelDeployer(
        model_name=request.model_name,
        model_id=request.model_id,
        model_repo_name=request.model_repo_name,
        operation="deploy",
    )

    # Create a service for the model... Need to create service before registering model..
    try:
        deployer.create_service()
    except Exception as e:
        logger.error(f"Error creating service for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model service creation failed for {request.model_name}",
        )

    # Register the model in Zookeeper in a warming state
    try:
        deployer.register_warming_model()
    except Exception as e:
        logger.error(f"Error registering warming model {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model registration failed for warming model {request.model_name}",
        )

    # Create or find an existing persistent volume claim (PVC) for the model
    try:
        deployer.create_pvc()
    except Exception as e:
        logger.error(f"Error finding or creating PVC for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model PVC creation failed for {request.model_name}",
        )

    # Create a deployment for the model
    try:
        deployer.create_deployment()
    except Exception as e:
        logger.error(f"Error creating deployment for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Model deployment failed for {request.model_name}"
        )

    try:
        deployer.create_podmonitoring()
    except Exception as e:
        logger.error(f"Error creating pod monitoring for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model pod monitoring creation failed for {request.model_name}",
        )

    try:
        deployer.create_hpa()
    except Exception as e:
        logger.error(f"Error creating HPA for {request.model_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model HPA creation failed for {request.model_name}",
        )

    # Update Zookeeper with the model's ClusterIP
    if deployer.watch_deployment():
        deployer.register_active_model()
    else:
        logger.error(
            f"The deployment and service for {request.model_name} were likely successful but failed to monitor deployment."
        )
        raise HTTPException(
            status_code=500, detail="Model deployment failed due to monitoring failure"
        )

    return {"status": "Model deployed and registered successfully"}
