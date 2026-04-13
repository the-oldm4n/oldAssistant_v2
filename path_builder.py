import configparser
import os
import sys
from pathlib import Path
from config import dev_mode, app_name

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

def get_root():
    if dev_mode:
        return get_path() 
    else:
        return get_app_data_dir()

def get_base_directory():
    """Возвращает правильный базовый путь в любом режиме"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys.executable).parent
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_app_data_dir():
    """Возвращает путь к папке данных приложения"""
    appdata = os.getenv('APPDATA')
    return os.path.join(appdata, app_name)

def get_full_filepath():
    """Возвращает полный путь к текущему исполняемому файлу"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        return __file__

def get_config_value(section, key, default=None):
    """Получение конкретного значения из конфига"""
    config = configparser.ConfigParser()
    if dev_mode:
        root = get_path()
    else:
        root = get_base_directory()
    config_path = os.path.join(root, "config.ini")
    if not os.path.exists(config_path):
        return default
    config.read(config_path, encoding='utf-8')
    if not config.has_section(section) or not config.has_option(section, key):
        return default
    return config.get(section, key, fallback=default)
