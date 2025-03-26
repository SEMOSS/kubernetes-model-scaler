from enum import Enum
import logging
from cloud.gcp.gcp_manager import GCPManager
from config.config import CLOUD_PROVIDER

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    GCP = "GCP"
    AWS = "AWS"
    AZURE = "AZURE"


def get_cloud_manager():
    """
    Factory function that returns the appropriate cloud manager based on the provider name.
    Returns:
        CloudManager: An instance of the appropriate cloud manager
    Raises:
        ValueError: If the provider is not supported
    """
    if CLOUD_PROVIDER == CloudProvider.GCP.value:
        logger.info("Initializing GCPManager")
        return GCPManager()
    # elif CLOUD_PROVIDER == CloudProvider.AWS.value:
    #     logger.info("Initializing AWSManager")
    #     return AWSManager()
    # elif CLOUD_PROVIDER == CloudProvider.AZURE.value:
    #     logger.info("Initializing AzureManager")
    #     return AzureManager()
    else:
        supported_providers = ", ".join([p.value for p in CloudProvider])
        raise ValueError(
            f"Unsupported cloud provider: {CLOUD_PROVIDER}. "
            f"Please set the CLOUD_PROVIDER environment variable to one of: {supported_providers}"
        )
