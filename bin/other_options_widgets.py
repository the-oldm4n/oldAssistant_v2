import csv
import os
from datetime import datetime, date
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QMainWindow, QMessageBox, QCheckBox, QTextEdit
from bin.apply_color_methods import main_apply_colors
from bin.custom_svg_widget import CustomSvgWidget
from bin.download_thread import DownloadThread
from bin.lists import setup_custom_font_label
from bin.progress_bar_widget import SVGProgressBar
from logging_config import logger, debug_logger
from path_builder import get_path


class CensorCounterWidget(QWidget):
    """
    Виджет счетчика матерных слов
    """

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._help_initialized = False
        self.data = []
        self.init_ui()
        self.load_data()
        self.setProperty("helpId", "censor_conter_widget")
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.title = setup_custom_font_label("Статистика по цензуре", font_style="Comfortaa", weight="Medium")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.day_label = QLabel("За день: 0", self)
        self.week_label = QLabel("За последние 7 дней: 0", self)
        self.month_label = QLabel("За последние 30 дней: 0", self)
        self.total_label = QLabel("Всего: 0", self)

        self.day_label.setStyleSheet("background: transparent;")
        self.week_label.setStyleSheet("background: transparent;")
        self.month_label.setStyleSheet("background: transparent;")
        self.total_label.setStyleSheet("background: transparent;")

        layout.addWidget(self.day_label)
        layout.addWidget(self.week_label)
        layout.addWidget(self.month_label)
        layout.addWidget(self.total_label)

        self.reset_button = QPushButton("Сбросить счетчик")
        self.reset_button.clicked.connect(self.reset_censor_counter)
        layout.addWidget(self.reset_button)

        layout.addStretch()

    def load_data(self):
        """Загружает данные из CSV-файла"""
        file_path = get_path("user_settings", "censor_counter.csv")
        
        self.data = []
        
        try:
            if not os.path.exists(file_path):
                debug_logger.warning("Файл censor_counter.csv не найден, создаем новый")
                self.update_labels()
                return
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                # Проверяем наличие обязательных колонок
                if not reader.fieldnames or 'date' not in reader.fieldnames:
                    debug_logger.error("Некорректный формат CSV файла")
                    return
                
                for row in reader:
                    try:
                        parsed_row = {
                            'date': self.parse_date(row.get('date', '')),
                            'score': int(row.get('score', 0) or 0),
                            'total_score': int(row.get('total_score', 0) or 0)
                        }
                        self.data.append(parsed_row)
                    except (ValueError, TypeError) as e:
                        debug_logger.warning(f"Пропущена некорректная строка: {row}, ошибка: {e}")
                        continue
                
            debug_logger.debug(f"Загружено {len(self.data)} записей из CSV")
            self.calculate_scores()
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            debug_logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            self.update_labels()

    def parse_date(self, date_str):
        """Парсит дату из строки в объект date"""
        if not date_str:
            return None
        
        try:
            for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y', '%Y/%m/%d'):
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except ValueError:
                    continue
            debug_logger.warning(f"Не удалось распарсить дату: {date_str}")
            return None
        except Exception as e:
            debug_logger.warning(f"Ошибка парсинга даты {date_str}: {e}")
            return None

    def calculate_scores(self):
        """Вычисляет статистику по дням/неделям/месяцам"""
        try:
            today = date.today()
            
            valid_data = [row for row in self.data if row['date'] is not None]
            
            if not valid_data:
                self.update_labels(0, 0, 0, 0)
                return
            
            day_score = 0
            week_score = 0
            month_score = 0
            total_score = 0
            
            for row in valid_data:
                row_date = row['date']
                score = row['score']
                
                total_score += score
                
                days_diff = (today - row_date).days
                
                if days_diff == 0:
                    day_score += score
                
                if 0 <= days_diff <= 6:
                    week_score += score
                
                if 0 <= days_diff <= 29:
                    month_score += score
            
            # Обновляем UI
            self.day_label.setText(f"За день: {day_score}")
            self.week_label.setText(f"За последние 7 дней: {week_score}")
            self.month_label.setText(f"За последние 30 дней: {month_score}")
            self.total_label.setText(f"Всего: {total_score}")
            
        except Exception as e:
            logger.error(f"Ошибка в calculate_scores: {e}", exc_info=True)
            debug_logger.error(f"Ошибка в calculate_scores: {e}", exc_info=True)
            self.update_labels(0, 0, 0, 0)

    def update_labels(self, day=0, week=0, month=0, total=0):
        """Обновляет метки с заданными значениями"""
        self.day_label.setText(f"За день: {day}")
        self.week_label.setText(f"За последние 7 дней: {week}")
        self.month_label.setText(f"За последние 30 дней: {month}")
        self.total_label.setText(f"Всего: {total}")

    def reset_censor_counter(self):
        """Сбрасывает счетчик, обнуляя таблицу censor_counter.csv"""
        result = self.assistant.show_message(
            text="Точно сбросить значения?",
            title="Сброс счетчика",
            message_type="warning",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result != QMessageBox.StandardButton.Yes:
            logger.info("Сброс счетчика отменен.")
            debug_logger.info("Сброс счетчика отменен.")
            return
        
        CSV_FILE = get_path('user_settings', 'censor_counter.csv')
        
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['date', 'score', 'total_score'])
        
        self.data = []
        
        self.update_labels(0, 0, 0, 0)
        
        logger.info("Счетчик успешно сброшен.")
        debug_logger.info("Счетчик успешно сброшен.")


class CheckUpdateWidget(QWidget):
    """
    Виджет для ручной проверки обновлений, выбора определенной версии из списка доступных
    """

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._help_initialized = False
        self.init_ui()
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_manager.apply_progressbar(key="QPushButton", widget=self.progress, style="parts")
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        # Основной layout
        layout = QVBoxLayout(self)

        self.title = setup_custom_font_label("Центр обновлений", font_style="Comfortaa", weight="Medium")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.check_button = QPushButton("Проверить обновления")
        self.check_button.clicked.connect(self.assistant.check_update_app)
        self.check_button.setProperty("helpId", "check_button_update")
        layout.addWidget(self.check_button)

        self.update_check = QCheckBox("Проверить свежие бета-версии", self)
        self.update_check.setStyleSheet("background: transparent;")
        self.update_check.setChecked(self.assistant.beta_version)
        self.update_check.stateChanged.connect(self.toggle_beta_version)
        self.update_check.setProperty("helpId", "check_exp_update")
        layout.addWidget(self.update_check)

        self.rollback = QPushButton("Откат до стабильной версии")
        self.rollback.clicked.connect(self.wait_and_rollback)
        self.rollback.setProperty("helpId", "rollback_version")
        layout.addWidget(self.rollback)

        layout.addStretch()
        
        self.progress = SVGProgressBar(style="circle", show_text=False, circle_size=200)
        self.progress.hide()
        self.progress.setProperty("helpId", "rollback_version")
        layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

    def toggle_beta_version(self, state):
        """Включает/отключает проверку экспериментальных версий"""
        self.assistant.beta_version = state == Qt.CheckState.Checked

    def wait_and_rollback(self):
        # Показываем диалог и получаем результат
        result = self.assistant.show_message(
            "Уверены в своих действиях?",
            "Запрос на откат версии",
            "question",
            buttons=QMessageBox.StandardButton.Ok
        )

        # Обрабатываем результат
        if result == QMessageBox.StandardButton.Ok:
            self.rollback_stable_version()
        else:
            pass

    def rollback_stable_version(self):
        try:
            self.start_load()
            self.download_thread = DownloadThread(type_version="stable")
            self.download_thread.download_complete.connect(
                lambda: self.assistant.update_app(type_version="stable"))
            self.download_thread.finished.connect(self.finish_load)
            self.download_thread.start()
        except Exception as e:
            self.progress.hide()
            self.progress.stopAnimation()
            self.rollback.show()
            self.assistant.show_notification_message(f"Ошибка: {e}")
            debug_logger.error(f"Ошибка в методе rollback_stable_version: {e}")

    def start_load(self):
        self.progress.show()
        self.rollback.hide()
        self.progress.startAnimation()

    def finish_load(self):
        self.progress.hide()
        self.rollback.setText("Ожидайте")
        self.progress.stopAnimation()


class DebugLoggerWidget(QWidget):
    """Виджет для открытия папки с подробными логами"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        self._help_initialized = False
        self.check_button = None
        self.init_ui()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
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
            debuglog = DebuglogWindow(self)
            debuglog.show()
        except Exception as e:
            logger.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")
            debug_logger.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")


class DebuglogWindow(QMainWindow):
    """
    Окно с логами
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.drag_pos = None
        self.init_ui()
        self.parent_window.assistant.style_manager.apply_color_svg(self.close_svg, strength=0.90,
                                                                   specified_color="#FF0000")

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
        self.title_bar_widget.setObjectName("TitleBar")
        self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
        self.title_bar_layout.setContentsMargins(10, 5, 10, 5)
        self.title_bar_layout.setSpacing(5)

        self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
        self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release

        title_label = setup_custom_font_label("Подробные логи", font_style="Comfortaa", weight="Medium")
        title_label.setStyleSheet("background: transparent;")
        title_label.setObjectName("TitleLabel")
        self.title_bar_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_bar_layout.addStretch()

        close_btn = QPushButton("")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.icon_close_path, close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_bar_layout.addWidget(close_btn)

        root_layout.addWidget(self.title_bar_widget)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.log_area = QTextEdit()
        self.log_area.setStyleSheet("background: transparent;")
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas"))
        self.log_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
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
        path = get_path("log", "debug_assist.log")
        try:
            if not os.path.exists(path):
                logger.info("Файл логов не найден. Создаем новый.")
                with open(path, "w", encoding="utf-8"):
                    pass  # Создаем пустой файл

            with open(path, "r", encoding="utf-8-sig", errors="replace") as file:
                # Эффективное чтение последних 1000 строк без загрузки всего файла в память
                lines = []
                buffer_size = 8192  # Размер буфера для чтения
                file_size = os.path.getsize(path)

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
            logger.error(f"Ошибка при чтении файла логов: {e}")
            self.log_area.append(f"Ошибка при чтении файла логов: {e}")
