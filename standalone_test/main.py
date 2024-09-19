from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kazoo.client import KazooClient
import uuid
import time

NAMESPACE="default"
ZK_HOST="127.0.0.1:8888"

class KubernetesModelDeployer:
    def __init__(self, model_repo_name, model_id, model_name, namespace='default', zookeeper_hosts=ZK_HOST):
        self.model_repo_name = model_repo_name
        self.model_id = model_id
        self.model_name = model_name
        self.namespace = namespace
        self.zookeeper_hosts = zookeeper_hosts
        config.load_kube_config()
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

    def create_deployment(self):
        # Define the container
        container = client.V1Container(
            name=self.model_name,
            image="your-docker-image",  # Replace with your actual image
            env=[client.V1EnvVar(name="MODEL_REPO_NAME", value=self.model_repo_name)],
            ports=[client.V1ContainerPort(container_port=80)]
        )

        # Define the template
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"model-id": self.model_id, "model-name": self.model_name}),
            spec=client.V1PodSpec(containers=[container])
        )

        # Define the spec
        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={'matchLabels': {"model-id": self.model_id, "model-name": self.model_name}}
        )

        # Define the deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=self.model_name),
            spec=spec
        )

        # Create the deployment
        api_instance = client.AppsV1Api()
        try:
            api_response = api_instance.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment
            )
            print("Deployment created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating deployment: %s\n" % e)

    def create_service(self):
        # Define the service
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=self.model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": self.model_id, "model-name": self.model_name},
                ports=[client.V1ServicePort(port=80, target_port=80)],
                type="ClusterIP"
            )
        )

        # Create the service
        api_instance = client.CoreV1Api()
        try:
            api_response = api_instance.create_namespaced_service(
                namespace=self.namespace,
                body=service
            )
            print("Service created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating service: %s\n" % e)

    def watch_deployment(self):
        api_instance = client.AppsV1Api()
        w = watch.Watch()
        try:
            for event in w.stream(api_instance.list_namespaced_deployment, namespace=self.namespace, timeout_seconds=600):
                deployment = event['object']
                if deployment.metadata.name == self.model_name:
                    status = deployment.status
                    print(f"Deployment {self.model_name} status: Available Replicas: {status.available_replicas}, Ready Replicas: {status.ready_replicas}")
                    if status.available_replicas == status.replicas and status.ready_replicas == status.replicas:
                        print(f"Deployment {self.model_name} is healthy.")
                        w.stop()
                        self.update_zookeeper()
        except ApiException as e:
            print("Exception when watching deployment: %s\n" % e)

    def get_service_cluster_ip(self):
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(name=self.model_name, namespace=self.namespace)
            return service.spec.cluster_ip
        except ApiException as e:
            print("Exception when reading service: %s\n" % e)
            return None

    def update_zookeeper(self):
        cluster_ip = self.get_service_cluster_ip()
        if cluster_ip:
            path = f"/models/{self.model_id}"
            self.kazoo_client.ensure_path("/models")
            self.kazoo_client.set(path, cluster_ip.encode('utf-8'))
            print(f"Zookeeper updated at {path} with value {cluster_ip}")

if __name__ == "__main__":
    model_repo_name = "meta/llama70b"
    model_id = str(uuid.uuid4())
    model_name = "llama70b"

    deployer = KubernetesModelDeployer(model_repo_name, model_id, model_name)
    deployer.create_deployment()
    deployer.create_service()
    deployer.watch_deployment()