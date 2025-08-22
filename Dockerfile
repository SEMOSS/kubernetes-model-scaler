FROM python:3.11-slim

ENV HOME=/root \
    GIT_LFS_SKIP_SMUDGE=0 \
    GIT_TERMINAL_PROMPT=0 \
    GIT_LFS_PROGRESS=true \
    GIT_TRACE=1 \
    DOCKER_IMAGE=default_image \
    IMAGE_PULL_SECRET=default_secret \
    ZK_HOSTS=default_hosts \
    NAMESPACE=default_namespace \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    python3-pip \
    python3-dev \
    libgl1-mesa-dri \
    libglib2.0-0 \
    git \
    build-essential \
    curl \
    && curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash \
    && apt-get install -y git-lfs \
    && git lfs install --system \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /root/.config/git

RUN git config --system credential.helper store \
    && git config --system http.sslVerify false \
    && git config --system http.postBuffer 524288000 \
    && git config --system http.lowSpeedLimit 1000 \
    && git config --system http.lowSpeedTime 600 \
    && git config --system protocol.version 2 \
    && git config --system lfs.concurrenttransfers 4 \
    && git config --system core.compression 0 \
    && git config --system http.maxRequestBuffer 100M

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1