import time
import logging
from kserve import KServeClient

logger = logging.getLogger(__name__)


class KServeMixin:
    def wait_for_model_ready(self):
        """
        Check if the model is ready for inference.

        Args:
            timeout (int): Maximum time to wait in seconds

        Returns:
            bool: True if model is ready, False otherwise
        """
        logger.info("Waiting for InferenceService to be ready...")
        model_name = self.model_name
        namespace = self.model_namespace
        kserve = KServeClient()

        timeout = 1200  # 20 minutes
        polling_interval = 10
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                isvc = kserve.get(name=model_name, namespace=namespace)
                # Using this because there is an issue with the wait_isvc_ready method...
                if kserve.is_isvc_ready(model_name, namespace=namespace):
                    logger.info(f"Model {model_name} is ready for inference")
                    return True

                logger.info(f"Model {model_name} exists but not ready yet, waiting...")

            except Exception as e:
                logger.warning(f"Error checking model status: {e}")

            time.sleep(polling_interval)

        logger.warning(
            f"Timeout waiting for model {model_name} to become ready after {timeout} seconds"
        )
        return False
