# from kubernetes import client
# from kubernetes.client.rest import ApiException
# from fastapi import HTTPException
# import logging

# logger = logging.getLogger(__name__)


# class AutoscalerMixin:
#     def create_hpa(
#         self,
#         min_replicas: int = 1,
#         max_replicas: int = 5,
#         target_average_value: str = "5",
#     ):
#         custom_api = client.CustomObjectsApi()

#         hpa_body = {
#             "apiVersion": "autoscaling/v2",
#             "kind": "HorizontalPodAutoscaler",
#             "metadata": {"name": f"{self.model_name}-hpa", "namespace": self.namespace},
#             "spec": {
#                 "scaleTargetRef": {
#                     "apiVersion": "apps/v1",
#                     "kind": "Deployment",
#                     "name": self.model_name,
#                 },
#                 "minReplicas": min_replicas,
#                 "maxReplicas": max_replicas,
#                 "metrics": [
#                     {
#                         "type": "Pods",
#                         "pods": {
#                             "metric": {
#                                 "name": "prometheus.googleapis.com|modelserver_queue_size|gauge"
#                             },
#                             "target": {
#                                 "type": "AverageValue",
#                                 "averageValue": target_average_value,
#                             },
#                         },
#                     }
#                 ],
#             },
#         }

#         try:
#             custom_api.create_namespaced_custom_object(
#                 group="autoscaling",
#                 version="v2",
#                 namespace=self.namespace,
#                 plural="horizontalpodautoscalers",
#                 body=hpa_body,
#             )
#             logger.info(f"HorizontalPodAutoscaler '{self.model_name}-hpa' created.")
#         except ApiException as e:
#             if e.status == 409:
#                 logger.info(
#                     f"HorizontalPodAutoscaler '{self.model_name}-hpa' already exists."
#                 )
#             else:
#                 logger.error(f"Exception when creating HorizontalPodAutoscaler: {e}\n")
#                 raise HTTPException(
#                     status_code=500, detail="Failed to create HorizontalPodAutoscaler"
#                 )

#     def delete_hpa(self):
#         custom_api = client.CustomObjectsApi()
#         try:
#             custom_api.delete_namespaced_custom_object(
#                 group="autoscaling",
#                 version="v2",
#                 namespace=self.namespace,
#                 plural="horizontalpodautoscalers",
#                 name=f"{self.model_name}-hpa",
#                 body=client.V1DeleteOptions(),
#             )
#             logger.info(f"HorizontalPodAutoscaler '{self.model_name}-hpa' deleted.")
#         except ApiException as e:
#             if e.status == 404:
#                 logger.info(
#                     f"HorizontalPodAutoscaler '{self.model_name}-hpa' not found."
#                 )
#             else:
#                 logger.error(f"Exception when deleting HorizontalPodAutoscaler: {e}\n")
#                 raise HTTPException(
#                     status_code=500, detail="Failed to delete HorizontalPodAutoscaler"
#                 )
