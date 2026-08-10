import os
import platform
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from config import app_name

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

def get_resource_path(relative_path):
    """Универсальный путь для ресурсов внутри/снаружи EXE"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent

    return base_path / relative_path

def get_base_directory():
    """Возвращает правильный базовый путь в любом режиме"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys.executable).parent
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_app_data_dir():
    """Возвращает путь к папке данных приложения (кросс-платформенно)"""
    if platform.system() == "Windows":
        base = os.getenv('APPDATA')
        result = os.path.join(base, app_name)
    else:  # Linux, macOS и другие
        # Используем XDG стандарт: ~/.local/share/
        home = os.path.expanduser('~')
        base = os.path.join(home, '.local', 'share')
        result = os.path.join(base, app_name)
    
    os.makedirs(result, exist_ok=True)
    return result


class UpdateStatusSignal(QObject):
    status_update = Signal(str, int)

update_signal = UpdateStatusSignal()


class RunAppSignal(QObject):
    run_main_app = Signal()

run_app_signal = RunAppSignal()