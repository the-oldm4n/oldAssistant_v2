import configparser
import logging
import os
import sys
from pathlib import Path
from config import app_name

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("update")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="[{levelname}] {asctime} | {message}",
    style="{"
)

file_handler = logging.FileHandler("update.log", encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

if not logger.handlers:
    logger.addHandler(file_handler)

def get_base_directory():
    """Возвращает правильный базовый путь в любом режиме"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys.executable).parent
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_directory():
    """Автоматически определяет корневую директорию для всех режимов"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        base = Path(sys.executable).parent
        internal = base / '_internal'
        return internal if internal.exists() else base
    return Path(__file__).parent

def get_path(*path_parts):
    """Строит абсолютный путь, идентичный в обоих режимах"""
    return str(get_directory() / Path(*path_parts))

def get_app_data_dir():
    """Возвращает путь к папке данных приложения"""
    appdata = os.getenv('APPDATA')
    return os.path.join(appdata, app_name)

def get_config_value(section, key, default=None):
    """Получение конкретного значения из конфига"""
    config = configparser.ConfigParser()
    root = get_base_directory()
    config_path = os.path.join(root, "config.ini")
    logger.info(f"config_path:{config_path}")
    if not os.path.exists(config_path):
        logger.info(f"File is not found")
        return default
    config.read(config_path, encoding='utf-8')
    if not config.has_section(section) or not config.has_option(section, key):
        return default
    return config.get(section, key, fallback=default)


class UpdateStatusSignal(QObject):
    status_update = Signal(str, int)

update_signal = UpdateStatusSignal()


class RunAppSignal(QObject):
    run_main_app = Signal()

run_app_signal = RunAppSignal()