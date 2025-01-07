from kubernetes import client, config
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_metric_collection(model_name: str):
    # Load kube config
    config.load_kube_config()
    v1 = client.CoreV1Api()

    try:
        # Get pods with your model label
        pods = v1.list_namespaced_pod(
            namespace="semoss", label_selector=f"model-name={model_name}"
        )

        for pod in pods.items:
            pod_ip = pod.status.pod_ip
            if pod_ip:
                # Try to access metrics endpoint directly
                try:
                    response = requests.get(f"http://{pod_ip}:8888/metrics")
                    if response.status_code == 200:
                        logger.info(f"Pod {pod.metadata.name} metrics accessible")
                        # Check if our specific metric is present
                        if "modelserver_queue_size" in response.text:
                            logger.info("Queue size metric found in response")
                            # Print the actual metric lines
                            for line in response.text.split("\n"):
                                if (
                                    "modelserver_queue_size" in line
                                    and not line.startswith("#")
                                ):
                                    logger.info(f"Metric value: {line}")
                        else:
                            logger.error("Queue size metric not found in response")
                    else:
                        logger.error(
                            f"Metrics endpoint returned {response.status_code}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to access metrics for pod {pod.metadata.name}: {e}"
                    )

        # Check PodMonitoring status
        custom_api = client.CustomObjectsApi()
        pod_monitoring = custom_api.get_namespaced_custom_object(
            group="monitoring.googleapis.com",
            version="v1",
            namespace="semoss",
            plural="podmonitorings",
            name=f"{model_name}-pod-monitoring",
        )
        logger.info(f"PodMonitoring status: {pod_monitoring.get('status', {})}")

        # Check HPA configuration
        try:
            hpa = custom_api.get_namespaced_custom_object(
                group="autoscaling",
                version="v2",
                namespace="semoss",
                plural="horizontalpodautoscalers",
                name=f"{model_name}-hpa",
            )
            logger.info("HPA Configuration:")
            logger.info(f"Metric spec: {hpa.get('spec', {}).get('metrics', [])}")
            logger.info(f"HPA status: {hpa.get('status', {})}")
        except client.ApiException as e:
            if e.status == 404:
                logger.error(f"HPA '{model_name}-hpa' not found")
            else:
                logger.error(f"Error checking HPA: {e}")

    except Exception as e:
        logger.error(f"Diagnostic failed: {e}")


if __name__ == "__main__":
    MODEL_NAME = "gliner-multi-v2-1"
    check_metric_collection(MODEL_NAME)
