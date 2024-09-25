import os
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kazoo.client import KazooClient
from dotenv import load_dotenv

load_dotenv()

ZK_HOSTS = os.getenv("ZK_HOSTS")
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE")
NAMESPACE = os.getenv("NAMESPACE")
IMAGE_PULL_SECRET = os.getenv("IMAGE_PULL_SECRET")
USE_KUBE_CONFIG = os.getenv("USE_KUBE_CONFIG", "False")


class KubernetesModelDeployer:
    def __init__(
        self,
        namespace=NAMESPACE,
        zookeeper_hosts=ZK_HOSTS,
        image_pull_secret=IMAGE_PULL_SECRET,
    ):
        self.namespace = namespace
        self.zookeeper_hosts = zookeeper_hosts
        self.image_pull_secret = image_pull_secret
        if USE_KUBE_CONFIG.lower() == "true":
            config.load_kube_config()
        else:
            config.load_incluster_config()
        self.kazoo_client = KazooClient(hosts=self.zookeeper_hosts)
        self.kazoo_client.start()

    def create_deployment(self, model_repo_name, model_id, model_name, pvc_name):
        volume = client.V1Volume(
            name="model-storage",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=pvc_name
            ),
        )

        volume_mount = client.V1VolumeMount(
            name="model-storage", mount_path="/app/model_files"
        )
        container = client.V1Container(
            name=model_name,
            image=DOCKER_IMAGE,
            env=[client.V1EnvVar(name="MODEL_REPO_NAME", value=model_repo_name)],
            ports=[client.V1ContainerPort(container_port=8888)],
            volume_mounts=[volume_mount],
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"model-id": model_id, "model-name": model_name}
            ),
            spec=client.V1PodSpec(
                containers=[container],
                volumes=[volume],
                image_pull_secrets=(
                    [client.V1LocalObjectReference(name=self.image_pull_secret)]
                    if self.image_pull_secret
                    else None
                ),
            ),
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector={"matchLabels": {"model-id": model_id, "model-name": model_name}},
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=model_name),
            spec=spec,
        )

        api_instance = client.AppsV1Api()
        try:
            api_response = api_instance.create_namespaced_deployment(
                namespace=self.namespace, body=deployment
            )
            print("Deployment created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating deployment: %s\n" % e)
            raise

    def create_pvc(self, pvc_name, storage_size="50Gi"):
        api_instance = client.CoreV1Api()

        # check if the PVC already exists
        try:
            existing_pvc = api_instance.read_namespaced_persistent_volume_claim(
                name=pvc_name, namespace=self.namespace
            )
            print(f"PVC '{pvc_name}' already exists. Using the existing PVC.")
            return existing_pvc
        except ApiException as e:
            if e.status != 404:  # If error is not "Not Found"
                print(f"Exception when checking for existing PVC: {e}\n")
                raise

        # If PVC doesn't exist create a new one
        pvc = client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=pvc_name),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": storage_size}
                ),
            ),
        )

        try:
            api_response = api_instance.create_namespaced_persistent_volume_claim(
                namespace=self.namespace, body=pvc
            )
            print(f"PVC created. status='{str(api_response.status)}'")
            return api_response
        except ApiException as e:
            print(f"Exception when creating PVC: {e}\n")
            raise

    def create_service(self, model_id, model_name):
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=model_name),
            spec=client.V1ServiceSpec(
                selector={"model-id": model_id, "model-name": model_name},
                ports=[client.V1ServicePort(port=8888, target_port=8888)],
                type="ClusterIP",
            ),
        )

        api_instance = client.CoreV1Api()
        try:
            api_response = api_instance.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            print("Service created. status='%s'" % str(api_response.status))
        except ApiException as e:
            print("Exception when creating service: %s\n" % e)
            raise

    def watch_deployment(self, model_name):
        api_instance = client.AppsV1Api()
        w = watch.Watch()
        try:
            for event in w.stream(
                api_instance.list_namespaced_deployment,
                namespace=self.namespace,
                timeout_seconds=600,
            ):
                deployment = event["object"]
                if deployment.metadata.name == model_name:
                    status = deployment.status
                    print(
                        f"Deployment {model_name} status: Available Replicas: {status.available_replicas}, Ready Replicas: {status.ready_replicas}"
                    )
                    if (
                        status.available_replicas == status.replicas
                        and status.ready_replicas == status.replicas
                    ):
                        print(f"Deployment {model_name} is healthy.")
                        w.stop()
                        return True
        except ApiException as e:
            print("Exception when watching deployment: %s\n" % e)
            raise
        return False

    def get_service_cluster_ip(self, model_name):
        api_instance = client.CoreV1Api()
        try:
            service = api_instance.read_namespaced_service(
                name=model_name, namespace=self.namespace
            )
            return service.spec.cluster_ip
        except ApiException as e:
            print("Exception when reading service: %s\n" % e)
            raise

    def update_zookeeper(self, model_id, model_name):
        cluster_ip = self.get_service_cluster_ip(model_name)
        if cluster_ip:
            path = f"/models/{model_id}"
            self.kazoo_client.ensure_path(path)
            self.kazoo_client.set(path, cluster_ip.encode("utf-8"))
            print(f"Zookeeper updated at {path} with value {cluster_ip}")


def main():
    model_repo_name = "PixArt-alpha/PixArt-XL-2-1024-MS"
    model_id = "3a3c3b49-8ce4-4e66-bf42-204c3cbbfcb0"
    model_name = "pixart"
    pvc_name = f"{model_name}-pvc"

    deployer = KubernetesModelDeployer()
    pvc = deployer.create_pvc(pvc_name)
    if pvc:
        deployer.create_deployment(model_repo_name, model_id, model_name, pvc_name)
        deployer.create_service(model_id, model_name)
        if deployer.watch_deployment(model_name):
            deployer.update_zookeeper(model_id, model_name)
            print("Model deployed and registered successfully")
        else:
            print("Model deployment failed")
    else:
        print("Failed to create or find PVC")


if __name__ == "__main__":
    main()