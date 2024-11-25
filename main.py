import os
import uvicorn
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from events.startup_events import register_with_zookeeper
from events.shutdown_events import clean_up_zk
from router.health_route import health_check_router
from router.version_route import version_router
from router.start_route import start_router
from router.stop_route import stop_router
from router.pvc_manager.get_pvcs_route import get_pvc_router
from router.pvc_manager.remove_model_route import remove_model_router
from router.pvc_manager.download_model_route import download_model_router
from router.pvc_manager.log_pvc_contents_route import pvc_contents_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_dev = os.getenv("IS_DEV", "false").lower() == "true"
    if not is_dev:
        logger.info("Starting application and registering with Zookeeper...")
        if not register_with_zookeeper():
            logger.error(
                "Failed to register with Zookeeper. Application startup aborted."
            )
            raise RuntimeError("Failed to register the Model Deployer with Zookeeper")
        yield
        clean_up_zk()
    else:
        yield


app = FastAPI(lifespan=lifespan)

app.include_router(health_check_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(start_router, prefix="/api")
app.include_router(stop_router, prefix="/api")
app.include_router(get_pvc_router, prefix="/api/pvc")
app.include_router(remove_model_router, prefix="/api/pvc")
app.include_router(download_model_router, prefix="/api/pvc")
app.include_router(pvc_contents_router, prefix="/api/pvc")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
