import os
import sys
import shutil
from log_config import logger
from path_builder import get_app_data_dir

def extract_resource(resource_name, target_path, force_extract=False):
    """
    Извлекает файл или папку из собранного exe в целевой путь
    
    Args:
        resource_name: имя ресурса в _MEIPASS (например, 'templates' или 'config_default.ini')
        target_path: куда сохранить (полный путь)
        force_extract: принудительно перезаписать, даже если существует
    """
    if getattr(sys, 'frozen', False):
        source_dir = sys._MEIPASS
    else:
        source_dir = os.path.dirname(os.path.abspath(__file__))
    
    source_path = os.path.join(source_dir, resource_name)
    logger.info(f"[extract_resource] source_path: {source_path}")

    if not os.path.exists(source_path):
        logger.info(f"[extract_resource] Ресурс не найден: {source_path}")
        raise FileNotFoundError(f"Ресурс не найден: {source_path}")
    
    # Проверяем, существует ли уже
    if not force_extract and os.path.exists(target_path):
        if os.path.isdir(target_path) and os.listdir(target_path):
            logger.info(f"[extract_resource] Папка {target_path} уже существует и не пуста, пропускаем")
            return False
        elif os.path.isfile(target_path):
            logger.info(f"[extract_resource] Файл {target_path} уже существует, пропускаем")
            return False
        else:
            pass
    
    # Создаём целевую папку
    if os.path.isdir(source_path):
        # Если ресурс — папка
        os.makedirs(target_path, exist_ok=True)
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)
        logger.info(f"[extract_resource] Папка распакована: {target_path}")
    else:
        # Если ресурс — файл
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(source_path, target_path)
        logger.info(f"[extract_resource] Файл распакован: {target_path}")
    
    return True

def ensure_resources():
    """Гарантирует наличие всех необходимых ресурсов"""
    app_data_dir = get_app_data_dir()
    resources = [
        ('config.ini', os.path.join(app_data_dir, '.')),
        ('user_data/color.json', os.path.join(app_data_dir, 'user_data/color.json')),
        ('data/script-icons', os.path.join(app_data_dir, 'data/script-icons'))
    ]

    for resource_name, target_path in resources:
        try:
            extract_resource(resource_name, target_path, force_extract=False)
        except Exception as e:
            logger.error(f"[ensure_resources] Ошибка распаковки {resource_name}: {e}")