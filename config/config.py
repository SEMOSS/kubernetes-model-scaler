import os

# uncomment this line if you are running locally
# from dotenv import load_dotenv

# load_dotenv()

ZK_HOSTS = os.getenv("ZK_HOSTS", None)
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", None)
NAMESPACE = os.getenv("NAMESPACE", "semoss")
IMAGE_PULL_SECRET = os.getenv("IMAGE_PULL_SECRET", None)
