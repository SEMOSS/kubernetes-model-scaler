"""Check each node in a nodepool to see if Docker Image is cached.."""

from kubernetes import client, config


def check_image_on_nodes(image_name, nodepool_label):
    config.load_kube_config()

    v1 = client.CoreV1Api()

    nodes = v1.list_node(
        label_selector=f"cloud.google.com/gke-nodepool={nodepool_label}"
    )

    results = {}
    for node in nodes.items:
        node_name = node.metadata.name
        pods = v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node_name}"
        )

        has_image = False
        for pod in pods.items:
            for container in pod.spec.containers:
                if container.image == image_name:
                    has_image = True
                    break
            if has_image:
                break

        results[node_name] = has_image

    return results


image_name = "docker.semoss.org/genai/remote-client-server:2025-01-08-1923"
nodepool = "large-gpu-pool"
results = check_image_on_nodes(image_name, nodepool)

print("\nImage cache status for each node:")
print("-" * 50)
cached_count = sum(1 for v in results.values() if v)
print(f"\nNodes with image cached: {cached_count}/{len(results)}")
print("\nDetailed status:")
for node, has_image in results.items():
    status = "✓ Has image cached" if has_image else "✗ No image cache found"
    print(f"{node}: {status}")
