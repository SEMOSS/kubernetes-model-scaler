import os
from kazoo.client import KazooClient
from dotenv import load_dotenv

load_dotenv()
ZK_HOSTS = os.getenv("ZK_HOSTS")

zk = KazooClient(hosts=ZK_HOSTS)
zk.start()

# List registered models
if zk.exists("/models"):
    models = zk.get_children("/models")
    print("Registered models:", models)
else:
    print("/models path does not exist.")

# Get the cluster IP for a specific model
model_id = "3a3c3b49-8ce4-4e66-bf42-204c3cbbfcb0"  # Replace with your model_id
if zk.exists(f"/models/{model_id}"):
    data, stat = zk.get(f"/models/{model_id}")
    print(f"Model ID: {model_id}, Cluster IP: {data.decode('utf-8')}")
else:
    print(f"Model {model_id} not found in Zookeeper.")

zk.stop()
