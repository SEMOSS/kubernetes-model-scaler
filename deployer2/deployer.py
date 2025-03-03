from deployer2.deployer_config import DeployerConfig
from deployer2.deployment_mixin import DeploymentMixin
from deployer2.load_balancer_mixin import LoadBalancerMixin
from deployer2.external_name_mixin import ExternalNameMixin
from deployer2.ingress_mixin import IngressMixin
from deployer2.kserve_mixin import KServeMixin
from deployer2.zk_mixin import ZookeeperMixin


class Deployer(
    DeployerConfig,
    DeploymentMixin,
    LoadBalancerMixin,
    ExternalNameMixin,
    IngressMixin,
    KServeMixin,
    ZookeeperMixin,
):
    pass
