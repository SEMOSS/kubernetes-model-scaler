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
        elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            logger.info(
                "Using GOOGLE_APPLICATION_CREDENTIALS environment variable for authentication"
            )
            return None
        else:
            logger.info("Using workload identity for GCP operations")
            return None
