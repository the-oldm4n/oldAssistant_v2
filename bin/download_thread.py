from PySide6.QtCore import QThread, Signal, QPropertyAnimation
from PySide6.QtWidgets import QProgressBar

from bin.check_update import download_update


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
 

class SliderProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)

        # Инициализация анимации
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(2000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(100)
        self.animation.setLoopCount(-1)

    def startAnimation(self):
        """Запуск анимации ползунка"""
        self.animation.start()

    def stopAnimation(self):
        """Остановка анимации"""
        self.animation.stop()
        self.setValue(0)