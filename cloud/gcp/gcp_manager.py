import logging
import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from cloud.cloud_manager import CloudManager
from cloud.gcp.storage.storage_manager import StorageManager
from config.config import IS_DEV

logger = logging.getLogger(__name__)


class GCPManager(CloudManager):

    def __init__(self):
        self.required_vars = ["GCP_PROJECT_ID", "GCP_PRIVATE_KEY", "GCP_CLIENT_EMAIL"]
        self.is_dev = IS_DEV
        self.creds = self.get_credentials()
        self.storage = StorageManager()

    def get_credentials(self) -> Credentials | None:
        """
        Get credentials for GCP operations.
        """
        # This is for if I want to use workload identity locally
        override = True

        if self.is_dev and not override:
            creds_path = Path(__file__).parent / "credentials.json"
            if creds_path.exists():
                logger.info(f"Using service account credentials from: {creds_path}")
                return Credentials.from_service_account_file(creds_path)
            else:
                logger.info(
                    "No service account credentials found for local development"
                )
                return None
        # Gotta do this since I'm not allowed to bind the service account...
        elif all(var in os.environ for var in self.required_vars):
            logger.info("Using environment variables for GCP authentication")

            private_key = os.environ.get("GCP_PRIVATE_KEY")

            if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
                private_key = private_key.replace("\\n", "\n")

            service_account_info = {
                "type": "service_account",
                "project_id": os.environ.get("GCP_PROJECT_ID"),
                "private_key_id": os.environ.get("GCP_PRIVATE_KEY_ID"),
                "private_key": private_key,
                "client_email": os.environ.get("GCP_CLIENT_EMAIL"),
                "client_id": os.environ.get("GCP_CLIENT_ID"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ.get('GCP_CLIENT_EMAIL').replace('@', '%40')}",
            }

            try:
                return Credentials.from_service_account_info(service_account_info)
            except Exception as e:
                logger.error(
                    f"Failed to create credentials from environment variables: {e}"
                )
                return None
        else:
            logger.info("Using workload identity for GCP operations")
            return None
