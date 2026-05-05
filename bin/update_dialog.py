from pathlib import Path
import shutil
import subprocess
from path_builder import get_app_data_dir, get_full_filepath, get_path
from log_config import logger, debuglog
from PySide6.QtWidgets import QDialog
from PySide6.QtCore import QTimer


class UpdateApp(QDialog):
    def __init__(self, parent=None, type_version="stable"):
        super().__init__(parent)
        self.main_window = parent
        self.type_version = type_version

    def main(self):
        self.main_window.show_toast("Начинаю установку...")
        QTimer.singleShot(800, lambda: self.start_update())

    def restart_app(self):
        try:
            updater_exe = self.get_updater_path()
            debuglog.info(updater_exe)
            subprocess.Popen([updater_exe, "--restart-app", "--target", self.get_main_exe_path()], shell=True)
            logger.info("[RESTART] updater.exe запущен с флагом --restart-app")
        except Exception as e:
            logger.error(f"[RESTART] Ошибка при запуске updater.exe: {e}")

    def start_update(self):
        try:
            updater_exe = self.get_updater_path()
            debuglog.info(updater_exe)
            subprocess.Popen([updater_exe, "--no-checked", "--target", self.get_main_exe_path()], shell=False)
            logger.info("[UPD] updater.exe успешно запущен с флагом --no-checked")
        except Exception as e:
            logger.error(f"[UPD] Ошибка при запуске updater.exe: {e}")

    def get_main_exe_path(self):
        path = get_full_filepath()
        logger.info(f"[UPD] Путь к исполняемому файлу {path}")
        return path
    
    def get_updater_path(self) -> str:
        """Возвращает путь к updater.exe, всегда извлекая актуальную версию из ресурсов."""
        
        updater_dir = Path(get_app_data_dir())
        updater_dir.mkdir(exist_ok=True)
        updater_path = updater_dir / "updater.exe"

        source = Path(get_path("updater.exe"))

        if not source.exists():
            raise FileNotFoundError(f"updater.exe не найден в ресурсах: {source}")

        # Принудительно перезаписываем
        shutil.copy2(source, updater_path)
        return str(updater_path)