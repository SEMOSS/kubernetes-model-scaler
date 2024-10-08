from deployer.base_deployer import BaseDeployer
from deployer.deployment_mixin import DeploymentMixin
from deployer.service_mixin import ServiceMixin
from deployer.zookeeper_mixin import ZookeeperMixin
from deployer.monitoring_mixin import MonitoringMixin
from deployer.pvc_mixin import PVCMixin
from deployer.autoscaler_mixin import AutoscalerMixin


class KubernetesModelDeployer(
    AutoscalerMixin,
    BaseDeployer,
    DeploymentMixin,
    ServiceMixin,
    ZookeeperMixin,
    MonitoringMixin,
    PVCMixin,
):
    pass
