import sys
from pathlib import Path

from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PRIME_DIR = f"{BASE_DIR}/logs/"

dev_config = {
    "handlers": [
        {"sink": sys.stdout, "level": "INFO"},
    ],
}

logger.configure(**dev_config)

service_logger = logger
