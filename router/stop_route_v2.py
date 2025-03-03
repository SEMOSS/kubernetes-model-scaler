import logging
from fastapi import APIRouter, HTTPException
from deployer2.deployer import Deployer

logger = logging.getLogger(__name__)
stop_router_v2 = APIRouter()


@stop_router_v2.post("/stop")
async def stop_model(model_id: str = None, model: str = None):
    logger.info(f"Received request to stop model {model} with an ID {model_id}")
    try:
        deployer = Deployer(
            operation="delete",
            model_id=model_id,
            model=model,
            model_repo_id="",
            model_type="",
        )

        # Removing the InferenceService from the standard cluster
        deployer.remove_inference_service()

        # Removing Load Balancer from the standard cluster
        deployer.remove_load_balancer()

        # Removing the ExternalName service from autopilot cluster
        deployer.remove_external_name_service()

        # Removing the Ingress from the autopilot cluster
        deployer.remove_ingress()

        # I think I can attempt to remove both here regardless if they exist??
        # Unregister the model from Zookeeper warming path
        deployer.unregister_warming_model()
        # Unregister the model from Zookeeper active path
        deployer.unregister_active_model()

        return {"message": "Model stopped successfully"}
    except Exception as e:
        logger.error(f"Failed to stop model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop model: {str(e)}")
