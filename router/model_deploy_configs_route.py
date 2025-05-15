from fastapi import APIRouter, Request, Query, HTTPException
import asyncio, logging
from cloud.gcp.storage.storage_manager import StorageManager

logger = logging.getLogger(__name__)
model_deployment_configs_router = APIRouter()


def _reload_configs() -> dict:
    """Blocking function that creates a StorageManager, reloads, returns dict."""
    mgr = StorageManager()
    mgr.reload_model_configs()
    return mgr.get_model_deployments_config()


@model_deployment_configs_router.get("/model-deploy-configs")
async def get_model_deploy_configs(
    request: Request,
    refresh: bool = Query(
        False, description="Reload configs from GCS before returning"
    ),
):
    if refresh:
        try:
            # run the blocking helper in a thread
            new_configs = await asyncio.to_thread(_reload_configs)
        except Exception as exc:
            logger.exception("Failed to refresh model deployment configs")
            raise HTTPException(
                status_code=500,
                detail="Unable to refresh model deployment configurations",
            ) from exc

        request.app.state.deployment_configs = new_configs
        logger.info(
            "Model deployment configs cache refreshed (items=%d)", len(new_configs)
        )

    return request.app.state.deployment_configs
