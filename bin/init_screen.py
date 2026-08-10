import ctypes
import os
import re
import pyaudio
from PySide6.QtWidgets import QLabel, QVBoxLayout, QApplication, QWidget,\
    QDialog, QGraphicsColorizeEffect, QSizePolicy, QMessageBox
from PySide6.QtCore import Signal, QTimer, Qt, QThread
from bin.base_modules.toast_notification import SimpleNotif
from mygui import main_apply_colors, CustomSvgWidget, SVGProgressBar
from path_builder import get_app_data_dir, get_path
from log_config import debuglog
from config import dev_mode 

if dev_mode:
    style_path = get_path("user_data", "color.json")
else:
    style_path = os.path.join(get_app_data_dir(), "user_data", "color.json")


class InitScreen(QWidget):
    """
    Окно инициализации программы, проверка файлов и необходимых параметров перед основным запуском
    """
    init_complete = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth = None
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_path = style_path
        self.svg_path = get_path("bin", "icons", "logo-app.svg")
        self.init_ui()
        self.apply_styles()
        self.start_checks()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(250, 250)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(15, 0, 15, 20)
        content_layout.addStretch()

        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(120, 120)
        self.svg_image.setStyleSheet("""
                    background: transparent;
                    border: none;
                    outline: none;
                """)
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)

        content_layout.addStretch()

        self.progress = SVGProgressBar(
            svg_widget=self.svg_image,
            style="circle",
            circle_size=180,
            show_text=False,
            line_width=3)
        content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Инициализация...", self)
        self.label.setStyleSheet("background: transparent; min-height: 35px; max-height: 35px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content_layout.addWidget(self.label)

        self.setLayout(layout)
        layout.addWidget(self.main_widget, 1)

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_progressbar(widget=self.progress)

            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):
                    selector = widget
                else:
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            self.setStyleSheet(style_sheet)
            self.main_widget.setStyleSheet("""border-radius:20px""")
        except Exception as e:
            debuglog.error(f"[INIT] Ошибка в методе apply_styles: {e}")

    def show_message(self, text, title="Уведомление", message_type="info", buttons=QMessageBox.StandardButton.Ok):
        try:
            message = SimpleNotif(
                parent=self,
                message=text,
                title=title,
                message_type=message_type,
                buttons=buttons
            )
            return message.exec_()
        except Exception as e:
            debuglog.error(f"[INIT] Ошибка при показе уведомления(оконного): {e}")
            return QDialog.DialogCode.Rejected

    def start_checks(self):
        self.check_thread = CheckThread()
        self.check_thread.progress_update.connect(self.update_progress)
        self.check_thread.checks_complete.connect(self.on_checks_complete)
        self.check_thread.start()

    def update_progress(self, message, value):
        self.label.setText(message)
        self.progress.setValue(value)
        QApplication.processEvents()

    def on_checks_complete(self, result, error=""):
        if result:
            QTimer.singleShot(50, lambda: self.finalize_initialization(True))
        else:
            self.label.setText(f"Ошибка")
            self.show_message(text=f"{error}", title="Ошибка", message_type="error")
            self.init_complete.emit(False)
            QTimer.singleShot(1000, lambda: self.close())

    def finalize_initialization(self, success):
        self.init_complete.emit(success)
        self.close()


class CheckThread(QThread):
    checks_complete = Signal(bool, str)
    progress_update = Signal(str, int)

    def run(self):
        try:
            self.progress_update.emit("Проверка прав администратора...", 0)
            if not self.check_admin():
                self.progress_update.emit("Ошибка: Нет прав администратора!", 0)
                self.checks_complete.emit(False, "Ошибка: Нет прав администратора!")
                return
            for i in range(1, 31):
                if i % 2 == 0:
                    QThread.msleep(5)
                    self.progress_update.emit("Проверка прав администратора...", i)

            if not self.check_audio_devices():
                return
            
            for i in range(31, 60):
                if i % 2 == 0:
                    QThread.msleep(5)
                    self.progress_update.emit("Поиск устройств ввода/вывода...", i)

            if self.check_main_path(get_path()):
                self.checks_complete.emit(False, "Ошибка: В пути обнаружена кириллица!")
                return
            
            for i in range(61, 99):
                if i % 2 == 0:
                    QThread.msleep(5)
                    self.progress_update.emit("Проверяю путь до исполняемого файла...", i)

            self.progress_update.emit("Запуск...", 100)
            self.checks_complete.emit(True, "")
        except Exception as e:
            self.progress_update.emit(f"Критическая ошибка: {str(e)}", 0)
            self.checks_complete.emit(False, "")

    # noinspection PyUnresolvedReferences
    def check_admin(self):
        """Проверка прав администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def check_main_path(self, path):
        self.progress_update.emit("Проверяю путь до исполняемого файла...", 61)
        cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]')
        return bool(cyrillic_pattern.search(path))

    def input_device(self):
        p = pyaudio.PyAudio()
        try:
            default_input_device = p.get_default_input_device_info()
            return True
        except IOError:
            self.progress_update.emit("Ошибка: Нет устройств ввода звука.", 31)
            self.checks_complete.emit(False, "Ошибка: Нет устройств ввода звука")
            return False

    def output_device(self):
        p = pyaudio.PyAudio()
        try:
            default_output_device = p.get_default_output_device_info()
            return True
        except IOError:
            self.progress_update.emit("Ошибка: Нет устройств вывода звука.", 46)
            self.checks_complete.emit(False, "Ошибка: Нет устройств вывода звука")
            return False
        finally:
            p.terminate()

    def check_audio_devices(self):
        if not self.input_device() or not self.output_device():
            return False
        return True
