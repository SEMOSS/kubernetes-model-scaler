import logging
import os
from pathlib import Path
from google.cloud import storage
from google.oauth2.service_account import Credentials
from fastapi import HTTPException
from config.config import RESOURCE_BUCKET_NAME, IS_DEV
from pydantic import BaseModel, Field, ValidationError
from typing import Dict
import yaml


class _Meta(BaseModel):
    name: str = Field(..., description="Kubernetes object name")


class InferenceServiceManifest(BaseModel):
    apiVersion: str
    kind: str
    metadata: _Meta

    class Config:
        extra = "allow"


logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manager class for interacting with Google Cloud Storage.
    Handles authentication and operations like downloading YAML files.
    """

    def __init__(self, creds: Credentials = None):
        """
        Initialize the GCP Storage Manager with the specified bucket.
        Args:
            bucket_name (str): Name of the GCS bucket containing deployment resources
        """
        self.is_dev = IS_DEV
        self.creds = creds
        self.bucket_name = RESOURCE_BUCKET_NAME
        self.client = self._initialize_client()
        self.bucket = self.client.bucket(self.bucket_name)
        self.model_configs: Dict[str, InferenceServiceManifest] = {}

    def _initialize_client(self):
        """
        Initialize the Google Cloud Storage client with appropriate credentials.
        Returns:
            storage.Client: Authenticated GCS client
        """
        try:
            if self.creds:
                return storage.Client(credentials=self.credentials)

            return storage.Client()

        except Exception as e:
            logger.error(f"Failed to initialize GCP Storage client: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to initialize GCP Storage: {str(e)}"
            )

    def download_yaml(self, model_name, local_path=None):
        """
        Download a YAML file from GCS for the specified model.
        Args:
            model_name (str): Name of the model (without .yaml extension)
            local_path (Path, optional): Path to store downloaded file.
                                         If None, returns content as string.
        Returns:
            str or Path: YAML content as string if local_path is None,
                         otherwise Path to downloaded file
        """
        blob_name = f"{model_name}.yaml"
        blob = self.bucket.blob(blob_name)

        try:
            if not blob.exists():
                logger.error(
                    f"YAML file {blob_name} not found in bucket {self.bucket_name}"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"YAML file {blob_name} not found in bucket {self.bucket_name}",
                )

            if local_path:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                blob.download_to_filename(local_path)
                logger.info(f"Downloaded {blob_name} to {local_path}")
                return Path(local_path)

            content = blob.download_as_string().decode("utf-8")
            logger.info(f"Downloaded {blob_name} content from GCS")
            return content

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Error downloading YAML from GCS: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to download YAML from GCS: {str(e)}"
            )

    def get_node_pool_config(self, config_name="node_pools.json"):
        """
        Download and parse node pool configuration from GCS.
        Args:
            config_name (str): Name of the config file (default: node_pools_config.json)
        Returns:
            dict: Parsed node pool configuration
        """
        import json

        try:
            blob = self.bucket.blob(config_name)

            if not blob.exists():
                logger.error(
                    f"Config file {config_name} not found in bucket {self.bucket_name}"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Config file {config_name} not found in bucket {self.bucket_name}",
                )

            content = blob.download_as_string().decode("utf-8")
            config = json.loads(content)
            logger.info(f"Downloaded and parsed {config_name} from GCS")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON config from GCS: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse node pool config JSON: {str(e)}",
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Error downloading config from GCS: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download node pool config from GCS: {str(e)}",
            )

    def reload_model_configs(self) -> None:
        """Fetch every *.yaml (except node_pools.json) and rebuild the cache."""
        new_cache: Dict[str, dict] = {}

        for blob in self.bucket.list_blobs():
            if blob.name == "node_pools.json" or not blob.name.endswith(".yaml"):
                continue

            raw = blob.download_as_bytes()
            try:
                manifest_dict = yaml.safe_load(raw)
                manifest = InferenceServiceManifest.model_validate(manifest_dict)
            except ValidationError as exc:
                logger.error("Skipping bad YAML %s: %s", blob.name, exc)
                continue
            except yaml.YAMLError as exc:
                logger.error("Skipping unreadable YAML %s: %s", blob.name, exc)
                continue

            new_cache[manifest.metadata.name] = manifest_dict

        self.model_configs = new_cache
        logger.info("Loaded %d model configs into cache", len(new_cache))

    def get_model_deployments_config(self):
        return self.model_configs
