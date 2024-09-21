FROM python:3.11-slim

# Set environment variables for improved performance in containerized Python applications
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# The Docker Image for the Remote Client Server to be used on server startup
ENV RCS_DOCKER_IMAGE="docker.semoss.org/genai/remote-client-server:latest"

HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1