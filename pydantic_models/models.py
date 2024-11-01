from pydantic import BaseModel


class ModelRequest(BaseModel):
    model_id: str
    model: str

    model_config = {"protected_namespaces": ()}
