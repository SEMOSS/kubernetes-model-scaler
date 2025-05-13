# import logging
# from fastapi import HTTPException
# from instance_capability.capability_check import ModelCompatibilityChecker
# from instance_capability.node_pool_selector import NodePoolSelector
# from instance_capability.models import NodePool
# from instance_capability.config import approved_models

# logger = logging.getLogger(__name__)


# class CapabilityMixin:
#     def get_capability(self) -> NodePool:
#         try:
#             if self.model_repo_id in approved_models:
#                 self.node_pool = approved_models[self.model_repo_id].node_pool
#                 return approved_models[self.model_repo_id].node_pool
#             compatibility_checker = ModelCompatibilityChecker()
#             can_run, details = compatibility_checker.check_compatibility(
#                 self.model_repo_id
#             )
#             if not can_run:
#                 raise HTTPException(
#                     status_code=400,
#                     detail={
#                         "error": "Incompatible model",
#                         "message": "The specified model cannot run on any avilable instances.",
#                     },
#                 )

#             node_pool_selector = NodePoolSelector(details, self.model_type)
#             node_pool = node_pool_selector.select_node_pool()
#             if not node_pool:
#                 raise HTTPException(
#                     status_code=400,
#                     detail={
#                         "error": "Incompatible model",
#                         "message": "The specified model cannot run on any available instances.",
#                     },
#                 )

#             logger.info(f"Selected node pool: {node_pool.node_pool_name}")

#             self.node_pool = node_pool

#             return node_pool

#         except ValueError as e:
#             error_msg = str(e).lower()
#             logger.error(f"ValueError encountered: {error_msg}")
#             if "gated" in error_msg:
#                 raise HTTPException(
#                     status_code=401,
#                     detail={
#                         "error": "Authentication required",
#                         "message": "This is a gated model. Please provide an access token.",
#                     },
#                 )
#             elif "not found" in error_msg:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "error": "Model not found",
#                         "message": "The specified model was not found. Please provide a valid model ID.",
#                     },
#                 )
#             else:
#                 raise HTTPException(
#                     status_code=500,
#                     detail={
#                         "error": "Internal Server Error",
#                         "message": "An unexpected server error occurred. Please try again later.",
#                     },
#                 )
