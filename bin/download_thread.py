from PySide6.QtCore import QThread, Signal, QPropertyAnimation
from PySide6.QtWidgets import QProgressBar

from bin.check_update import download_delta_files, download_update


class DownloadThread(QThread):
    download_complete = Signal(str, bool, bool, str)
    progress_signal = Signal(str)

    def __init__(self, type_version, version=None, parent=None):
        super().__init__(parent)
        self.type_version = type_version
        self.version = version

    def run(self):
        download_update(type_version=self.type_version,
                        on_complete=self._handle_complete,
                        version=self.version)
        self.progress_signal.emit("Начинаем загрузку...")

    def _handle_complete(self, file_path, success=True, skipped=False, error=None):
        self.download_complete.emit(file_path, success, skipped, error)
       
        
class DeltaDownloadThread(QThread):
    download_complete = Signal(str, bool, bool, str, bool)
    progress_signal = Signal(str)

    def __init__(self, files_to_update, manifest, auth_manager, parent=None):
        super().__init__(parent)
        self.files_to_update = files_to_update
        self.manifest = manifest
        self.auth_manager = auth_manager

    def run(self):
        download_delta_files(
            files_to_update=self.files_to_update,
            manifest=self.manifest,
            auth_manager=self.auth_manager,
            on_complete=self._handle_complete,
            on_progress=self._handle_progress
        )
        self.progress_signal.emit("Начинаем загрузку...")

    def _handle_complete(self, file_path, success=True, skipped=False, error=None, batch=False):
        self.download_complete.emit(file_path, success, skipped, error, batch)
        
    def _handle_progress(self, status, progress):  # ✅ Новый метод для прогресса
        self.progress_signal.emit(status)


class SliderProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)  # Скрываем текст

        # Инициализация анимации
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(2000)  # Продолжительность одного цикла
        self.animation.setStartValue(0)
        self.animation.setEndValue(100)
        self.animation.setLoopCount(-1)  # Бесконечное повторение

    def startAnimation(self):
        """Запуск анимации ползунка"""
        self.animation.start()

    def stopAnimation(self):
        """Остановка анимации"""
        self.animation.stop()
        self.setValue(0)  # Сброс в начальное положение