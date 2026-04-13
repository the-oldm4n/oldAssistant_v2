import os
import sys
import shutil
from pathlib import Path
from log_config import debuglog
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
        # Запущены из exe
        source_dir = sys._MEIPASS
    else:
        # Запущены из скрипта (режим разработки)
        source_dir = os.path.dirname(os.path.abspath(__file__))
    
    source_path = os.path.join(source_dir, resource_name)
    
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Ресурс не найден: {source_path}")
    
    # Проверяем, нужно ли распаковывать
    if not force_extract and os.path.exists(target_path):
        # Если это папка, проверяем не пустая ли она
        if os.path.isdir(target_path) and os.listdir(target_path):
            debuglog.info(f"Папка {target_path} уже существует и не пуста, пропускаем")
            return False
        elif os.path.isfile(target_path):
            debuglog.info(f"Файл {target_path} уже существует, пропускаем")
            return False
    
    # Создаём целевую директорию если нужно
    os.makedirs(os.path.dirname(target_path) if os.path.isfile(target_path) else target_path, exist_ok=True)
    
    # Копируем
    if os.path.isdir(source_path):
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)
        debuglog.info(f"Папка распакована: {target_path}")
    else:
        shutil.copy2(source_path, target_path)
        debuglog.info(f"Файл распакован: {target_path}")
    
    return True


def ensure_resources():
    """Гарантирует наличие всех необходимых ресурсов"""
    app_data_dir = get_app_data_dir()
    
    resources = [
        ('config.ini', os.path.join(app_data_dir, '.')),
        ('user_data', os.path.join(app_data_dir, 'user_data')),
    ]
    
    for resource_name, target_path in resources:
        try:
            extract_resource(resource_name, target_path, force_extract=False)
        except Exception as e:
            debuglog.error(f"Ошибка распаковки {resource_name}: {e}")