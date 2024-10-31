import uvicorn
import logging
from fastapi import FastAPI
from router.health_route import health_check_router
from router.version_route import version_router
from router.start_route import start_router
from router.stop_route import stop_router

logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(health_check_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(start_router, prefix="/api")
app.include_router(stop_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
