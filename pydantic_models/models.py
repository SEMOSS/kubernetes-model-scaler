from pydantic import BaseModel


class ModelRequest(BaseModel):
    model_id: str  # SEMOSS UUID for the model
    model_repo_id: str  # HuggingFace model repo ID
    model: str  # SEMOSS Short name for the model
    model_type: str  # Model Type

    model_config = {"protected_namespaces": ()}
