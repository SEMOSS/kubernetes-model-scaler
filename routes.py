from fastapi import APIRouter, HTTPException
from models import ModelRequest
from kubernetes_deployer import KubernetesModelDeployer

router = APIRouter()

@router.post("/start")
def start_model(request: ModelRequest):
    deployer = KubernetesModelDeployer()
    deployer.create_deployment(request.model_repo_name, request.model_id, request.model_name)
    deployer.create_service(request.model_id, request.model_name)
    if deployer.watch_deployment(request.model_name):
        deployer.update_zookeeper(request.model_id, request.model_name)
        return {"status": "Model deployed and registered successfully"}
    else:
        raise HTTPException(status_code=500, detail="Model deployment failed")

@router.post("/stop")
def stop_model(model_id: str):
    deployer = KubernetesModelDeployer()
    model_name = deployer.get_model_name_from_id(model_id)  # Implement this method to map model_id to model_name
    deployer.delete_deployment(model_name)
    deployer.delete_service(model_name)
    deployer.remove_zookeeper(model_id)
    return {"status": "Model deployment stopped and unregistered successfully"}
