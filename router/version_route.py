import logging
from fastapi import APIRouter
from config.version import version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

version_router = APIRouter()


@version_router.get("/version")
async def get_version():
    logger.info("Version check successful")
    return {"version": version}
