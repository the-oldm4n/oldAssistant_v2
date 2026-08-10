import logging
import os
from config import dev_mode
from utils import get_path, get_app_data_dir

logger = logging.getLogger("update")
logger.setLevel(logging.DEBUG)

# Формат сообщений
formatter = logging.Formatter(
    fmt="[{levelname}] {asctime} | {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S"
)

if dev_mode:
    base_path = get_path()
else:
    base_path = get_app_data_dir()

file_path = os.path.join(base_path, "update.log")
file_handler = logging.FileHandler(file_path, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)