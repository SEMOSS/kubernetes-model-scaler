from pydantic import BaseModel

class ModelRequest(BaseModel):
    model_repo_name: str
    model_id: str
    model_name: str