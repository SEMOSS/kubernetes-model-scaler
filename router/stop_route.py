from fastapi import APIRouter, HTTPException
from deployer.model_deployer import KubernetesModelDeployer
import logging

logger = logging.getLogger(__name__)

stop_router = APIRouter()


@stop_router.post("/stop")
async def stop_model(model_id: str = None, model: str = None):
    """
    Stops the model deployment by deleting the Kubernetes deployment, service, and zookeeper entry.
    Accepts either model_id or model_name to identify the model.
    """
    if not model_id and not model:
        raise HTTPException(
            status_code=400, detail="Either model_id or model_name must be provided"
        )

    deployer = KubernetesModelDeployer(
        operation="delete",
        model_id=model_id,
        model=model,
        model_repo_id="",
        model_type="",
    )

    try:
        deployer.delete_deployment()
        deployer.delete_service()
        deployer.delete_podmonitoring()
        deployer.delete_hpa()
        deployer.unregister_active_model()
        # await deployer.delete_deployment_status()
    except Exception as e:
        logger.error(f"Error stopping model {model}/{model_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to stop model {model}/{model_id}"
        )

    return {"status": "Model deployment stopped and unregistered successfully"}
