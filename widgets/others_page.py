from collections import defaultdict
import csv
import os
from datetime import datetime, date, timedelta
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QMainWindow, QMessageBox, QCheckBox, QTextEdit
from bin.graph_widget import SimpleGraph
from bin.stacked_widget import SlidingStackedWidget
from mygui import CustomSvgWidget, main_apply_colors, SVGProgressBar, color_signal
from bin.download_thread import DownloadThread
from bin.lists import setup_custom_font_label
from bin.signals import censor_signal
from log_config import logger, debuglog
from path_builder import get_path, get_app_data_dir
from config import dev_mode

if dev_mode:
    folder_links = get_path('user_data', "links")
    links_file = get_path('user_data', 'links.json')
    commands_file = get_path('user_data', 'commands.json')
    censor_file = get_path("user_data", "censor_counter.csv")
else:
    folder_links = os.path.join(get_app_data_dir(), 'user_data', "links")
    links_file = os.path.join(get_app_data_dir(), 'user_data', 'links.json')
    commands_file = os.path.join(get_app_data_dir(), 'user_data', 'commands.json')
    censor_file = os.path.join(get_app_data_dir(), "user_data", "censor_counter.csv")


class OthersPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        self.main = main_window
        self.setObjectName("CustomPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        self.button_panel = QWidget()
        self.button_panel.setObjectName("TabPanel")
        button_layout = QHBoxLayout(self.button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        
        self.content_container = SlidingStackedWidget(self)
        
        censor_widget = CensorCounterWidget(self.main, self)
        updates_widget = CheckUpdateWidget(self.main, self)
        debug_widget = DebugLoggerWidget(self.main, self)
        
        self.content_container.add_page(censor_widget)
        self.content_container.add_page(updates_widget)
        self.content_container.add_page(debug_widget)
        
        buttons_data = [
            {
                "key": "censor",
                "text": "Счетчик цензуры",
                "icon_path": self.main.icon_censor_path,
                "tooltip": "Счетчик цензуры",
                "index": 0,
                "widget": censor_widget
            },
            {
                "key": "updates",
                "text": "Обновления",
                "icon_path": self.main.icon_updates_path,
                "tooltip": "Обновления",
                "index": 1,
                "widget": updates_widget
            },
            {
                "key": "debugger",
                "text": "Подробные логи",
                "icon_path": self.main.icon_logs_path,
                "tooltip": "Подробные логи",
                "index": 2,
                "widget": debug_widget
            }
        ]
        
        self.nav_buttons = []
        self.nav_svgs = []
        
        for data in buttons_data:
            btn = QPushButton()
            btn.setFixedSize(60, 40)
            btn.setObjectName("TabBtn")
            btn.setToolTip(data["tooltip"])
            
            if data["icon_path"]:
                svg = CustomSvgWidget(data["icon_path"], btn)
                svg.setFixedSize(35, 35)
                svg.move(12, 2)
                self.main.style_manager.apply_color_svg(svg)
                self.nav_svgs.append(svg)
            
            btn.clicked.connect(lambda checked, idx=data["index"]: self.switch_page(idx, "bottom"))
            
            self.nav_buttons.append(btn)
            button_layout.addWidget(btn)
        
        button_layout.addStretch()
        
        self.main_layout.addWidget(self.button_panel)
        self.main_layout.addWidget(self.content_container)
        
        self.switch_page(0, "bottom")


    def switch_page(self, index, direction="right"):
        self.content_container.switch_to(index, direction)

        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_colors(self):
        for svg in self.nav_svgs:
            self.main.style_manager.apply_color_svg(svg)


class CensorCounterWidget(QWidget):
    """
    Виджет счетчика матерных слов
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        censor_signal.update_count.connect(self.censor_counter)
        self.main = main_window
        self.parent = parent
        self._help_initialized = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPageWidget")
        self.data = []
        self.init_ui()
        self.load_data()
        self.setProperty("helpId", "censor_conter_widget")
        self.calculate_favorite_word()
        self.update_colors()

    def refresh_data(self):
        debuglog.info("Refresh data in censor counter")
        self.load_data()
        self.calculate_favorite_word()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def update_colors(self):
        """Обновляет цвета графика при смене темы"""
        if hasattr(self, 'graph'):
            main_color = self.main.style_manager.get_svg_color()

            self.graph.update_colors(
                line_color=main_color,
                fill_color_start=main_color,
                fill_color_end=main_color,
                point_color=main_color,
                point_border_color="#FFFFFF"
            )

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

        self.graph = SimpleGraph(self)
        layout.addWidget(self.graph)

        self.favorite_word_label = QLabel("Самое популярное слово: -", self)
        self.favorite_word_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.favorite_word_label)

        self.favorite_word_week_label = QLabel("Слово недели: -", self)
        self.favorite_word_week_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.favorite_word_week_label)

        layout.addStretch()

    def load_data(self):
        """Загружает данные из CSV-файла с автоматическим обновлением структуры"""
        self.data = []
        
        expected_columns = {
            'date': '',
            'score': 0,
            'total_score': 0,
            'word': None,
            'word_total_score': 0
        }
        
        try:
            if not os.path.exists(censor_file):
                debuglog.warning("Файл censor_counter.csv не найден, создаем новый")
                self._ensure_correct_structure(expected_columns)
                self.update_labels()
                return
            
            self._ensure_correct_structure(expected_columns)
            
            with open(censor_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    try:
                        parsed_row = {
                            'date': self.parse_date(row.get('date', '')),
                            'score': int(row.get('score', 0) or 0),
                            'total_score': int(row.get('total_score', 0) or 0),
                            'word': str(row.get('word', '') or None),
                            'word_total_score': int(row.get('word_total_score', 0) or 0)
                        }
                        self.data.append(parsed_row)
                    except (ValueError, TypeError) as e:
                        debuglog.warning(f"Пропущена некорректная строка: {row}, ошибка: {e}")
                        continue
                
            debuglog.debug(f"Загружено {len(self.data)} записей из CSV")
            self.calculate_scores()
            self.update_graph()
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            debuglog.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            self.update_labels()

    def _ensure_correct_structure(self, expected_columns):
        """
        Проверяет и обновляет структуру CSV файла
        Добавляет недостающие колонки с дефолтными значениями
        """
        try:
            if not os.path.exists(censor_file):
                os.makedirs(os.path.dirname(censor_file), exist_ok=True)
                with open(censor_file, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(expected_columns.keys())
                debuglog.info(f"Создан новый CSV файл")
                return

            with open(censor_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                current_headers = reader.fieldnames or []
                rows = list(reader)

            missing_columns = set(expected_columns.keys()) - set(current_headers)
            
            if not missing_columns:
                return
            
            debuglog.warning(f"Добавляем недостающие колонки: {missing_columns}")
            
            new_headers = list(current_headers) + list(missing_columns)

            updated_rows = []
            for row in rows:
                new_row = {}
                for header in current_headers:
                    new_row[header] = row.get(header, '')
                for col in missing_columns:
                    default_value = expected_columns[col]
                    new_row[col] = '' if default_value is None else str(default_value)
                updated_rows.append(new_row)
            
            with open(censor_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=new_headers)
                writer.writeheader()
                writer.writerows(updated_rows)
            
            debuglog.info(f"Структура CSV обновлена. Добавлены колонки: {missing_columns}")
            
        except Exception as e:
            debuglog.error(f"Ошибка обновления структуры CSV: {e}")

    def update_graph(self):
        """Обновляет график данными за неделю"""
        today = datetime.now().date()
        labels = []
        values = []
        days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            weekday = day.weekday()
            labels.append(days_ru[weekday])

            day_total = 0
            # Если данных нет - day_total так и останется 0
            if self.data:
                for row in self.data:
                    if row['date'] and row['date'] == day:
                        day_total += row['score']
            values.append(day_total)

        self.graph.set_data(labels, values)

    def update_stats(self):
        self.update_graph()
        self.calculate_scores()
        self.calculate_favorite_word()

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
            debuglog.warning(f"Не удалось распарсить дату: {date_str}")
            return None
        except Exception as e:
            debuglog.warning(f"Ошибка парсинга даты {date_str}: {e}")
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
            debuglog.error(f"Ошибка в calculate_scores: {e}", exc_info=True)
            self.update_labels(0, 0, 0, 0)

    def update_labels(self, day=0, week=0, month=0, total=0):
        """Обновляет метки с заданными значениями"""
        self.day_label.setText(f"За день: {day}")
        self.week_label.setText(f"За последние 7 дней: {week}")
        self.month_label.setText(f"За последние 30 дней: {month}")
        self.total_label.setText(f"Всего: {total}")

    def reset_censor_counter(self):
        """Сбрасывает счетчик, обнуляя таблицу censor_counter.csv"""
        result = self.main.show_message(
            text="Точно сбросить значения?",
            title="Сброс счетчика",
            message_type="warning",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result != QMessageBox.StandardButton.Yes:
            logger.info("Сброс счетчика отменен.")
            debuglog.info("Сброс счетчика отменен.")
            return
                
        os.makedirs(os.path.dirname(censor_file), exist_ok=True)
        
        with open(censor_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['date', 'score', 'total_score'])
        
        self.data = []
        
        self.update_labels(0, 0, 0, 0)
        self.update_stats()
        
        logger.info("Счетчик успешно сброшен.")
        debuglog.info("Счетчик успешно сброшен.")

    def calculate_favorite_word(self):
        """Вычисляет самое популярное слово за все время и за неделю"""
        # Фильтруем данные сразу, убирая None и пустые
        valid_data = [
            row for row in self.data 
            if row.get('word') and row['word'] not in ['unknown', 'None', '']
        ]
        
        if not valid_data:
            self.favorite_word_label.setText("Самое популярное слово: -")
            self.favorite_word_week_label.setText("Слово недели: -")
            return
        
        today = date.today()
        word_stats = defaultdict(int)      # За все время
        word_stats_week = defaultdict(int)  # За неделю
        
        for row in valid_data:
            word = row['word']
            row_date = row['date']
            if not row_date:
                continue
            
            # За все время
            word_stats[word] += row['word_total_score']
            
            # За неделю
            days_diff = (today - row_date).days
            if 0 <= days_diff <= 6:
                word_stats_week[word] += row['score']
        
        # Самое популярное слово за все время
        if word_stats:
            favorite_word = max(word_stats, key=word_stats.get)
            self.favorite_word_label.setText(
                f"Самое популярное слово: '{favorite_word}' ({word_stats[favorite_word]})"
            )
        else:
            self.favorite_word_label.setText("Самое популярное слово: -")
        
        # Слово недели
        if word_stats_week:
            week_word = max(word_stats_week, key=word_stats_week.get)
            self.favorite_word_week_label.setText(
                f"Слово недели: '{week_word}' ({word_stats_week[week_word]})"
            )
        else:
            self.favorite_word_week_label.setText("Слово недели: -")

    def censor_counter(self, detected_word=None):
        """Добавляет запись о матерном слове в счетчик"""
        os.makedirs(os.path.dirname(censor_file), exist_ok=True)
        
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        headers = ['date', 'score', 'total_score', 'word', 'word_total_score']
        data = []
        file_exists = os.path.exists(censor_file)
        
        if file_exists:
            try:
                with open(censor_file, mode='r', encoding='utf-8', newline='') as file:
                    reader = csv.DictReader(file)
                    
                    if not reader.fieldnames or 'word' not in reader.fieldnames:
                        debuglog.warning(f"[MAIN] Обновление структуры CSV файла {censor_file}")
                        file_exists = False
                    else:
                        for row in reader:
                            try:
                                row_date = row['date'].strip()
                                score = int(row.get('score', 0) or 0)
                                total_score = int(row.get('total_score', 0) or 0)
                                word = row.get('word', '').strip()
                                word_total_score = int(row.get('word_total_score', 0) or 0)
                                
                                data.append({
                                    'date': row_date,
                                    'score': score,
                                    'total_score': total_score,
                                    'word': word,
                                    'word_total_score': word_total_score
                                })
                            except (ValueError, KeyError) as e:
                                debuglog.warning(f"[MAIN] Пропущена некорректная строка: {row}, ошибка: {e}")
                                continue
            except Exception as e:
                logger.error(f"[MAIN] Ошибка чтения файла {censor_file}: {e}")
                debuglog.error(f"[MAIN] Ошибка чтения файла {censor_file}: {e}")
                file_exists = False
        
        if not file_exists:
            data = []
            with open(censor_file, mode='w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()

        if not detected_word:
            detected_word = "unknown"

        detected_word = detected_word.lower().strip()

        if data:
            current_total = max(r['total_score'] for r in data)
        else:
            current_total = 0

        new_total = current_total + 1

        found = False
        for record in data:
            if record['date'] == today_str and record['word'] == detected_word:
                record['score'] += 1
                record['total_score'] = new_total
                record['word_total_score'] += 1
                found = True
                break
        
        if not found:
            data.append({
                'date': today_str,
                'score': 1,
                'total_score': new_total,
                'word': detected_word,
                'word_total_score': 1
            })

        for record in data:
            if record['date'] == today_str:
                record['total_score'] = new_total

        try:
            with open(censor_file, mode='w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            debuglog.debug(f"[MAIN] Счетчик обновлен. Слово: {detected_word}, Всего: {new_total}")

            self.data = []
            for row in data:
                parsed_row = {
                    'date': self.parse_date(row['date']),
                    'score': row['score'],
                    'total_score': row['total_score'],
                    'word': row['word'],
                    'word_total_score': row['word_total_score']
                }
                self.data.append(parsed_row)

            self.update_stats()
            
        except Exception as e:
            logger.error(f"[MAIN] Ошибка записи в файл {censor_file}: {e}")
            debuglog.error(f"[MAIN] Ошибка записи в файл {censor_file}: {e}")


class CheckUpdateWidget(QWidget):
    """
    Виджет для ручной проверки обновлений, выбора определенной версии из списка доступных
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self._help_initialized = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPageWidget")
        self.init_ui()
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_manager.apply_progressbar(widget=self.progress)
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        # Основной layout
        layout = QVBoxLayout(self)

        self.title = setup_custom_font_label("Центр обновлений", font_style="Comfortaa", weight="Medium")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.check_button = QPushButton("Проверить обновления")
        self.check_button.clicked.connect(self.main.check_update_app)
        self.check_button.setProperty("helpId", "check_button_update")
        layout.addWidget(self.check_button)

        self.update_check = QCheckBox("Проверить свежие бета-версии", self)
        self.update_check.setStyleSheet("background: transparent;")
        self.update_check.setChecked(self.main.beta_version)
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
        self.main.beta_version = state == Qt.CheckState.Checked

    def wait_and_rollback(self):
        # Показываем диалог и получаем результат
        result = self.main.show_message(
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
                lambda: self.main.update_app(type_version="stable"))
            self.download_thread.finished.connect(self.finish_load)
            self.download_thread.start()
        except Exception as e:
            self.progress.hide()
            self.progress.stopAnimation()
            self.rollback.show()
            self.main.show_toast(f"Ошибка: {e}")
            debuglog.error(f"Ошибка в методе rollback_stable_version: {e}")

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
            debuglog = DebuglogWindow(log_path=self.main.debuglog_file_path, parent=self)
            debuglog.show()
        except Exception as e:
            logger.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")
            debuglog.error(f"Ошибка при открытии/закрытии окна дебаг-файла: {e}")


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
        self.parent_window.main.style_manager.apply_color_svg(self.close_svg, strength=0.90,
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
        close_btn.setObjectName("TitleBarCloseBtn")
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
        
        try:
            if not os.path.exists(self.debug_log_path):
                logger.info("Файл логов не найден. Создаем новый.")
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
            logger.error(f"Ошибка при чтении файла логов: {e}")
            self.log_area.append(f"Ошибка при чтении файла логов: {e}")
