import os
import platform
import subprocess
import sys
from path_builder import get_base_directory
from PySide6.QtCore import QObject
from log_config import logger
from config import app_name, base_name


class AutostartManager(QObject):
    """
    
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window

    def check_autostart(self):
        """Проверка автозапуска (кроссплатформенно)"""
        system = platform.system()
        
        if system == "Windows":
            task_name = app_name
            command = ['schtasks', '/query', '/tn', task_name]
            
            try:
                subprocess.run(command, check=True, capture_output=True, text=True, encoding='cp866')
                self.main.autostart_app = True
                return True
            except subprocess.CalledProcessError:
                self.main.autostart_app = False
                return False
                
        elif system == "Linux":
            home = os.path.expanduser('~')
            desktop_file = os.path.join(home, '.config', 'autostart', f'{app_name}.desktop')
            self.main.autostart_app = os.path.exists(desktop_file)
            return True
        else:
            self.main.autostart_app = False
            return False

    def toggle_autostart_win(self):
        """Переключает состояние и меняет цвет иконки"""
        self.main.autostart_app = not self.main.autostart_app

        if self.main.autostart_app:
            result = self.add_to_autostart()
        else:
            result = self.remove_from_autostart()

        return result

    def add_to_autostart(self):
        """Добавление программы в автозапуск (кроссплатформенно)"""
        system = platform.system()
        
        if system == "Windows":
            self._add_to_autostart_windows()
        elif system == "Linux":
            self._add_to_autostart_linux()
        else:
            logger.warning(f"[AUTOSTART MANAGER][add_to_autostart] Автозапуск не поддерживается на {system}")

    def _add_to_autostart_windows(self):
        """Windows: через планировщик задач"""
        current_directory = get_base_directory()

        task_name = app_name
        target_path = os.path.join(current_directory, base_name)

        if not os.path.isfile(target_path):
            logger.error(f"[AUTOSTART MANAGER][_add_to_autostart_windows] Файл не найден: {target_path}")
            self.main.show_toast(f"Файл приложения для добавления в автозапуск не найден. (Путь поиска {target_path})")
            return False
        
        command = [
            'schtasks', '/create', '/tn', task_name,
            '/tr', f'"{target_path}"', '/sc', 'onlogon',
            '/rl', 'highest', '/f'
        ]
        
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='cp866')
            logger.info(f"[AUTOSTART MANAGER][_add_to_autostart_windows] Добавлено в автозапуск: {task_name}")
            self.main.show_toast(f"Добавлено в автозапуск")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[AUTOSTART MANAGER][_add_to_autostart_windows] Ошибка: {e.stderr}")
            self.main.show_toast(f"Ошибка при добавлении в автозапуск: {e.stderr}")
            return False

    def _add_to_autostart_linux(self):
        """Linux: через .desktop файл (автозапуск в Xfce/GNOME)"""
        home = os.path.expanduser('~')
        autostart_dir = os.path.join(home, '.config', 'autostart')
        os.makedirs(autostart_dir, exist_ok=True)
        
        desktop_file = os.path.join(autostart_dir, f'{app_name}.desktop')
        
        # Определяем путь к исполняемому файлу
        if getattr(sys, 'frozen', False):
            exec_path = os.path.join(get_base_directory(), app_name)
        else:
            exec_path = sys.executable
            script_path = os.path.abspath(__file__)
        
        desktop_content = f"""[Desktop Entry]
            Type=Application
            Name={app_name}
            Comment={app_name}
            Exec={exec_path}
            Icon=system-run
            Terminal=false
            Hidden=false
            X-GNOME-Autostart-enabled=true
            """
        
        with open(desktop_file, 'w') as f:
            f.write(desktop_content)
        
        os.chmod(desktop_file, 0o755)
        logger.info(f"[AUTOSTART MANAGER][_add_to_autostart_linux] Добавлено в автозапуск: {desktop_file}")
        self.main.show_toast(f"Добавлено в автозапуск")

    def remove_from_autostart(self):
        """Удаление из автозапуска (кроссплатформенно)"""
        system = platform.system()
        
        if system == "Windows":
            self._remove_from_autostart_windows()
        elif system == "Linux":
            self._remove_from_autostart_linux()

    def _remove_from_autostart_windows(self):
        task_name = app_name
        
        command = ['schtasks', '/delete', '/tn', task_name, '/f']
        
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='cp866')
            logger.info(f"[AUTOSTART MANAGER][_remove_from_autostart_windows] Удалено из автозапуска: {task_name}")
            return self.main.show_toast(f"Удалено из автозапуска")
        except subprocess.CalledProcessError as e:
            if "не существует" not in e.stderr:
                logger.error(f"[AUTOSTART MANAGER][_remove_from_autostart_windows] Ошибка: {e.stderr}")
                self.main.show_toast(f"Ошибка при удалении из автозапуска: {e.stderr}")

    def _remove_from_autostart_linux(self):
        home = os.path.expanduser('~')
        desktop_file = os.path.join(home, '.config', 'autostart', f'{app_name}.desktop')
        
        if os.path.exists(desktop_file):
            os.remove(desktop_file)
            logger.info(f"[AUTOSTART MANAGER][_remove_from_autostart_linux] Удалено из автозапуска: {desktop_file}")
            return self.main.show_toast(f"Удалено из автозапуска")

    
