import os

ZK_HOSTS = os.getenv('ZK_HOSTS', '127.0.0.1:2181')
DOCKER_IMAGE = os.getenv('DOCKER_IMAGE', 'your-docker-image')  # Replace with your actual image
NAMESPACE = os.getenv('NAMESPACE', 'default')
IMAGE_PULL_SECRET  = os.getenv('IMAGE_PULL_SECRET', None)