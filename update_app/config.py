# -----------------------------------------
    # CHECK VALUES APP_NAME AND OTHER, ICON.ICO AND LOGO-APP.SVG
# -----------------------------------------

import configparser
import os
import socket
import sys
from pathlib import Path
import requests

dev_mode = False

app_name = "Voxodium"
base_name = "Voxodium.exe"
update_name = "Voxodium-new.exe"
user_agent = "VOXODIUM"
prefix_url = "voxodium"
session_app_id = "voxodium_updater"

_domain_cache = None

def is_local_server_running(host='127.0.0.1', port=5000, timeout=0.3):
    """Проверяет, открыт ли порт на локалке"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def get_domain():
    global _domain_cache
    if _domain_cache:
        return _domain_cache
    
    local_url = "http://127.0.0.1:5000"
    main_url = "https://owl-app.ru"
    
    if is_local_server_running():
        _domain_cache = local_url
    else:
        _domain_cache = main_url
    
    return _domain_cache

domain = get_domain()

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

def get_config_value(section, key, default=None):
    """Получение конкретного значения из конфига"""
    config = configparser.ConfigParser()
    if dev_mode:
        root = get_path()
    else:
        root = get_directory()
    config_path = os.path.join(root, "config.ini")
    if not os.path.exists(config_path):
        return default
    config.read(config_path, encoding='utf-8')
    if not config.has_section(section) or not config.has_option(section, key):
        return default
    return config.get(section, key, fallback=default)

APP_VERSION = get_config_value("app", "version", "1.0.0")
USER_AGENT = f"{user_agent}/Updater/v.{APP_VERSION}/"

session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT
})