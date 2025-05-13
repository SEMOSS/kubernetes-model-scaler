import os
import uvicorn
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from events.startup_events import register_with_zookeeper
from events.shutdown_events import clean_up_zk
from router.health_route import health_check_router
from router.version_route import version_router
from router.can_it_run_route import instance_check_router
from router.shutdown_lock_route import shutdown_lock_router
from router.zk_info_route import zk_info_router
from router.deploy_daemon_set_route import deploy_daemon_set_router
from router.destroy_daemon_set_route import destroy_daemon_set_router
from router.start_route_v2 import start_router_v2
from router.stop_route_v2 import stop_router_v2
from router.compute.pools_info import pools_info_router

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

app.include_router(start_router_v2, prefix="/api/v2")
app.include_router(stop_router_v2, prefix="/api/v2")
app.include_router(health_check_router, prefix="/api")
app.include_router(version_router, prefix="/api")
# CanItRun
app.include_router(instance_check_router, prefix="/api")
# Get Node Pool Information
app.include_router(pools_info_router, prefix="/api/resources")


app.include_router(shutdown_lock_router, prefix="/api")
app.include_router(zk_info_router, prefix="/api")

app.include_router(deploy_daemon_set_router, prefix="/api/daemon-set")
app.include_router(destroy_daemon_set_router, prefix="/api/daemon-set")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
