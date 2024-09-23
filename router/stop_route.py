from fastapi import APIRouter, HTTPException
from deployer.kubernetes_deployer import KubernetesModelDeployer
import logging

logger = logging.getLogger(__name__)

stop_router = APIRouter()


@stop_router.post("/stop")
def stop_model(model_id: str):
    """
    1. Maps the model_id to a model_name.
    2. Deletes the deployment.
    3. Deletes the service.
    4. Removes the model's entry from Zookeeper.
    """
    deployer = KubernetesModelDeployer()
    # TODO: Implement get_model_name_from_id
    try:
        model_name = deployer.get_model_name_from_id(model_id)
    except Exception as e:
        logger.error(f"Error mapping model name from id for {model_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get model name for {model_id}"
        )

    try:
        deployer.delete_deployment(model_name)
    except Exception as e:
        logger.error(f"Error deleting deployment for {model_name}/{model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete deployment for {model_name}/{model_id}",
        )

    try:
        deployer.delete_service(model_name)
    except Exception as e:
        logger.error(f"Error deleting service for {model_name}/{model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete service for {model_name}/{model_id}",
        )

    try:
        deployer.remove_zookeeper(model_id)
    except Exception as e:
        logger.error(f"Error removing Zookeeper entry for {model_name}/{model_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove Zookeeper entry for {model_name}/{model_id}",
        )
    return {"status": "Model deployment stopped and unregistered successfully"}
