import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

ZK_HOSTS = os.getenv("ZK_HOSTS")
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE")
NAMESPACE = os.getenv("NAMESPACE", "semoss")
MODEL_NAMESPACE = os.getenv("MODEL_NAMESPACE", "huggingface-models")
IMAGE_PULL_SECRET = os.getenv("IMAGE_PULL_SECRET")
IS_DEV = os.getenv("IS_DEV", "false").lower()

STANDARD_CLUSTER = os.getenv("STANDARD_CLUSTER", "standard")
AUTOPILOT_CLUSTER = os.getenv("AUTOPILOT_CLUSTER", "autopilot")
KUBECONFIG_PATH = os.getenv("KUBECONFIG_PATH", "/app/kubeconfig/config")
