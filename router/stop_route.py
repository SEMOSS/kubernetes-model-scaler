from fastapi import APIRouter, HTTPException
from deployer.kubernetes_deployer import KubernetesModelDeployer
import logging

logger = logging.getLogger(__name__)

stop_router = APIRouter()


@stop_router.post("/stop")
def stop_model(model_id: str = None, model_name: str = None):
    """
    Stops the model deployment by deleting the Kubernetes deployment, service, and zookeeper entry.
    Accepts either model_id or model_name to identify the model.
    """
    deployer = KubernetesModelDeployer()

    if not model_id and not model_name:
        raise HTTPException(
            status_code=400, detail="Either model_id or model_name must be provided"
        )

    # Retrieve model_name and model_id if one is missing
    try:
        if model_id and not model_name:
            model_name = deployer.get_model_name_from_id(model_id)
        elif model_name and not model_id:
            model_id = deployer.get_model_id_from_name(model_name)
    except Exception as e:
        logger.error(f"Error retrieving model_id or model_name: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve model information: {e}"
        )

    try:
        deployer.delete_deployment(model_name)
        deployer.delete_service(model_name)
        deployer.remove_zookeeper(model_id)
        deployer.delete_podmonitoring(model_name)
        deployer.delete_hpa(model_name)
    except Exception as e:
        logger.error(f"Error stopping model {model_name}/{model_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to stop model {model_name}/{model_id}"
        )

    return {"status": "Model deployment stopped and unregistered successfully"}
