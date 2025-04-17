import time
import logging
import requests

logger = logging.getLogger(__name__)


class KServeMixin:
    def wait_for_model_ready(self):
        """
        Check if the model is ready for inference by directly pinging the health endpoint.
        Returns:
            bool: True if model is ready, False otherwise
        """
        logger.info("Waiting for InferenceService to be ready...")
        model_name = self.model_name

        timeout = 1200  # 20 minutes
        polling_interval = 10
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.check_model_health_endpoint():
                logger.info(
                    f"Model {model_name} is ready according to health endpoint check"
                )
                return True

            time.sleep(polling_interval)

        logger.warning(
            f"Timeout waiting for model {model_name} to become ready after {timeout} seconds"
        )
        return False

    def check_model_health_endpoint(self):
        """
        Directly check the model's health/ready endpoint.
        Returns:
            bool: True if the health endpoint returns a successful response, False otherwise
        """

        lb_ip = self.get_load_balancer_ip(wait=True)

        logger.info(f"Checking LoadBalancer External IP: {lb_ip}")

        endpoint = f"http://{lb_ip}:80/v2/health/ready"

        try:
            logger.info(f"Checking health endpoint: {endpoint}")
            response = requests.get(endpoint, timeout=5)

            if response.status_code < 400:
                logger.info(
                    f"Health endpoint {endpoint} returned status code {response.status_code}"
                )
                return True
            else:
                logger.warning(
                    f"Health endpoint {endpoint} returned status code {response.status_code}"
                )

        except requests.RequestException as e:
            logger.warning(f"Failed to connect to health endpoint {endpoint}: {e}")

        logger.info("All health endpoint checks failed")
        return False
