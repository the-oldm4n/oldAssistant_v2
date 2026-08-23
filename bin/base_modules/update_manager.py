import json
from packaging import version
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, Signal, QObject, Slot, QTimer, QThreadPool
from PySide6.QtGui import QMouseEvent
from bin.base_modules.check_update import VersionCheckThread, load_changelog
from bin.base_modules.config_manager import get_config_value, set_config_value
from bin.base_modules.download_thread import DownloadThread
from bin.base_modules.update_dialog import UpdateApp
from mygui import sidebar_animated_signal
from log_config import logger


class UpdateManager(QObject):
    """
    
    """
    update_checked = Signal(bool, str)
    def __init__(self, download_dir, main_window, parent=None):
        super().__init__(parent)
        self.download_dir = download_dir
        self.main = main_window
        self.is_manual_check = False
        self.stop_checking = False
        self.count = 0
        self.update_checked.connect(self.handle_update_status)

    def get_version(self, version: str = '0.0.0'):
        vers_on_ini = get_config_value("app", "version")

        if not vers_on_ini or vers_on_ini != version:
            set_config_value("app", "version", f"{version}")
            return version
        return version
    
    def open_update_app(self, event):
        """Запускает скрипт для установки обновления при клике на текст."""
        try:
            self.update_app()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске программы обновления: {e}")
    
    @Slot()
    def update_answer(self, event):
        """Реакция бота на отсутствие обновления"""
        try:
            self.is_manual_check = True  # Устанавливаем флаг ручной проверки
            self.check_update_app()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске программы обновления: {e}")

    def handle_update_status(self, is_success, status_text):
        """Обрабатывает результат проверки обновлений"""
        if not self.is_manual_check:  # Пропускаем реакцию для автоматических проверок
            return

        self.main.handle_update_react(is_success, status_text)

        self.is_manual_check = False

    def update_app(self):
        """Обработка нажатия кнопки 'Установить обновление'"""
        logger.info(f"Вызвано создание update_app")
        dialog = UpdateApp(self.main)
        dialog.main()

    def update_complete(self):
        from send2trash import send2trash

        if os.path.exists(self.download_dir):
            for old_file in os.listdir(self.download_dir):
                old_path = os.path.join(self.download_dir, old_file)
                if os.path.isfile(old_path) and old_file.endswith('.exe'):
                    try:
                        send2trash(old_path)
                        logger.info(f"[MAIN] Файл отправлен в корзину: {old_path}")
                    except Exception as e:
                        logger.error(f"[MAIN] Не удалось удалить {old_path}: {e}")

    def animation_start_load(self):
        self.main.progress_load.show()
        self.main.progress_load.startAnimation()

    def animation_stop_load(self):
        self.main.progress_load.hide()
        self.main.progress_load.stopAnimation()

    def update_answer(self, event):
        try:
            self.check_update_app()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске программы обновления: {e}")

    def check_update_app(self):
        """Проверяет обновления"""
        if self.stop_checking:
            return
        try:
            self.animation_start_load()
            self.main.toggle_update_button()
            self.main.update_label.setText("Searching...")

            task = VersionCheckThread()
            task.signals.version_checked.connect(self.handle_version_check)
            task.signals.check_failed.connect(self.handle_check_failed)

            QThreadPool.globalInstance().start(task)

        except Exception as e:
            self.animation_stop_load()
            logger.error(f"[MAIN] Неожиданная ошибка: {str(e)}", exc_info=True)
            self.main.update_label.setText("Error")
            QTimer.singleShot(2000, self.check_update_app)

    def handle_version_check(self, stable_version):
        # Обработка полученных версий
        new_version = stable_version
        self.latest_version = version.parse(new_version)
        self.current_ver = version.parse(self.main.version)

        type_version = "stable"

        load_changelog(self.main.changelog_file_path)

        if self.latest_version > self.current_ver:
            self.start_full_download()
        else:
            self.animation_stop_load()
            self.main.update_label.setText("Stable")
            self.update_checked.emit(True, "Stable")
            self.main.toggle_update_button()

            self.stop_checking = False
            QTimer.singleShot(4000, lambda: self.update_complete())

    def start_full_download(self):
        """Запуск загрузки полной версии"""
        self.main.update_label.setText("Loading...")
        logger.info("Запуск загрузки обновлений")
        type_version = "stable"
        self.download_thread = DownloadThread(type_version)
        self.download_thread.download_complete.connect(self.handle_download_complete)
        self.download_thread.finished.connect(self.animation_stop_load)
        self.download_thread.start()
        self.main.toggle_update_button()

    def handle_check_failed(self):
        self.count += 1
        self.animation_stop_load()
        self.main.update_label.setText("Error")
        if self.count == 3:
            pass
            self.main.update_label.setText("Server error")  
        if self.count <= 2: # 3 попытки на запрос версии в случае неудачи
            QTimer.singleShot(2000, self.check_update_app)
    
    def handle_download_complete(self, file_path, success=True, skipped=False, error=None):
        self.animation_stop_load()
        logger.info(f"[MAIN] Values: {file_path}, {success}, {skipped}, {error}")
        self.main.update_label.setText("New version")
        if success:
            self.main.show_toast(f"Доступно обновление (v.{self.latest_version})")
            self.stop_checking = True
            if skipped:
                self.main.show_toast("Подготовка к процедуре обновления...\n Не закрывайте приложение")
                logger.info(f"[MAIN][SKIP] Файл уже существует")
                self.open_window_and_update()
            else:
                logger.info(f"[MAIN][OK] Новый файл загружен")
        else:
            logger.error(f"[MAIN] Не удалось скачать: {error}")
        
        self.main.toggle_update_button()

    def open_window_and_update(self):
        """Обработка действия, если апдейт уже был скачан (активация окна)"""
        if not self.main.isVisible():
            self.main.show()
        if self.main.isMinimized():
            self.main.showNormal()
        self.main.raise_()
        self.main.activateWindow()
        QApplication.processEvents()
        QTimer.singleShot(500, lambda: self.update_app())