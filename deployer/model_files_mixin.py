# import logging

# logger = logging.getLogger(__name__)


# class ModelFilesMixin:
#     def check_model_files_exist(self) -> bool:
#         """
#         Check if model files already exist in the bucket.
#         Returns:
#             bool: True if files exist, False if they need to be downloaded
#         """
#         try:
#             bucket = self.storage_client.bucket("semoss-model-files")
#             blobs = list(bucket.list_blobs(prefix=f"{self.model_name}/", max_results=1))

#             self.requires_download = len(blobs) == 0
#             logger.info(
#                 f"Model {self.model_name} requires download: {self.requires_download}"
#             )
#             return not self.requires_download

#         except Exception as e:
#             logger.error(f"Error checking model files: {str(e)}")
#             # If can't check assume we need to download to be safe
#             self.requires_download = True
#             return False

#     def get_health_check_timeout(self) -> float:
#         """
#         Get appropriate timeout based on whether model needs to be downloaded.
#         Returns:
#             float: Timeout in seconds
#         """
#         if self.requires_download is None:
#             self.check_model_files_exist()

#         base_timeout = 2700.0
#         download_timeout = 3600.0

#         return download_timeout if self.requires_download else base_timeout
