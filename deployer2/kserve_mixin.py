import time
import logging
import requests

logger = logging.getLogger(__name__)


class KServeMixin:
    def wait_for_model_ready(self) -> bool:
        """
        Check if the model is ready for inference by directly pinging the health endpoint using the external IP.
        Returns:
            bool: True if model is ready, False otherwise
        """
        logger.info("Waiting for InferenceService to be ready...")
        model_name = self.model_name

        timeout = 500
        polling_interval = 5
        start_time = time.time()

        failed_lb_ip_acquisition_count = 0

        while time.time() - start_time < timeout:
            lb_ip = self.get_load_balancer_ip(wait=True)

            if not lb_ip:
                logger.warning(
                    "LoadBalancer IP is not available for model health check..."
                )
                failed_lb_ip_acquisition_count += 1

                if failed_lb_ip_acquisition_count > 3:
                    logger.warning(
                        "Failed to acquire LoadBalancer IP multiple times, stopping health checks."
                    )
                    return False
            else:
                if self.check_model_health_endpoint(lb_ip):
                    logger.info(
                        f"Model {model_name} is ready according to health endpoint check"
                    )
                    return True

            time.sleep(polling_interval)

        logger.warning(
            f"Timeout waiting for model {model_name} to become ready after {timeout} seconds"
        )
        return False

    def check_model_health_endpoint(self, lb_ip: str) -> bool:
        """
        Directly check the model's health/ready endpoint.
        Returns:
            bool: True if the health endpoint returns a successful response, False otherwise
        """

        endpoint = f"http://{lb_ip}:80/v2/health/ready"

        logger.info(
            f"Using load balancer external IP to check model health at: {endpoint}"
        )

        try:
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

        logger.info("Model health endpoint check failed..")
        return False
