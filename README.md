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
docker run -p 8000:8000 --name model-scaler model-scaler
```

## Access API Documentation
- `http://127.0.0.1:8000/docs` for Swagger UI documentation.
- `http://127.0.0.1:8000/redoc` for ReDoc documentation.


## Access API Endpoints
- `http://localhost:8000/api/health` - Health check endpoint.

- `http://localhost:8000/api/start` - Start endpoint.

- `http://localhost:8000/api/stop` - Stop endpoint.