import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from config import dev_mode
from path_builder import get_app_data_dir


def get_base_directory():
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
        os.makedirs(current_dir, exist_ok=True)
        return current_dir
    else:
        current_dir = os.path.dirname(__file__)
        return current_dir

def get_debuglog_path():
    base = get_base_directory() if dev_mode else get_app_data_dir()
    file_path = os.path.join(base, "log", "logger.log")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    return file_path

def get_log_path():
    base = get_base_directory() if dev_mode else get_app_data_dir()
    file_path = os.path.join(base, "log", "main.log")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    return file_path

assist_log = logging.getLogger("main")
assist_log.setLevel(logging.INFO)
handler = RotatingFileHandler(
    get_log_path(),
    maxBytes=0.5 * 1024 * 1024,
    backupCount=2,
    encoding='utf-8'
)
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
assist_log.addHandler(handler)

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
debug_handler = RotatingFileHandler(
    get_debuglog_path(),
    maxBytes=2 * 1024 * 1024,
    backupCount=2,
    encoding='utf-8'
)
debug_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
debug_handler.setFormatter(debug_formatter)
logger.addHandler(debug_handler)
