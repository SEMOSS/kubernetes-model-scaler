from kubernetes import client, config
from kserve import KServeClient
from kserve import constants
from kserve import utils
from kserve import V1beta1InferenceService
from kserve import V1beta1InferenceServiceSpec
from kserve import V1beta1PredictorSpec
from kserve import V1beta1TorchServeSpec, V1beta1ONNXRuntimeSpec
import logging

logger = logging.getLogger(__name__)


class KServe:

    def __init__(self):
        self.ks_client = KServeClient()
        self.namespace = "huggingface-models"
        self.api_version = "serving.kserve.io/v1beta1"
        self.IS_DEV = "true"
        if self.IS_DEV == "true":
            print("Using dev config")
            config.load_kube_config(context="standard")
        else:
            print("Using Incluster config")
            config.load_incluster_config()

    def create_isvc(self, model_name: str, storage_uri: str):
        isvc = V1beta1InferenceService(
            api_version=self.api_version,
            kind=constants.KSERVE_KIND,
            metadata=client.V1ObjectMeta(name=model_name, namespace=self.namespace),
            spec=V1beta1InferenceServiceSpec(
                predictor=V1beta1PredictorSpec(
                    pytorch=V1beta1TorchServeSpec(
                        storage_uri=storage_uri,
                        resources=client.V1ResourceRequirements(
                            requests={"memory": "10Gi", "cpu": "1"},
                            limits={"memory": "14Gi", "cpu": "2"},
                        ),
                    )
                )
            ),
        )
        self.ks_client.create(isvc)


if __name__ == "__main__":
    kserve = KServe()
    kserve.create_isvc(
        "samlowe-roberta-base-go-emotions", "hf://SamLowe/roberta-base-go_emotions"
    )
