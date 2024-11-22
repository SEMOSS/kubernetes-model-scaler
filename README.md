# Kubernetes Model Scaler


## Running the Server Locally
```bash
python main.py
```

## Docker
```bash
docker build -t model-scaler .
```

```bash
docker run -p 8000:8000 -e DOCKER_IMAGE=docker-image-name -e IMAGE_PULL_SECRET=image-pull-secret -e ZK_HOSTS=zk-hosts -e NAMESPACE=namespace  --name model-scaler model-scaler
```

## Access API Documentation
- `http://127.0.0.1:8000/docs` for Swagger UI documentation.
- `http://127.0.0.1:8000/redoc` for ReDoc documentation.


## Access API Endpoints
- `http://localhost:8000/api/health` - Health check endpoint.

- `http://localhost:8000/api/start` - Start endpoint.

- `http://localhost:8000/api/stop` - Stop endpoint.

- `http://localhost:8000/api/pvc/get-pvcs` - Get list of attached PVCs and the downloaded models.

- `http://localhost:8000/api/pvc/remove-model` - Remove a model from the PVC.

- `http://localhost:8000/api/pvc/download-model` - Download a model to the PVC.