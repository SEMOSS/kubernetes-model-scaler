import os
import shutil
from typing import Dict, List, Tuple
from pathlib import Path
from pvc_manager.download_manager import DownloadManager
import logging

logger = logging.getLogger(__name__)


class PVCManager:
    def __init__(self):
        self.base_path = "/app/"
        self.pvcs = self.get_pvcs()
        self.pvc_config = self.build_pvc_config()
        self.download_manager = DownloadManager()

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        Convert size in bytes to a human-readable string with appropriate units.
        Will return in GB if size is >= 1GB, otherwise in MB.
        """
        mb_size = size_bytes / (1024 * 1024)
        if mb_size >= 1024:
            gb_size = mb_size / 1024
            return f"{gb_size:.2f} gbs"
        return f"{mb_size:.2f} mbs"

    def get_pvcs(self) -> List[str]:
        """
        Identify the mounted PVCs off the base path
        """
        mounted_pvs = []
        for root, dirs, files in os.walk(self.base_path):
            for dir in dirs:
                if os.path.ismount(os.path.join(root, dir)):
                    mounted_pvs.append(os.path.join(root, dir))
        return mounted_pvs

    def get_pvc_usage(self, pvc: str) -> dict:
        """
        Get the usage of a specific PVC with appropriate size units
        """
        total, used, free = shutil.disk_usage(pvc)
        return {
            "pvc": pvc,
            "total": self.format_size(total),
            "used": self.format_size(used),
            "free": self.format_size(free),
        }

    def get_pvc_models(self, pvc_path: str) -> List[Dict]:
        """
        Get the models stored in each PVC, handling snapshot subdirectories
        """
        try:
            # check if there's a snapshot directory
            base_path = pvc_path
            logger.info(f"Checking for snapshot directory in {base_path}")

            for item in Path(base_path).iterdir():
                logger.info(f"Checking {item}")
                if "snapshot" in item.name.lower() and item.is_dir():
                    base_path = item
                    break

            pvc_contents = [d for d in Path(base_path).iterdir() if d.is_dir()]

            models = []
            for model_dir in pvc_contents:
                size = self.get_model_dir_size(model_dir)
                model = {
                    "name": model_dir.name,
                    "size": size,
                    "path": model_dir,
                }
                models.append(model)
            return models
        except OSError as e:
            print(f"Error accessing directory {pvc_path}: {e}")
            return []

    def log_directory_tree(self, path: str, level: int = 0) -> None:
        """
        Print the entire directory tree starting from the given path
        """
        try:
            prefix = "  " * level + ("└── " if level > 0 else "")
            path_obj = Path(path)
            logger.info(f"{prefix}{path_obj.name}/")

            try:
                for item in path_obj.iterdir():
                    if item.is_dir():
                        self.log_directory_tree(str(item), level + 1)
                    else:
                        child_prefix = "  " * (level + 1) + "└── "
                        logger.info(f"{child_prefix}{item.name}")
            except PermissionError as e:
                logger.error(f"Permission denied accessing {path}: {e}")
            except Exception as e:
                logger.error(f"Error accessing {path}: {e}")

        except Exception as e:
            logger.error(f"Error processing {path}: {e}")

    def get_model_dir_size(self, model_dir: str) -> str:
        """
        Get the size of a model directory with appropriate units
        Returns size as a string with 'mbs' or 'gbs' suffix
        """
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(model_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        if os.path.isfile(fp):
                            total_size += os.path.getsize(fp)
                    except OSError as e:
                        print(f"Error getting size of {fp}: {e}")
                        continue

            return self.format_size(total_size)
        except OSError as e:
            print(f"Error processing directory {model_dir}: {e}")
            return "0.00mbs"

    def build_pvc_config(self) -> dict:
        """
        Build a config of all PVCs, their models, and their usage.
        """
        config = {}

        for pvc in self.pvcs:
            config[pvc] = {
                "models": self.get_pvc_models(pvc),
                "usage": self.get_pvc_usage(pvc),
            }

        return config

    def remove_model_dir(self, model_dir: str) -> Tuple[bool, str]:
        """
        Remove a model directory from the PVC
        """
        if not os.path.exists(model_dir):
            return False, "Model directory does not exist"

        try:
            shutil.rmtree(model_dir)
            return True, "Model directory removed successfully"
        except Exception as e:
            return False, f"Failed to remove model directory: {str(e)}"
