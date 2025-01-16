import asyncio
import logging
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException
from pydantic_models.models import ModelRequest
from deployer.model_deployer import KubernetesModelDeployer
from dataclasses import dataclass

logger = logging.getLogger(__name__)
start_router = APIRouter()


@dataclass
class DeploymentState:
    """Tracks which resources have been created during deployment"""

    service_created: bool = False
    deployment_created: bool = False
    pod_monitoring_created: bool = False
    hpa_created: bool = False


class ZookeeperDeploymentManager:
    def cleanup_resources(self, deployer, state: DeploymentState):
        """
        Cleanup all created resources in reverse order of creation
        """
        if state.hpa_created:
            try:
                deployer.delete_hpa()
                logger.info(
                    f"Successfully cleaned up HPA for model {deployer.model_id}"
                )
            except Exception as e:
                logger.error(f"Failed to clean up HPA: {str(e)}")

        if state.pod_monitoring_created:
            try:
                deployer.delete_podmonitoring()
                logger.info(
                    f"Successfully cleaned up pod monitoring for model {deployer.model_id}"
                )
            except Exception as e:
                logger.error(f"Failed to clean up pod monitoring: {str(e)}")

        if state.deployment_created:
            try:
                deployer.delete_deployment()
                logger.info(
                    f"Successfully cleaned up deployment for model {deployer.model_id}"
                )
            except Exception as e:
                logger.error(f"Failed to clean up deployment: {str(e)}")

        try:
            deployer.unregister_warming_model()
            logger.info(
                f"Successfully cleaned up warming state for model {deployer.model_id}"
            )
        except Exception as e:
            logger.error(f"Failed to clean up warming state: {str(e)}")

        if state.service_created:
            try:
                deployer.delete_service()
                logger.info(
                    f"Successfully cleaned up service for model {deployer.model_id}"
                )
            except Exception as e:
                logger.error(f"Failed to clean up service: {str(e)}")

    @contextmanager
    def deployment_context(self, deployer):
        """
        Context manager to handle resource creation and cleanup during deployment.
        Tracks which resources are created and ensures proper cleanup on failure.
        """
        state = DeploymentState()

        try:
            deployer.create_service()
            state.service_created = True

            deployer.register_warming_model()
            yield state

        except Exception as e:
            logger.error(f"Deployment failed for model {deployer.model_id}: {str(e)}")
            self.cleanup_resources(deployer, state)
            raise


@start_router.post("/start")
async def start_model(request: ModelRequest):
    logger.info(
        f"Received request to deploy model {request.model} with an ID {request.model_id}, "
        f"a repo ID of {request.model_repo_id} and a type of {request.model_type}."
    )
    deployer = KubernetesModelDeployer(
        model=request.model,
        model_id=request.model_id,
        model_repo_id=request.model_repo_id,
        model_type=request.model_type,
        operation="deploy",
    )

    zk_manager = ZookeeperDeploymentManager()

    deployer.check_model_files_exist()

    with zk_manager.deployment_context(deployer) as state:
        try:
            deployer.create_pvc()

            deployer.create_deployment()
            state.deployment_created = True

            deployer.create_podmonitoring()
            state.pod_monitoring_created = True

            deployer.create_hpa()
            state.hpa_created = True

            if deployer.watch_deployment():
                # Checking if the container is healthy..
                is_healthy = await deployer.check_until_healthy()
                if not is_healthy:
                    raise Exception("Model deployment failed health check")

                # Checking for when the model finally loads..
                is_model_loaded = await deployer.check_until_model_loaded()
                if not is_model_loaded:
                    raise Exception("Model deployment failed model load check")

                deployer.register_active_model()
            else:
                raise Exception("Deployment monitoring failed")

        except Exception as e:
            logger.error(f"Deployment process failed: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Model deployment failed: {str(e)}"
            )

    return {"status": "Model deployed and registered successfully"}
