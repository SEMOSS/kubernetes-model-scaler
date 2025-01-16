from deployer.base_deployer import BaseDeployer
from deployer.deployment_mixin import DeploymentMixin
from deployer.service_mixin import ServiceMixin
from deployer.zookeeper_mixin import ZookeeperMixin
from deployer.monitoring_mixin import MonitoringMixin
from deployer.pvc_mixin import PVCMixin
from deployer.autoscaler_mixin import AutoscalerMixin
from deployer.health_check_mixin import HealthCheckMixin
from deployer.model_load_mixin import ModelLoadMixin
from deployer.model_files_mixin import ModelFilesMixin


class KubernetesModelDeployer(
    AutoscalerMixin,
    BaseDeployer,
    DeploymentMixin,
    ServiceMixin,
    ZookeeperMixin,
    MonitoringMixin,
    PVCMixin,
    HealthCheckMixin,
    ModelLoadMixin,
    ModelFilesMixin,
):
    pass
