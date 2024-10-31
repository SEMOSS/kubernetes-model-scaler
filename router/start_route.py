import logging
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException
from pydantic_models.models import ModelRequest
from deployer.model_deployer import KubernetesModelDeployer

logger = logging.getLogger(__name__)
start_router = APIRouter()


class ZookeeperDeploymentManager:
    @contextmanager
    def deployment_context(self, deployer):
        """
        Context manager to handle both service creation and warming state of a model deployment.
        Ensures cleanup of both service and warming state in case of deployment failure.
        """
        service_created = False
        try:
            # Always need to create service first to use Zookeeper
            deployer.create_service()
            service_created = True

            # Registering model in warming state
            deployer.register_warming_model()
            yield

        except Exception as e:
            # On failure we need to clean up the service and warming state
            logger.error(f"Deployment failed for model {deployer.model_id}: {str(e)}")

            # Removing model from warming state
            try:
                deployer.unregister_warming_model()
                logger.info(
                    f"Successfully cleaned up warming state for model {deployer.model_id}"
                )
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up warming state: {str(cleanup_error)}")

            # Removing service
            if service_created:
                try:
                    deployer.delete_service()
                    logger.info(
                        f"Successfully cleaned up service for model {deployer.model_id}"
                    )
                except Exception as service_cleanup_error:
                    logger.error(
                        f"Failed to clean up service: {str(service_cleanup_error)}"
                    )

            raise  # Re-raising original exception


@start_router.post("/start")
def start_model(request: ModelRequest):
    deployer = KubernetesModelDeployer(
        model_name=request.model_name,
        model_id=request.model_id,
        model_repo_name=request.model_repo_name,
        operation="deploy",
    )

    zk_manager = ZookeeperDeploymentManager()

    # Using the context manager to handle service creation and warming state
    with zk_manager.deployment_context(deployer):
        try:
            # Creating or finding PVC (almost always find)
            deployer.create_pvc()

            # Creating deployment
            deployer.create_deployment()

            # Creating monitoring
            deployer.create_podmonitoring()

            # Creating HPA
            deployer.create_hpa()

            # Adding model to active state and removing it from warming state
            if deployer.watch_deployment():
                deployer.register_active_model()
            else:
                raise Exception("Deployment monitoring failed")

        except Exception as e:
            logger.error(f"Deployment process failed: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Model deployment failed: {str(e)}"
            )

    return {"status": "Model deployed and registered successfully"}
