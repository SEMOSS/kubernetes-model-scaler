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

        # Register model as cooling first and remember its original state
        original_state = deployer.register_cooling_model()
        logger.info(
            f"Model {model_id} registered as cooling (original state: {original_state})"
        )

        try:
            # Removing the InferenceService from the standard cluster
            deployer.remove_inference_service()

            # Removing Load Balancer from the standard cluster
            deployer.remove_load_balancer()

            # # Removing the ExternalName service from autopilot cluster
            # deployer.remove_external_name_service()

            # # Removing the Ingress from the autopilot cluster
            # deployer.remove_ingress()

            # Unregister from all states after successful removal
            deployer.unregister_warming_model()
            deployer.unregister_active_model()
            deployer.unregister_cooling_model()

            return {"message": "Model stopped successfully"}
        except Exception as e:
            # If any operation fails, restore the original state
            logger.warning(
                f"Model stop operation failed, attempting to restore original state: {str(e)}"
            )
            if deployer.restore_original_state():
                logger.info(f"Successfully restored model {model_id} to original state")
            else:
                logger.error(
                    f"Failed to restore model {model_id} to original state - manual intervention may be required"
                )
            # Re-raise the exception to be caught by the outer try-except
            raise

    except Exception as e:
        logger.error(f"Failed to stop model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop model: {str(e)}")
