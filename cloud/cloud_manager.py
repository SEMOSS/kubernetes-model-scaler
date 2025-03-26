from abc import ABC, abstractmethod
from config.config import IS_DEV


class CloudManager(ABC):
    """Base class for all cloud provider implementations."""

    @abstractmethod
    def get_credentials(self):
        """Create a load balancer for the service."""
        pass
