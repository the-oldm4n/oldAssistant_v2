from collections import defaultdict
import csv
from datetime import date, datetime, timedelta
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox
from bin.graph_widget import SimpleGraph
from bin.signals import censor_signal
from bin.utils import setup_custom_font_label
from mygui import color_signal
from log_config import logger, assist_log


class CensorCounterWidget(QWidget):
    """
    Виджет счетчика матерных слов
    """
    def __init__(self, main_window=None, censor_file=None, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        censor_signal.update_count.connect(self.censor_counter)
        self.main = main_window
        self.censor_file = censor_file
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
        logger.info("Refresh data in censor counter")
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
            if not os.path.exists(self.censor_file):
                logger.warning("Файл censor_counter.csv не найден, создаем новый")
                self._ensure_correct_structure(expected_columns)
                self.update_labels()
                return
            
            self._ensure_correct_structure(expected_columns)
            
            with open(self.censor_file, 'r', encoding='utf-8') as file:
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
                        logger.warning(f"Пропущена некорректная строка: {row}, ошибка: {e}")
                        continue
                
            logger.debug(f"Загружено {len(self.data)} записей из CSV")
            self.calculate_scores()
            self.update_graph()
            
        except Exception as e:
            assist_log.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            self.update_labels()

    def _ensure_correct_structure(self, expected_columns):
        """
        Проверяет и обновляет структуру CSV файла
        Добавляет недостающие колонки с дефолтными значениями
        """
        try:
            if not os.path.exists(self.censor_file):
                os.makedirs(os.path.dirname(self.censor_file), exist_ok=True)
                with open(self.censor_file, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(expected_columns.keys())
                logger.info(f"Создан новый CSV файл")
                return

            with open(self.censor_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                current_headers = reader.fieldnames or []
                rows = list(reader)

            missing_columns = set(expected_columns.keys()) - set(current_headers)
            
            if not missing_columns:
                return
            
            logger.warning(f"Добавляем недостающие колонки: {missing_columns}")
            
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
            
            with open(self.censor_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=new_headers)
                writer.writeheader()
                writer.writerows(updated_rows)
            
            logger.info(f"Структура CSV обновлена. Добавлены колонки: {missing_columns}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления структуры CSV: {e}")

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
            logger.warning(f"Не удалось распарсить дату: {date_str}")
            return None
        except Exception as e:
            logger.warning(f"Ошибка парсинга даты {date_str}: {e}")
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
            assist_log.error(f"Ошибка в calculate_scores: {e}", exc_info=True)
            logger.error(f"Ошибка в calculate_scores: {e}", exc_info=True)
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
            assist_log.info("Сброс счетчика отменен.")
            logger.info("Сброс счетчика отменен.")
            return
                
        os.makedirs(os.path.dirname(self.censor_file), exist_ok=True)
        
        with open(self.censor_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['date', 'score', 'total_score'])
        
        self.data = []
        
        self.update_labels(0, 0, 0, 0)
        self.update_stats()
        
        assist_log.info("Счетчик успешно сброшен.")
        logger.info("Счетчик успешно сброшен.")

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
        os.makedirs(os.path.dirname(self.censor_file), exist_ok=True)
        
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        headers = ['date', 'score', 'total_score', 'word', 'word_total_score']
        data = []
        file_exists = os.path.exists(self.censor_file)
        
        if file_exists:
            try:
                with open(self.censor_file, mode='r', encoding='utf-8', newline='') as file:
                    reader = csv.DictReader(file)
                    
                    if not reader.fieldnames or 'word' not in reader.fieldnames:
                        logger.warning(f"[MAIN] Обновление структуры CSV файла {self.censor_file}")
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
                                logger.warning(f"[MAIN] Пропущена некорректная строка: {row}, ошибка: {e}")
                                continue
            except Exception as e:
                assist_log.error(f"[MAIN] Ошибка чтения файла {self.censor_file}: {e}")
                logger.error(f"[MAIN] Ошибка чтения файла {self.censor_file}: {e}")
                file_exists = False
        
        if not file_exists:
            data = []
            with open(self.censor_file, mode='w', encoding='utf-8', newline='') as file:
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
            with open(self.censor_file, mode='w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            logger.debug(f"[MAIN] Счетчик обновлен. Слово: {detected_word}, Всего: {new_total}")

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
            assist_log.error(f"[MAIN] Ошибка записи в файл {self.censor_file}: {e}")
            logger.error(f"[MAIN] Ошибка записи в файл {self.censor_file}: {e}")