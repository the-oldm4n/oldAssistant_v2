import os
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMainWindow, QTextEdit
from bin.base_modules.resize_manager import ResizeManager
from bin.utils import setup_custom_font_label
from log_config import logger, assist_log
from mygui import CustomSvgWidget
from path_builder import get_path


class DebugLoggerWidget(QWidget):
    """Виджет для открытия папки с подробными логами"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPageWidget")
        self._help_initialized = False
        self.check_button = None
        self.init_ui()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        # Основной layout
        layout = QVBoxLayout(self)

        self.title = setup_custom_font_label("Подробные логи", font_style="Comfortaa", weight="Medium")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.check_button = QPushButton("Файл логов")
        self.check_button.clicked.connect(self.open_folder)
        self.check_button.setProperty("helpId", "open_log_folder")
        layout.addWidget(self.check_button)

        self.open_button = QPushButton("Посмотреть последние логи")
        self.open_button.clicked.connect(self.load_window)
        self.open_button.setProperty("helpId", "open_log_file")
        layout.addWidget(self.open_button)

        layout.addStretch()

    def open_folder(self):
        path = get_path("log")
        os.startfile(path)

    def load_window(self):
        try:
            logger = DebuglogWindow(log_path=self.main.debuglog_file_path, parent=self)
            logger.show()
        except Exception as e:
            assist_log.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")
            logger.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")


class DebuglogWindow(QMainWindow):
    """
    Окно с логами
    """
    def __init__(self, log_path, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.drag_pos = None
        self.debug_log_path = log_path
        self.init_ui()
        self.parent_window.main.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(1000, 600)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("WindowContainer")
        self.setCentralWidget(self.central_widget)

        root_layout = QVBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar_widget = QWidget()
        self.title_bar_widget.setObjectName("TitleBarV2")
        self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
        self.title_bar_layout.setContentsMargins(10, 0, 0, 0)

        self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
        self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release

        title_label = setup_custom_font_label("Подробные логи", font_style="Comfortaa", weight="Medium")
        title_label.setStyleSheet("background: transparent; font-size: 18px;")
        title_label.setObjectName("TitleLabel")
        self.title_bar_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_bar_layout.addStretch()

        close_btn = QPushButton()
        close_btn.setObjectName("TitleBarCloseBtn")
        close_btn.setFixedSize(50, 38)
        close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.icon_close_path, close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(12, 7)
        self.title_bar_layout.addWidget(close_btn)

        root_layout.addWidget(self.title_bar_widget)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("TransparentWidget")
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas"))
        self.log_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.log_area.setStyleSheet("font-size: 14px;")
        self.load_debuglog()

        main_layout.addWidget(self.log_area)

        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(close_button)

        root_layout.addWidget(self.content_widget)

    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Запоминаем позицию относительно главного окна
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            # Вычисляем смещение и перемещаем главное окно
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

    def load_debuglog(self):
        
        try:
            if not os.path.exists(self.debug_log_path):
                assist_log.info("Файл логов не найден. Создаем новый.")
                with open(self.debug_log_path, "w", encoding="utf-8"):
                    pass  # Создаем пустой файл

            with open(self.debug_log_path, "r", encoding="utf-8-sig", errors="replace") as file:
                # Эффективное чтение последних 1000 строк без загрузки всего файла в память
                lines = []
                buffer_size = 8192  # Размер буфера для чтения
                file_size = os.path.getsize(self.debug_log_path)

                # Если файл небольшой, читаем обычным способом
                if file_size <= buffer_size * 10:  # примерно 80KB
                    lines = file.readlines()[-1000:]
                else:
                    # Для больших файлов используем эффективный алгоритм
                    blocks = []
                    block_count = 0

                    # Читаем файл с конца блоками
                    while file_size > 0 and len(lines) < 1000:
                        read_size = min(buffer_size, file_size)
                        file.seek(file_size - read_size)
                        block = file.read(read_size)
                        blocks.append(block)

                        # Считаем строки в блоке
                        line_count = block.count('\n')
                        lines_found = line_count - (1 if file_size - read_size > 0 else 0)

                        if len(lines) + lines_found >= 1000:
                            break

                        file_size -= read_size
                        block_count += 1

                    # Собираем все строки из прочитанных блоков
                    all_text = ''.join(reversed(blocks))
                    lines = all_text.splitlines()[-1000:]

                existing_logs = "\n".join(lines)
                self.log_area.append(existing_logs)
                self.last_position = file.tell()

        except Exception as e:
            assist_log.error(f"Ошибка при чтении файла логов: {e}")
            logger.error(f"Ошибка при чтении файла логов: {e}")
            self.log_area.append(f"Ошибка при чтении файла логов: {e}")