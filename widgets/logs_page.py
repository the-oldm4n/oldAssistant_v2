import os
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import Qt

from bin.monitoring_log_widget import MonitorLogWidget
from bin.ram_monitor import DualRAMProgressWidget
from log_config import assist_log


class LogsPage(QWidget):
    def __init__(self, main_window=None, log_path=""):
        super().__init__()
        self.main = main_window
        self.log_file_path = log_path
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPage")

        if not os.path.exists(self.log_file_path):
            self.init_error()
        else:
            self.init_ui()
            self.log_area.start_active_mode()

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.addSpacing(0)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("CustomPageWidget")

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.addSpacing(10)

        self.log_area = MonitorLogWidget(log_file_path=self.log_file_path, max_lines=100)
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas"))
        self.log_area.setStyleSheet("font-size: 16px")

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.addSpacing(10)

        self.clear_log_btn = QPushButton("Очистить логи")
        self.clear_log_btn.clicked.connect(self.log_area.clear_logs)

        self.open_log_file = QPushButton("Открыть папку с логами")
        self.open_log_file.clicked.connect(self.open_folder_logs)

        self.content_layout.addWidget(self.log_area)
        self.buttons_layout.addWidget(self.clear_log_btn, stretch=1)
        self.buttons_layout.addWidget(self.open_log_file, stretch=1)
        self.content_layout.addLayout(self.buttons_layout)

        self.main_layout.addWidget(self.content_widget)

        self.ram_info = DualRAMProgressWidget()
        self.main_layout.addWidget(self.ram_info)

    def init_error(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addSpacing(0)

        self.label_error = QLabel("Файл логов не найден")
        self.label_error.setStyleSheet("font-size: 25px; background: transparent;")

        self.main_layout.addWidget(self.label_error, alignment=Qt.AlignmentFlag.AlignCenter)

    def send_msg(self, msg=""):
        self.main.show_toast(msg)

    def open_folder_logs(self):
        try:
            path = os.path.dirname(self.log_file_path)

            os.startfile(path)

        except Exception as e:
            self.send_msg(f"Ошибка при открытии папки: {e}")
            assist_log.error(f"[LOGSPAGE] Ошибка при открытии папки с логами: {e}")
