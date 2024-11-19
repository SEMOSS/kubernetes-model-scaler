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

logger = logging.getLogger(__name__)

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application and registering with Zookeeper...")
    if not register_with_zookeeper():
        logger.error("Failed to register with Zookeeper. Application startup aborted.")
        raise RuntimeError("Failed to register the Model Deployer with Zookeeper")
    yield
    clean_up_zk()


app.include_router(health_check_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(start_router, prefix="/api")
app.include_router(stop_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
