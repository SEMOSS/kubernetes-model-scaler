import logging
import asyncio
from contextlib import contextmanager
from fastapi import APIRouter
from pydantic_models.models import ModelRequest
from deployer2.deployer import Deployer

logger = logging.getLogger(__name__)
start_router_v2 = APIRouter()


@contextmanager
def deployment_manager(deployer):
    """
    Context manager to handle deployment cleanup on failure.
    If an exception occurs during deployment, performs cleanup operations
    to tear down any resources that were successfully created.
    """
    deployment_steps_completed = {
        "warming_registered": False,
        "yaml_applied": False,
        "load_balancer_created": False,
        "external_name_created": False,
        "ingress_created": False,
        "active_registered": False,
    }

    try:
        yield deployment_steps_completed
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")

        try:
            cleanup_deployment(deployer, deployment_steps_completed)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {str(cleanup_error)}")
        raise


def cleanup_deployment(deployer, completed_steps):
    """
    Clean up resources created during a failed deployment.
    Removes resources in the reverse order they were created.
    """
    logger.info("Starting cleanup of partially completed deployment")

    if completed_steps["active_registered"]:
        logger.info("Unregistering from active path")
        try:
            deployer.unregister_active_model()
        except Exception as e:
            logger.error(f"Failed to unregister active model: {str(e)}")

    # if completed_steps["ingress_created"]:
    #     logger.info("Removing ingress")
    #     try:
    #         deployer.remove_ingress()
    #     except Exception as e:
    #         logger.error(f"Failed to remove ingress: {str(e)}")

    # if completed_steps["external_name_created"]:
    #     logger.info("Removing external name service")
    #     try:
    #         deployer.remove_external_name_service()
    #     except Exception as e:
    #         logger.error(f"Failed to remove external name service: {str(e)}")

    if completed_steps["load_balancer_created"]:
        logger.info("Removing load balancer")
        try:
            deployer.remove_load_balancer()
        except Exception as e:
            logger.error(f"Failed to remove load balancer: {str(e)}")

    if completed_steps["yaml_applied"]:
        logger.info("Removing inference service")
        try:
            deployer.remove_inference_service()
        except Exception as e:
            logger.error(f"Failed to remove inference service: {str(e)}")

    if completed_steps["warming_registered"]:
        logger.info("Unregistering from warming path")
        try:
            deployer.unregister_warming_model()
        except Exception as e:
            logger.error(f"Failed to unregister warming model: {str(e)}")

    logger.info("Cleanup completed")


@start_router_v2.post("/start")
async def start_model(request: ModelRequest):
    def blocking_deployment():
        logger.info(
            f"Received request to deploy model {request.model} with an ID {request.model_id}, "
            f"a repo ID of {request.model_repo_id} and a type of {request.model_type}."
        )

        deployer = Deployer(
            model=request.model,
            model_id=request.model_id,
            model_repo_id=request.model_repo_id,
            model_type=request.model_type,
            operation="deploy",
        )

        # Using context manager to handle failures
        with deployment_manager(deployer) as deployment_steps:
            # Register the model as warming
            deployer.register_warming_model()
            deployment_steps["warming_registered"] = True

            # Deploy the model with kserve
            deployer.apply_yaml()
            deployment_steps["yaml_applied"] = True

            # Create the LoadBalancer
            deployer.create_load_balancer()
            deployment_steps["load_balancer_created"] = True

            # Create the ExternalName service
            # deployer.create_external_name_service()
            # deployment_steps["external_name_created"] = True

            # # Create the Ingress
            # deployer.create_ingress()
            # deployment_steps["ingress_created"] = True

            # Wait for the inference service to be ready
            model_ready = deployer.wait_for_model_ready()
            if not model_ready:
                logger.warning(
                    f"Model {request.model} deployment completed but model is not ready for inference"
                )

            # Register the model as active
            deployer.register_active_model()
            deployment_steps["active_registered"] = True

            return {"message": "Model deployment started successfully"}

    return await asyncio.to_thread(blocking_deployment)
