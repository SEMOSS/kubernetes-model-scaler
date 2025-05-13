# from kubernetes import client
# from kubernetes.client.rest import ApiException
# import logging

# logger = logging.getLogger(__name__)


# class PVCMixin:
#     def create_pvc(self, storage_size: str = "100Gi", pvc_name: str = "fuse-pvc-rwm"):
#         """
#         Checks for an existing Persistent Volume Claim (PVC) with the given name.
#         If it doesn't exist, creates a new PVC using the gcs-fuse-csi storage class.
#         """
#         api_instance = client.CoreV1Api()

#         # Check if the PVC already exists
#         try:
#             existing_pvc = api_instance.read_namespaced_persistent_volume_claim(
#                 name=pvc_name, namespace=self.namespace
#             )
#             logger.info(f"PVC '{pvc_name}' already exists. Using the existing PVC.")
#             return existing_pvc
#         except ApiException as e:
#             if e.status != 404:
#                 logger.error(f"Exception when checking for existing PVC: {e}")
#                 raise

#         # Create PVC specification with gcs-fuse-csi storage class
#         pvc_spec = client.V1PersistentVolumeClaimSpec(
#             access_modes=["ReadWriteMany"],
#             resources=client.V1ResourceRequirements(requests={"storage": storage_size}),
#             storage_class_name="my-fuse-storage-class",
#         )

#         # Create PVC object
#         pvc = client.V1PersistentVolumeClaim(
#             metadata=client.V1ObjectMeta(
#                 name=pvc_name, annotations={"kubernetes.io/created-by": "pvc-mixin"}
#             ),
#             spec=pvc_spec,
#         )

#         # Attempt to create the PVC
#         try:
#             api_response = api_instance.create_namespaced_persistent_volume_claim(
#                 namespace=self.namespace, body=pvc
#             )
#             logger.info(
#                 f"PVC '{pvc_name}' created successfully with status: {api_response.status}"
#             )
#             return api_response
#         except ApiException as e:
#             logger.error(f"Exception when creating PVC '{pvc_name}': {e}")
#             raise
