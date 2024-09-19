from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kazoo.client import KazooClient
from fastapi import HTTPException
from config import ZK_HOSTS, DOCKER_IMAGE, NAMESPACE

class KubernetesModelDeployer:
    def __init__(self, namespace=NAMESPACE, zookeeper_hosts=ZK_HOSTS):
        self.namespace = namespace
        self.zookeeper_hosts = zookeeper_hosts
        config.load_kube_config()
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

    def create_deployment(self, model_repo_name, model_id, model_name):
        container = client.V1Container(
            name=model_name,
            image=DOCKER_IMAGE,  # Use the image from the config
            env=[client.V1EnvVar(name="MODEL_REPO_NAME", value=model_repo_name)],
            ports=[client.V1ContainerPort(container_port=80)]
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"model-id": model_id, "model-name": model_name}),
            spec=client.V1PodSpec(containers=[container])
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={'matchLabels': {"model-id": model_id, "model-name": model_name}}
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=model_name),
            spec=spec
        )

        api_instance = client.AppsV1Api()
        try:
            api_response = api_instance.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment
            )
            print("Deployment created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to create deployment")

    def create_service(self, model_id, model_name):
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": model_id, "model-name": model_name},
                ports=[client.V1ServicePort(port=80, target_port=80)],
                type="ClusterIP"
            )
        )

        api_instance = client.CoreV1Api()
        try:
            api_response = api_instance.create_namespaced_service(
                namespace=self.namespace,
                body=service
            )
            print("Service created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to create service")

    def watch_deployment(self, model_name):
        api_instance = client.AppsV1Api()
        w = watch.Watch()
        try:
            for event in w.stream(api_instance.list_namespaced_deployment, namespace=self.namespace, timeout_seconds=600):
                deployment = event['object']
                if deployment.metadata.name == model_name:
                    status = deployment.status
                    print(f"Deployment {model_name} status: Available Replicas: {status.available_replicas}, Ready Replicas: {status.ready_replicas}")
                    if status.available_replicas == status.replicas and status.ready_replicas == status.replicas:
                        print(f"Deployment {model_name} is healthy.")
                        w.stop()
                        return True
        except ApiException as e:
            print("Exception when watching deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to watch deployment")
        return False

    def get_service_cluster_ip(self, model_name):
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(name=model_name, namespace=self.namespace)
            return service.spec.cluster_ip
        except ApiException as e:
            print("Exception when reading service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to get service cluster IP")

    def update_zookeeper(self, model_id, model_name):
        cluster_ip = self.get_service_cluster_ip(model_name)
        if cluster_ip:
            path = f"/models/{model_id}"
            self.kazoo_client.ensure_path("/models")
            self.kazoo_client.set(path, cluster_ip.encode('utf-8'))
            print(f"Zookeeper updated at {path} with value {cluster_ip}")

    def delete_deployment(self, model_name):
        api_instance = client.AppsV1Api()
        try:
            api_instance.delete_namespaced_deployment(
                name=model_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions()
            )
            print(f"Deployment {model_name} deleted.")
        except ApiException as e:
            print("Exception when deleting deployment: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete deployment")

    def delete_service(self, model_name):
        api_instance = client.CoreV1Api()
        try:
            api_instance.delete_namespaced_service(
                name=model_name,
                namespace=self.namespace
            )
            print(f"Service {model_name} deleted.")
        except ApiException as e:
            print("Exception when deleting service: %s\n" % e)
            raise HTTPException(status_code=500, detail="Failed to delete service")

    def remove_zookeeper(self, model_id):
        path = f"/models/{model_id}"
        if self.kazoo_client.exists(path):
            self.kazoo_client.delete(path)
            print(f"Zookeeper entry {path} deleted.")