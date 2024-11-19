from kubernetes import client
from kubernetes.client.rest import ApiException
import logging

logger = logging.getLogger(__name__)


class PVCMixin:
    def create_pvc(self, storage_size="500Gi"):
        """
        Checks for an existing Persistent Volume Claim (PVC) with the given name. If it doesn't exist, creates a new PVC with the specified storage size.
        """
        api_instance = client.CoreV1Api()

        # check if the PVC already exists
        # pvc_name = "filestore-cfg-pv-rwm"
        pvc_name = "filestore-cfg-pvc-rwm"
        try:
            existing_pvc = api_instance.read_namespaced_persistent_volume_claim(
                name=pvc_name, namespace=self.namespace
            )
            logger.info(f"PVC '{pvc_name}' already exists. Using the existing PVC.")
            return existing_pvc
        except ApiException as e:
            if e.status != 404:  # If error is not "Not Found"
                logger.error(f"Exception when checking for existing PVC: {e}\n")
                # raise

        # If PVC doesn't exist create a new one
        pvc = client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=pvc_name),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteMany"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": storage_size}
                ),
            ),
        )

        try:
            api_response = api_instance.create_namespaced_persistent_volume_claim(
                namespace=self.namespace, body=pvc
            )
            print(f"PVC created. status='{str(api_response.status)}'")
            return api_response
        except ApiException as e:
            print(f"Exception when creating PVC: {e}\n")
            raise
