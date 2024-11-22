import json
import os
from typing import Set, Tuple
import logging
import subprocess

logger = logging.getLogger(__name__)


class DownloadManager:
    def __init__(self):
        self.base_path = "/app/"

    def download_model(self, model_path: str, repo_id: str) -> Tuple[bool, str]:
        git_url = f"https://huggingface.co/{repo_id}"
        logger.info(f"Downloading from: {git_url}")

        if self.check_model_existence(model_path):
            logger.info(f"Model already exists at {model_path}")
            return False, "Model already exists"
        os.makedirs(model_path)

        git_env = os.environ.copy()
        git_env.update(
            {
                "GIT_LFS_SKIP_SMUDGE": "1",  # Skip LFS files during clone
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_LFS_PROGRESS": "true",
                "GIT_TRACE": "1",
                "HOME": "/root",
                "GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
            }
        )

        clone_cmd = [
            "git",
            "clone",
            "--progress",
            "--depth",
            "1",
            "--single-branch",
            "--no-checkout",
            git_url,
            ".",
        ]

        clone_process = subprocess.run(
            clone_cmd,
            cwd=model_path,
            env=git_env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Clone output: {clone_process.stdout}")
        if clone_process.stderr:
            logger.info(f"Clone stderr: {clone_process.stderr}")

        # initialize LFS in the repo
        logger.info("Initializing LFS in repository...")
        subprocess.run(
            ["git", "lfs", "install", "--local"],
            cwd=model_path,
            env=git_env,
            check=True,
        )

        # Checkout the files first
        logger.info("Checking out files...")
        subprocess.run(
            ["git", "checkout", "HEAD"], cwd=model_path, env=git_env, check=True
        )

        # Explicitly fetch LFS files
        logger.info("Fetching LFS files...")
        lfs_fetch = subprocess.run(
            ["git", "lfs", "fetch", "--all"],
            cwd=model_path,
            env=git_env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"LFS fetch output: {lfs_fetch.stdout}")

        # Checkout LFS files
        logger.info("Checking out LFS files...")
        lfs_checkout = subprocess.run(
            ["git", "lfs", "checkout"],
            cwd=model_path,
            env=git_env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"LFS checkout output: {lfs_checkout.stdout}")

        # List files and their sizes
        logger.info("Checking downloaded files...")
        for root, dirs, files in os.walk(model_path):
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                logger.info(f"File: {file_path}, Size: {size} bytes")

        if self.verify_download_completion(model_path):
            logger.info("Download verified successfully")
            return True, "Model downloaded successfully"
        else:
            logger.error("Download verification failed")
            return False, "Download verification failed"

    def get_all_files(self, directory: str) -> Set[str]:
        """Get all files in directory and subdirectories."""
        files = set()
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                files.add(os.path.join(root, filename))
        return files

    def check_model_existence(self, model_path: str) -> bool:
        return os.path.exists(model_path)

    def check_file_size(self, filepath: str, min_size_kb: int = 1) -> bool:
        """Check if file exists and is larger than minimum size."""
        try:
            size_kb = os.path.getsize(filepath) / 1024
            return size_kb >= min_size_kb
        except (OSError, FileNotFoundError):
            return False

    def verify_download_completion(self, model_dir: str) -> bool:
        """
        Verify if all model files are completely downloaded and valid.

        This function checks for:
        1. Common model format files (safetensors, bin, model, json)
        2. Essential configuration files
        3. File size validation for key files
        4. Basic file integrity

        Args:
            model_dir: Path to the directory containing the model files

        Returns:
            bool: True if verification passes, False otherwise
        """

        try:
            # 1. Check if directory exists and is not empty
            if not os.path.exists(model_dir) or not os.path.isdir(model_dir):
                logger.error(
                    f"Model directory {model_dir} does not exist or is not a directory"
                )
                return False

            all_files = self.get_all_files(model_dir)
            if not all_files:
                logger.error(f"No files found in {model_dir}")
                return False

            # 2. Check for essential files by extension
            essential_extensions = {
                ".json",  # Config files
                ".txt",  # README, license, etc.
                ".md",  # Documentation
            }

            model_extensions = {
                ".safetensors",  # Common model format
                ".bin",  # Binary model files
                ".model",  # Another common model format
                ".onnx",  # ONNX format
                ".pth",  # PyTorch format
            }

            # Check if we have at least one model file
            has_model_file = any(
                any(f.endswith(ext) for ext in model_extensions) for f in all_files
            )

            if not has_model_file:
                logger.error("No model files found with standard extensions")
                return False

            # 3. Check for config files
            has_config = any(
                any(f.endswith(ext) for ext in essential_extensions) for f in all_files
            )

            if not has_config:
                logger.error("No configuration files found")
                return False

            # 4. Validate file sizes
            large_files = [
                f for f in all_files if self.check_file_size(f, min_size_kb=100)
            ]
            if not large_files:
                logger.error(
                    "No files larger than 100KB found - possible incomplete download"
                )
                return False

            # 5. Try to load and validate config.json if it exists
            config_files = [f for f in all_files if f.endswith("config.json")]
            if config_files:
                try:
                    with open(config_files[0], "r") as f:
                        config = json.load(f)
                    if not isinstance(config, dict):
                        logger.error("config.json is not a valid JSON object")
                        return False
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.error(f"Error reading config.json: {str(e)}")
                    return False

            # 6. Check for any .git* files that might indicate incomplete LFS download
            git_lfs_patterns = [".gitattributes", ".git/lfs"]
            incomplete_lfs = any(
                any(pattern in f for pattern in git_lfs_patterns) for f in all_files
            )
            if incomplete_lfs:
                logger.warning("Found Git LFS files - download might be incomplete")

            logger.info("Model verification completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during verification: {str(e)}")
            return False
