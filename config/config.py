import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

ZK_HOSTS = os.getenv("ZK_HOSTS")
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE")
NAMESPACE = os.getenv("NAMESPACE", "semoss")
IMAGE_PULL_SECRET = os.getenv("IMAGE_PULL_SECRET")
DEV = os.getenv("DEV", "false")
