from kserve import KServeClient
import logging

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
        try:
            model_name = self.model_name
            namespace = self.model_namespace

            kserve = KServeClient()
            model_ready = kserve.wait_isvc_ready(
                model_name, namespace=namespace, polling_interval=3
            )

            if model_ready:
                logger.info(f"Model {model_name} is ready for inference")
                return True
            else:
                logger.warning(
                    f"Timeout waiting for model {model_name} to become ready"
                )
                return False
        except Exception as e:
            logger.error(f"Error checking model readiness: {e}")
            return False
