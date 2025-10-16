import json
import os
import re
import shutil
import subprocess
import time
import zipfile
import psutil
from PySide6.QtCore import QThread, Signal, QTimer, Property, QPropertyAnimation
from PySide6.QtGui import QIcon, QColor, Qt, QPen, QColor, QRadialGradient, QLinearGradient, QBrush, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, \
                               QPushButton, QLabel, QSizePolicy,
                               QGraphicsColorizeEffect, QSpacerItem, QProgressBar)
import sys
from packaging import version
from check_and_download import DownloadThread, VersionCheckThread
from utils import get_path, logger, get_base_directory, update_signal, run_app_signal, get_config_value


class CustomProgressBar(QWidget):
    def __init__(self, parent=None, style="default", circle_size=100, line_width=2):
        super().__init__(parent)
        self.style = style
        self.circle_size = circle_size
        self.value = 0
        self.max_value = 100
        self.line_width = line_width
        
        # Цвета для кругового прогрессбара
        self.progress_color = QColor("#05B8CC")          # Цвет самой полосы прогресса
        self.track_color = QColor(40, 40, 40, 150)       # Цвет под полосой прогресса (фон кольца)
        self.background_color = QColor(30, 30, 30, 100)  # Цвет внутренней области
        self.text_color = QColor(255, 255, 255)          # Цвет текста
        
        # Инициализация в зависимости от стиля
        if self.style == "circle":
            self.setup_circular_progressbar()
        else:
            self.setup_linear_progressbar()
            
        # Общая анимация
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(2000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(100)
        self.animation.setLoopCount(-1)

    def setup_linear_progressbar(self):
        """Настройка линейного QProgressBar (default и looper)"""
        self.linear_progress = QProgressBar(self)
        self.linear_progress.setRange(0, 100)
        self.linear_progress.setValue(0)
        self.linear_progress.setTextVisible(False)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.linear_progress)

    def setup_circular_progressbar(self):
        """Настройка кругового прогрессбара"""
        self.setFixedSize(self.circle_size, self.circle_size)

    def setValue(self, value):
        """Установка значения прогресса"""
        self.value = max(0, min(value, self.max_value))
        if self.style != "circle" and hasattr(self, 'linear_progress'):
            self.linear_progress.setValue(self.value)
        self.update()
        
    def setLineWidth(self, width):
        """Устанавливает толщину линии прогресса"""
        self.line_width = width
        self.update()

    def setProgressColor(self, color):
        """Устанавливает цвет самой полосы прогресса"""
        if isinstance(color, str):
            self.progress_color = QColor(color)
        else:
            self.progress_color = color
        self.update()

    def setTrackColor(self, color):
        """Устанавливает цвет под полосой прогресса (фон кольца)"""
        if isinstance(color, str):
            self.track_color = QColor(color)
        else:
            self.track_color = color
        self.update()

    def setBackgroundColor(self, color):
        """Устанавливает цвет внутренней области"""
        if isinstance(color, str):
            self.background_color = QColor(color)
        else:
            self.background_color = color
        self.update()

    def setTextColor(self, color):
        """Устанавливает цвет текста"""
        if isinstance(color, str):
            self.text_color = QColor(color)
        else:
            self.text_color = color
        self.update()

    def setCircleSize(self, size):
        """Изменение размера кругового прогрессбара"""
        if self.style == "circle":
            self.circle_size = size
            self.setFixedSize(size, size)
            self.update()

    def apply_linear_style(self):
        """Применение стиля к линейному прогрессбару"""
        color = self.progress_color.name()
        darker = self.progress_color.darker(120).name()
        
        if self.style == "default":
            style = f"""
                QProgressBar {{
                    border: 1px solid {darker};
                    border-radius: 5px;
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {darker},
                        stop:1 {color}
                    );
                }}
            """
        else:  # looper
            style = f"""
                QProgressBar {{
                    border: 1px solid {darker};
                    border-radius: 5px;
                    background: {self.progress_color.darker(150).name()};
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {darker},
                        stop:1 {color}
                    );
                    border-radius: 2px;
                    width: 20px;
                    margin: 1px;
                }}
            """
        
        self.linear_progress.setStyleSheet(style)

    def startAnimation(self):
        """Запуск анимации"""
        if self.style == "looper" or self.style == "circle":
            self.animation.start()

    def stopAnimation(self):
        """Остановка анимации"""
        self.animation.stop()
        if self.style == "looper" or self.style == "circle":
            self.setValue(0)

    def paintEvent(self, event):
        """Отрисовка кругового прогрессбара"""
        if self.style != "circle":
            return super().paintEvent(event)
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        try:
            diameter = min(self.width(), self.height()) - 20
            x = (self.width() - diameter) // 2
            y = (self.height() - diameter) // 2
            
            # 1. Внутренняя область (центр)
            painter.setBrush(self.background_color)
            painter.setPen(Qt.NoPen)
            # Делаем внутренний круг немного меньше, чтобы был отступ от линии прогресса
            inner_margin = self.line_width + 4
            inner_diameter = diameter - inner_margin * 2
            inner_x = (self.width() - inner_diameter) // 2
            inner_y = (self.height() - inner_diameter) // 2
            painter.drawEllipse(inner_x, inner_y, inner_diameter, inner_diameter)
            
            # 2. Фон под полосой прогресса (фоновое кольцо)
            pen = QPen(self.track_color)
            pen.setWidth(self.line_width)
            painter.setPen(pen)
            painter.drawArc(x, y, diameter, diameter, 0, 360 * 16)
            
            # 3. Сама полоса прогресса
            if self.value > 0:
                progress_ratio = self.value / self.max_value
                half_angle = int(progress_ratio * 180 * 16)
                
                # Левая половинка
                self.draw_progress_arc(painter, x, y, diameter, 270 * 16, -half_angle)
                # Правая половинка
                self.draw_progress_arc(painter, x, y, diameter, 270 * 16, half_angle)
            
            # 4. Текст
            if self.circle_size >= 80:
                painter.setPen(self.text_color)
                font = painter.font()
                font.setPointSize(max(8, self.circle_size // 15))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(self.rect(), Qt.AlignCenter, f"{self.value}%")
            
        finally:
            painter.end()

    def draw_progress_arc(self, painter, x, y, diameter, start_angle, span_angle):
        """Отрисовка дуги прогресса"""
        if span_angle == 0:
            return
            
        # Градиент для полосы прогресса
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, self.progress_color.lighter(150))
        gradient.setColorAt(1, self.progress_color)
        
        pen = QPen(QBrush(gradient), self.line_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(x, y, diameter, diameter, start_angle, span_angle)
        
    def setProgressGradient(self, gradient):
        """Устанавливает градиент для полосы прогресса"""
        self.progress_gradient = gradient
        self.update()
    
    def draw_progress_arc(self, painter, x, y, diameter, start_angle, span_angle):
        """Отрисовка дуги прогресса"""
        if span_angle == 0:
            return
            
        # Используем градиент если он установлен, иначе создаем из цвета
        if hasattr(self, 'progress_gradient') and self.progress_gradient:
            brush = QBrush(self.progress_gradient)
        else:
            # Создаем градиент из цвета
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, self.progress_color.lighter(150))
            gradient.setColorAt(1, self.progress_color)
            brush = QBrush(gradient)
        
        pen = QPen(brush, self.line_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(x, y, diameter, diameter, start_angle, span_angle)
        
        
class SVGProgressBar(CustomProgressBar):
    def __init__(self, parent=None, style="default", circle_size=200, svg_widget=None, show_text=True, line_width=2):
        # Передаем line_width в родительский конструктор
        super().__init__(parent, style, circle_size, line_width)
        self.svg_widget = svg_widget
        self.show_text = show_text  # Флаг для отображения текста
        
        if self.svg_widget and style == "circle":
            self.setup_svg_widget()
            
    def setProgressGradient(self, gradient):
        """Устанавливает градиент для полосы прогресса"""
        self.progress_gradient = gradient
        self.update()
    
    def setup_svg_widget(self):
        """Настройка SVG виджета внутри прогрессбара"""
        self.svg_widget.setParent(self)
        self.svg_widget.setFixedSize(self.circle_size // 2, self.circle_size // 2)
        
        # Центрируем SVG внутри прогрессбара
        self.svg_widget.move(
            (self.width() - self.svg_widget.width()) // 2,
            (self.height() - self.svg_widget.height()) // 2
        )
        self.svg_widget.raise_()
        self.svg_widget.show()
    
    def setShowText(self, show):
        """Включает/отключает отображение текста прогресса"""
        self.show_text = show
        self.update()
    
    def setCircleSize(self, size):
        """Переопределяем для обновления SVG"""
        super().setCircleSize(size)
        if self.svg_widget and self.style == "circle":
            self.svg_widget.setFixedSize(size // 2, size // 2)
            self.svg_widget.move(
                (self.width() - self.svg_widget.width()) // 2,
                (self.height() - self.svg_widget.height()) // 2
            )
    
    def resizeEvent(self, event):
        """Обработка изменения размера"""
        super().resizeEvent(event)
        if self.svg_widget and self.style == "circle":
            self.svg_widget.move(
                (self.width() - self.svg_widget.width()) // 2,
                (self.height() - self.svg_widget.height()) // 2
            )
    
    def setSvgWidget(self, svg_widget):
        """Устанавливает SVG виджет динамически"""
        if self.svg_widget:
            self.svg_widget.deleteLater()
            
        self.svg_widget = svg_widget
        if self.svg_widget and self.style == "circle":
            self.setup_svg_widget()
    
    def paintEvent(self, event):
        """Отрисовка кругового прогрессбара с учетом флага show_text"""
        if self.style != "circle":
            return super().paintEvent(event)
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        try:
            diameter = min(self.width(), self.height()) - 20
            x = (self.width() - diameter) // 2
            y = (self.height() - diameter) // 2
            
            # 1. Внутренняя область (центр)
            painter.setBrush(self.background_color)
            painter.setPen(Qt.NoPen)
            inner_margin = self.line_width + 4  # Используем self.line_width от родителя
            inner_diameter = diameter - inner_margin * 2
            inner_x = (self.width() - inner_diameter) // 2
            inner_y = (self.height() - inner_diameter) // 2
            painter.drawEllipse(inner_x, inner_y, inner_diameter, inner_diameter)
            
            # 2. Фон под полосой прогресса (фоновое кольцо)
            pen = QPen(self.track_color)
            pen.setWidth(self.line_width)  # Используем self.line_width от родителя
            painter.setPen(pen)
            painter.drawArc(x, y, diameter, diameter, 0, 360 * 16)
            
            # 3. Сама полоса прогресса
            if self.value > 0:
                progress_ratio = self.value / self.max_value
                half_angle = int(progress_ratio * 180 * 16)
                
                # Левая половинка
                self.draw_progress_arc(painter, x, y, diameter, 270 * 16, -half_angle)
                # Правая половинка
                self.draw_progress_arc(painter, x, y, diameter, 270 * 16, half_angle)
            
            # 4. Текст (только если включен и размер достаточный)
            if self.show_text and self.circle_size >= 80:
                painter.setPen(self.text_color)
                font = painter.font()
                font.setPointSize(max(8, self.circle_size // 15))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(self.rect(), Qt.AlignCenter, f"{self.value}%")
            
        finally:
            painter.end()

class CustomSvgWidget(QSvgWidget):
    """
    Кастомный SVG виджет для встраивания в кнопки
    Автоматически синхронизируется с родительской кнопкой
    """

    def __init__(self, svg_path, parent_button=None):
        """
        :param svg_path: путь к SVG файлу
        :param parent_button: родительская кнопка (QPushButton)
        """
        super().__init__(parent_button)  # Передаем кнопку как родителя
        self._parent_button = parent_button
        self._color_effect = None
        self._current_color = QColor("#000000")
        self._current_strength = 1.0

        # Загружаем SVG
        if svg_path:
            self.load(svg_path)

        # Настройки для встраивания в кнопку
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def applyColorEffect(self, color, strength=1.0):
        """
        Применяет цветовой эффект
        """
        try:
            self._current_color = color
            self._current_strength = strength

            # Удаляем старый эффект
            if self._color_effect:
                self._color_effect.deleteLater()

            # Создаем и применяем эффект
            self._color_effect = QGraphicsColorizeEffect(self)
            self._color_effect.setColor(color)
            self._color_effect.setStrength(strength)
            self.setGraphicsEffect(self._color_effect)

            self._forceUpdate()
            return True

        except Exception as e:
            print(f"❌ Ошибка применения цвета: {e}")
            return False

    def _forceUpdate(self):
        """Принудительное обновление"""
        self.update()
        self.repaint()
        if self._parent_button:
            self._parent_button.update()

    # Свойства
    def getEffectColor(self):
        return self._current_color

    def setEffectColor(self, color):
        self.applyColorEffect(color, self._current_strength)

    effectColor = Property(QColor, getEffectColor, setEffectColor)


class UnpackAppThread(QThread):
    """
    Класс, отвечающий за распаковку архива обновления, испускает сигнал по окончании распаковки.
    """
    unpack_complete = Signal(bool)

    def __init__(self):
        super().__init__()

        self.root_dir = get_base_directory()  # Корень (Assistant/)
        self.update_pack_dir = self.root_dir / "update_pack"
        self.update_pack_dir.mkdir(parents=True, exist_ok=True)
        self.update_file_path = self.find_update_file()

    def run(self):
        if not self.update_file_path:
            logger.error("Не найден файл обновления (*.zip)")
            update_signal.status_update.emit("Не найден файл обновления (*.zip)")
            self.unpack_complete.emit(False)
            return

        if self.is_already_unpacked():
            logger.info("Архив уже распакован")
            update_signal.status_update.emit("Архив распакован", 70)
            self.unpack_complete.emit(True)
            return

        if not self.extract_archive(self.update_file_path):
            update_signal.status_update.emit("Не удалось распаковать архив с новой версией")
            self.unpack_complete.emit(False)
            return
        logger.info(f"Архив с новой версией распакован по пути {self.update_pack_dir}")
        self.unpack_complete.emit(True)

    def is_already_unpacked(self):
        """Проверяет, распакован ли уже архив"""
        try:
            # Проверяем существование папки и наличие файлов
            if not os.path.exists(self.update_pack_dir):
                return False

            # Проверяем, есть ли содержимое (игнорируем скрытые файлы)
            visible_files = [f for f in os.listdir(self.update_pack_dir)
                             if not f.startswith('.') and f not in ['log', 'user_settings']]

            if not visible_files:
                return False

            # Проверяем ключевые файлы/папки которые должны быть после распаковки
            required_items = ['Assistant.exe', '_internal']
            for item in required_items:
                item_path = os.path.join(self.update_pack_dir, item)
                if not os.path.exists(item_path):
                    return False

            logger.info("Обновление уже распаковано")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки распаковки: {e}")
            return False

    def find_update_file(self):
        root_dir = get_base_directory()
        update_dir = root_dir / "update"
        pattern = f"stable_Assistant_*.zip"
        # Ищем самый свежий файл по дате изменения
        files = []
        for file in os.listdir(update_dir):
            if file.lower().startswith("stable") and file.lower().endswith('.zip'):
                file_path = os.path.join(update_dir, file)
                files.append((file_path, os.path.getmtime(file_path)))

        if files:
            # Сортируем по дате изменения (новые сначала)
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
        return None

    def extract_archive(self, archive_path):
        """Безопасная распаковка архива с обработкой кодировок"""
        try:
            # Очищаем папку перед распаковкой
            for item in os.listdir(self.update_pack_dir):
                item_path = os.path.join(self.update_pack_dir, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                else:
                    shutil.rmtree(item_path)

            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Безопасное извлечение имени файла
                    file_name = self._safe_decode_filename(file_info.filename)

                    # Защита от Zip Slip
                    target_path = os.path.join(self.update_pack_dir, file_name)
                    if not os.path.abspath(target_path).startswith(os.path.abspath(self.update_pack_dir)):
                        raise ValueError(f"Попытка распаковки вне целевой папки: {file_name}")

                    # Создаем папки если нужно
                    if file_name.endswith('/'):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as f:
                            f.write(zip_ref.read(file_info))
            return True

        except Exception as e:
            logger.error(f"Ошибка распаковки: {str(e)}", exc_info=True)
            update_signal.status_update.emit(f"Ошибка распаковки: {str(e)}")
            return False

    def _safe_decode_filename(self, filename):
        """Безопасное декодирование имени файла из архива с поддержкой русского"""
        # Список кодировок для попытки декодирования (в порядке приоритета)
        encodings = [
            'cp866',  # DOS/Windows Russian
            'cp1251',  # Windows Cyrillic
            'utf-8',  # Unicode
            'cp437',  # DOS English
            'iso-8859-1',  # Latin-1
            'koi8-r'  # Russian KOI8-R
        ]

        # Сначала пробуем стандартное декодирование (для современных ZIP)
        try:
            return filename.encode('cp437').decode('utf-8')
        except UnicodeError:
            pass

        # Если не получилось, пробуем все кодировки по очереди
        for enc in encodings:
            try:
                return filename.encode('cp437').decode(enc)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

        # Если ничего не помогло, возвращаем как есть и логируем проблему
        logger.warning(f"Не удалось декодировать имя файла: {filename}")
        return filename


class UpdateWindow(QWidget):
    """
    Главное окно обновления.
    Содержит логику предварительной проверки обновлений, скачивание, установку и запуск основного приложения.
    """

    def __init__(self):
        super().__init__()
        self.check_thread = None
        self.download_thread = None
        self.unpack_thread = None
        self.root_dir = get_base_directory()
        self.update_pack_dir = self.root_dir / "update_pack"
        self.no_check_mode = "--no-checked" in sys.argv
        self.install_mode = "--install-mode" in sys.argv
        run_app_signal.run_main_app.connect(self.run_main_app)
        self.setWindowIcon(QIcon(get_path('icon.ico')))
        self.parent_style = self.root_dir / "user_settings" / "color_settings.json"
        self.style_path = get_path('color.json')
        if self.parent_style.exists():
            style = self.parent_style
        else:
            style = self.style_path
        self.svg_path = get_path("logo.svg")
        self.version = get_config_value("app", "version")
        self.style_manager = ApplyColor(style)
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()
        self.start_update_process()

    def init_ui(self):
        try:
            
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(250, 250)

            screen_geometry = QApplication.primaryScreen().availableGeometry()
            self.move(
                (screen_geometry.width() - self.width()) // 2,
                (screen_geometry.height() - self.height()) // 2
            )
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)

            self.main_widget = QWidget()
            self.main_widget.setStyleSheet("""border-radius:20px""")
            content_layout = QVBoxLayout(self.main_widget)
            content_layout.setContentsMargins(15, 0, 15, 10)
            content_layout.addStretch()

            self.svg_image = CustomSvgWidget(self.svg_path)
            self.svg_image.setFixedSize(120, 110)
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
            # self.progress = QProgressBar()
            self.progress.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

            self.label = QLabel("Завершение программы...")
            self.label.setStyleSheet("background: transparent; min-height: 35px; max-height: 35px; font-size:14px")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setWordWrap(True)
            self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            content_layout.addWidget(self.label)

            self.button_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            # content_layout.addItem(self.button_spacer)

            # Кнопка выхода
            self.error_button = QPushButton("Закрыть")
            self.error_button.clicked.connect(self.quit_application)
            self.error_button.setStyleSheet("""width:100px; border-radius:5px""")
            self.error_button.hide()
            content_layout.addWidget(self.error_button, alignment=Qt.AlignmentFlag.AlignCenter)

            self.setLayout(layout)
            layout.addWidget(self.main_widget, 1)
        except Exception as e:
            print(f"Ошибка {e}")

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            # Применение к SVG
            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_progressbar(key="QPushButton", widget=self.progress)

            # Применение общего стиля окна
            if hasattr(self, 'central_widget'):
                self.central_widget.setObjectName("CentralWidget")
            if hasattr(self, 'title_bar_widget'):
                self.title_bar_widget.setObjectName("TitleBar")
            # Применяем стили к текущему окну
            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):  # Для стандартных виджетов (например, QMainWindow, QPushButton)
                    selector = widget
                else:  # Для виджетов с objectName (например, TitleBar, CentralWidget)
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            self.setStyleSheet(style_sheet)

        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def start_update_process(self):
        if self.check_thread is not None:
            return

        self.label.setText("Проверка...")

        # 1. Сначала закрываем основную программу
        if self.is_main_app_running():
            self.set_status("Закрытие Assistant.exe...", 0)
            self.kill_main_app()
            time.sleep(2)  # Даем время на закрытие

        # 2. Проверяем режим no-check
        if self.no_check_mode:
            self.set_status("Пропуск проверки обновлений...", 30)
            QTimer.singleShot(1000, self.start_install_from_existing)  # Прямо к установке
        else:
            # 3. Запускаем обычную цепочку из UI потока
            self.start_check_update()

    def start_check_update(self):
        """Запуск проверки обновлений из UI потока"""
        self.set_status("Поиск обновлений...", 10)

        self.check_thread = VersionCheckThread()
        self.check_thread.version_checked.connect(self.on_version_checked)
        self.check_thread.check_failed.connect(self.on_check_failed)
        self.check_thread.start()

    def on_version_checked(self, stable_version, exp_version):
        """Обработка результата проверки в UI потоке"""
        if hasattr(self, 'check_attempts'):
            delattr(self, 'check_attempts')
        try:
            # Получаем текущую версию с обработкой ошибок
            current_version_str = get_config_value("app", "version")
            if not current_version_str:
                logger.warning("Не удалось получить текущую версию из конфига, используем '0.0.0'")
                current_version_str = "0.0.0"

            current_version = version.parse(current_version_str)

            # Проверяем stable_version на None
            if stable_version is None:
                logger.error("Не удалось получить стабильную версию с сервера")
                self.retry_version_check()
                return

            stable_ver = version.parse(stable_version)

            if stable_ver > current_version:
                self.set_status("Скачивание обновления...", 30)
                self.start_download(stable_version)
            else:
                self.set_status("Установлена последняя версия", 100)
                QTimer.singleShot(200, self.run_main_app)

        except Exception as e:
            logger.error(f"Ошибка при обработке версий: {e}")
            # В случае любой ошибки пытаемся скачать обновление
            if stable_version:
                self.set_status("Скачивание обновления...", 30)
                self.start_download(stable_version)
            else:
                self.retry_version_check()

    def retry_version_check(self, attempt=1, max_attempts=3):
        """Повторная попытка проверки версии"""
        if attempt > max_attempts:
            self.set_status("Не удалось получить версию с сервера", 0)
            self.show_error("Ошибка получения версии")
            # Запускаем основную программу через некоторое время
            QTimer.singleShot(3000, self.run_main_app)
            return

        self.set_status(f"Повторная проверка ({attempt}/{max_attempts})...", 20)
        logger.info(f"Повторная попытка проверки версии: {attempt}/{max_attempts}")

        QTimer.singleShot(2000, lambda: self.start_check_update())

    def on_check_failed(self):
        """Обработка ошибки проверки"""
        # Используем атрибут для отслеживания попыток
        if not hasattr(self, 'check_attempts'):
            self.check_attempts = 1
        else:
            self.check_attempts += 1

        if self.check_attempts <= 3:
            self.set_status(f"Ошибка проверки ({self.check_attempts}/3)", 0)
            QTimer.singleShot(1500, self.start_check_update)
        else:
            self.set_status("Не удалось проверить обновления", 0)
            # Запускаем основную программу
            QTimer.singleShot(2000, self.run_main_app)

    def start_download(self, version):
        """Запуск загрузки из UI потока"""
        self.download_thread = DownloadThread("stable", version)
        self.download_thread.download_complete.connect(self.on_download_complete)
        self.download_thread.download_progress.connect(self.on_download_progress)
        self.download_thread.start()

    def on_download_progress(self, progress_percent):
        """Обработка прогресса загрузки"""
        # Преобразуем прогресс от 0-100% к диапазону 30-60%
        mapped_progress = 30 + int(progress_percent * 0.3)  # 30% + (30% от progress_percent)
        self.progress.setValue(mapped_progress)

    def on_download_complete(self, file_path, success, skipped, error):
        """Обработка завершения загрузки"""
        if success:
            # Устанавливаем 60% при завершении скачивания
            self.progress.setValue(60)
            self.set_status("Распаковка...", 60)
            self.start_unpack()
        else:
            self.set_status(f"Ошибка загрузки: {error}", 0)
            self.show_error("Ошибка загрузки")

    def start_unpack(self):
        """Запуск распаковки из UI потока"""
        self.unpack_thread = UnpackAppThread()
        self.unpack_thread.unpack_complete.connect(self.on_unpack_complete)
        self.unpack_thread.start()

    def on_unpack_complete(self, success):
        """Обработка завершения распаковки"""
        if success:
            self.set_status("Установка...", 80)
            self.install_update()
        else:
            self.set_status("Ошибка распаковки", 0)
            self.show_error("Ошибка распаковки")

    def install_update(self):
        """Синхронная установка в UI потоке"""
        try:
            # Удаляем старые файлы
            self.set_status("Удаление старых файлов...", 85)
            self.delete_old_files()

            # Копируем новые
            self.set_status("Копирование новых файлов...", 90)
            if self.copy_new_files():
                self.set_status("Обновление завершено", 100)
                QTimer.singleShot(1000, self.run_main_app)
            else:
                self.show_error("Ошибка установки")

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            self.show_error("Ошибка установки")

    def start_install_from_existing(self):
        """Запуск установки из уже распакованного архива (режим --no-checked)"""
        self.set_status("Проверка распакованного обновления...", 60)

        # Проверяем, есть ли распакованные файлы
        unpack_thread = UnpackAppThread()
        if unpack_thread.is_already_unpacked():
            self.set_status("Начинаем установку...", 60)
            QTimer.singleShot(1000, self.install_update)
        else:
            self.set_status("Распаковка обновления...", 50)
            self.start_unpack()

    def run_main_app(self):
        """Запускает основную программу с флагом обновления и закрывает updater"""
        try:
            main_app = os.path.join(os.path.dirname(get_base_directory()), "Assistant.exe")
            if os.path.exists(main_app):
                # Запускаем с аргументом --updated
                subprocess.Popen([main_app, "--updated"])
                logger.info("Основная программа запущена после обновления")
            else:
                logger.error("Основная программа не найдена")

            # Даем время на запуск перед закрытием
            QTimer.singleShot(500, self.close)

        except Exception as e:
            logger.error(f"Ошибка запуска основной программы: {e}")
            self.close()

    def set_status(self, text, progress=None):
        self.label.setText(text)
        if progress is not None:
            self.progress.setValue(progress)

    def show_error(self, message):
        self.label.setText(message)
        self.error_button.show()
        self.button_spacer.changeSize(20, 0)

    def quit_application(self):
        sys.exit(1)

    def is_main_app_running(self):
        """Проверяет, запущена ли основная программа"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'Assistant.exe':
                return True
        return False

    def kill_main_app(self):
        """Завершает основную программу"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'Assistant.exe':
                try:
                    proc.kill()
                    proc.wait(timeout=5)  # Ждем завершения
                except:
                    pass

    def delete_old_files(self):
        preserved = ["user_settings", "update", "update_pack", "log"]

        # Удаление внутри self.root_dir (как раньше)
        for item in os.listdir(self.root_dir):
            full_path = os.path.join(self.root_dir, item)
            if os.path.isdir(full_path):
                if os.path.basename(full_path) not in preserved:
                    shutil.rmtree(full_path, ignore_errors=True)
            elif os.path.isfile(full_path):
                if os.path.basename(full_path) != "Assistant.exe":
                    try:
                        os.remove(full_path)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении старых файлов: {e}")
                        pass

        parent_dir = os.path.dirname(self.root_dir)  # Получаем родительскую папку
        assistant_exe_path = os.path.join(parent_dir, "Assistant.exe")

        if os.path.isfile(assistant_exe_path):
            try:
                os.remove(assistant_exe_path)
                logger.info(f"Удалён {assistant_exe_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления {assistant_exe_path}: {e}")

    def copy_new_files(self):
        try:
            # Путь к папке _internal внутри update_pack
            update_internal_dir = os.path.join(self.update_pack_dir, "_internal")

            # Копируем содержимое _internal из update_pack в целевую _internal, кроме user_settings
            if os.path.exists(update_internal_dir):
                for item in os.listdir(update_internal_dir):
                    # Пропускаем только в НЕ режиме установки
                    if not self.install_mode:
                        if item in ["user_settings", "Update.exe", "log"]:
                            continue

                    src = os.path.join(update_internal_dir, item)
                    dst = os.path.join(self.root_dir, item)

                    for _ in range(5):  # 5 попыток
                        try:
                            if os.path.isdir(src):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                            else:
                                if os.path.exists(dst):
                                    try:
                                        os.rename(dst, dst + ".old")
                                    except:
                                        pass
                                shutil.copy2(src, dst)
                            break
                        except Exception:
                            time.sleep(1)

            # Копируем Assistant.exe на уровень выше
            assistant_src = os.path.join(self.update_pack_dir, "Assistant.exe")
            if os.path.exists(assistant_src):
                parent_dir = os.path.dirname(self.root_dir)  # Родительская папка
                assistant_dst = os.path.join(parent_dir, "Assistant.exe")
                shutil.copy2(assistant_src, assistant_dst)

            return True
        except Exception as e:
            logger.error(f"Ошибка копирования: {e}")
            return False


class ApplyColor():
    def __init__(self, new_color=None, parent=None):
        self.parent = parent  # Сохраняем ссылку на родительское окно
        self.color_path = get_path('user_settings', 'color_settings.json')
        self.styles = self.load_styles()
        if new_color:
            self.color_path = new_color

    def load_styles(self):
        """Только загрузка стилей без применения"""
        try:
            with open(self.color_path, 'r') as file:
                self.styles = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.styles = {}
        return self.styles

    def apply_to_widget(self, widget, widget_name):
        """Применяет стиль к конкретному виджету"""
        if widget_name in self.styles:
            widget.setStyleSheet(self.format_style(self.styles[widget_name]))

    def apply_color_svg(self, svg_widget, strength: float, specified_color: str = "") -> None:
        """
        Применяет цвет к SVG виджету
        """
        try:
            if specified_color:
                color = QColor(specified_color)
                return svg_widget.applyColorEffect(color, strength)
            if "TitleBar" in self.styles and "border-bottom" in self.styles["TitleBar"]:
                border_value = self.styles["TitleBar"]["border-bottom"]
                color = QColor("#000000")

                # Ваш существующий код извлечения цвета
                gradient_match = re.search(r"qlineargradient\([^)]+\)", border_value)
                if gradient_match:
                    gradient_str = gradient_match.group(0)
                    color_match = re.search(r"stop:0\s+(#[0-9a-fA-F]+)", gradient_str)
                    if color_match:
                        color = QColor(color_match.group(1))
                else:
                    hex_match = re.search(r"#[0-9a-fA-F]{3,6}", border_value)
                    if hex_match:
                        color = QColor(hex_match.group(0))

                if isinstance(svg_widget, CustomSvgWidget):
                    # Используем наш кастомный метод
                    svg_widget.applyColorEffect(color, strength)
                else:
                    # Fallback для обычных QSvgWidget
                    self._apply_effect_fallback(svg_widget, color, strength)

        except Exception as e:
            logger.error(f"Ошибка в apply_color_svg: {e}")

    def _apply_effect_fallback(self, svg_widget, color, strength):
        """Fallback для обычных QSvgWidget"""
        try:
            effect = QGraphicsColorizeEffect()
            effect.setColor(color)
            effect.setStrength(strength)

            # Удаляем старый эффект
            old_effect = svg_widget.graphicsEffect()
            if old_effect:
                old_effect.deleteLater()

            svg_widget.setGraphicsEffect(effect)
            svg_widget.update()

        except Exception as e:
            logger.error(f"❌ Fallback ошибка: {e}")

    def format_style(self, style_dict):
        """Форматирует стиль в строку"""
        return '; '.join(f"{key}: {value}" for key, value in style_dict.items())
    
    def adjust_color(self, color, brightness=0):
        """
        Корректирует яркость цвета
        :param color: Исходный цвет (hex/rgb/rgba)
        :param brightness: Значение от -100 до 100
        :return: Новый цвет в hex-формате
        """
        from PySide6.QtGui import QColor
        try:
            qcolor = QColor(color)
            if brightness > 0:
                return qcolor.lighter(100 + brightness).name()
            elif brightness < 0:
                return qcolor.darker(100 - brightness).name()
            return qcolor.name()
        except:
            return color
        
    def get_color_from_border(self, widget_key):
        """Извлекает цвет или градиент из CSS-свойства border"""
        try:
            if widget_key and widget_key in self.styles:
                style = self.styles[widget_key]
                border_value = style.get("border", "")

                # Сначала ищем градиент в border
                import re
                gradient_match = re.search(
                    r'qlineargradient\([^)]*\)|qradialgradient\([^)]*\)|qconicalgradient\([^)]*\)',
                    border_value
                )
                
                if gradient_match:
                    return gradient_match.group(0)  # Возвращаем градиент как есть
                
                # Если градиента нет, ищем простой цвет
                color_match = re.search(
                    r'#(?:[0-9a-fA-F]{3}){1,2}|rgb\([^)]*\)|rgba\([^)]*\)',
                    border_value
                )
                return color_match.group(0) if color_match else "#05B8CC"
                
        except Exception as e:
            logger.error(f"Ошибка извлечения цвета: {e}")
        return "#BB05CC"
    
    def apply_progressbar(self, key=None, widget=None, style="solid"):
        """
        Применяет стиль к прогресс-бару
        :param style: "solid" (default), "looper", "circle"
        :param key: Ключ из стилей для извлечения цвета (например "QPushButton")
        :param widget: Ссылка на виджет QProgressBar или CustomProgressBar
        """
        if not widget or not hasattr(widget, 'setStyleSheet'):
            logger.warning("Не передан виджет или он не поддерживает стилизацию")
            return

        try:
            # Получаем цвет или градиент из стилей
            color_or_gradient = self.get_color_from_border(key) if key else "#05B8CC"

            # Если виджет является CustomProgressBar (круговой или looper)
            if hasattr(widget, 'style') and hasattr(widget, 'setProgressColor'):
                
                # Для кругового прогрессбара
                if widget.style == "circle":
                    # Обрабатываем градиент или цвет для кругового прогрессбара
                    if self.is_gradient(color_or_gradient):
                        # Если это градиент, используем первый цвет для прогресса
                        gradient = self.parse_gradient(color_or_gradient, widget.width(), widget.height())
                        widget.setProgressGradient(gradient)
                    else:
                        # Если это простой цвет
                        widget.setProgressColor(color_or_gradient)
                    
                    # Автоматически настраиваем дополнительные цвета
                    self.setup_circular_colors(widget, color_or_gradient)
                
                # Для линейных прогрессбаров применяем CSS стиль
                elif widget.style in ["default", "looper"]:
                    if self.is_gradient(color_or_gradient):
                        # Для градиента создаем специальный CSS
                        progress_style = self.create_gradient_css(color_or_gradient, widget.style)
                    else:
                        # Для простого цвета используем старую логику
                        progress_style = self.create_solid_css(color_or_gradient, widget.style)
                    
                    widget.linear_progress.setStyleSheet(progress_style)
                
                return

            # Старый функционал для обычного QProgressBar
            if self.is_gradient(color_or_gradient):
                progress_style = self.create_gradient_css(color_or_gradient, style)
            else:
                progress_style = self.create_solid_css(color_or_gradient, style)
                
            widget.setStyleSheet(progress_style)

        except Exception as e:
            logger.error(f"Ошибка применения стиля прогресс-бара: {e}")
            # Применяем минимальный рабочий стиль при ошибках
            fallback_style = """
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                }
                QProgressBar::chunk {
                    background-color: #05B8CC;
                }
            """
            if hasattr(widget, 'linear_progress'):
                widget.linear_progress.setStyleSheet(fallback_style)
            else:
                widget.setStyleSheet(fallback_style)

    def is_gradient(self, color_string):
        """Проверяет, является ли строка градиентом"""
        return color_string.startswith('qlineargradient') or color_string.startswith('qradialgradient')

    def parse_gradient(self, gradient_string, width, height):
        """Создает QLinearGradient из строки"""
        try:
            # Парсим параметры градиента
            import re
            params = re.findall(r'([xy]\d):([\d.]+)', gradient_string)
            stops = re.findall(r'stop:([\d.]+)\s+([^,)]+)', gradient_string)
            
            # Создаем градиент
            gradient = QLinearGradient(0, 0, width, height)
            
            for stop in stops:
                pos = float(stop[0])
                color = stop[1].strip()
                gradient.setColorAt(pos, QColor(color))
                
            return gradient
        except Exception as e:
            logger.error(f"Ошибка парсинга градиента: {e}")
            # Возвращаем градиент по умолчанию
            gradient = QLinearGradient(0, 0, width, height)
            gradient.setColorAt(0, QColor("#05B8CC"))
            gradient.setColorAt(1, QColor("#05B8CC"))
            return gradient

    def get_first_gradient_color(self, gradient_string):
        """Извлекает первый цвет из градиента"""
        try:
            import re
            stops = re.findall(r'stop:([\d.]+)\s+([^,)]+)', gradient_string)
            if stops:
                return stops[0][1].strip()
        except:
            pass
        return "#05B8CC"

    def setup_circular_colors(self, widget, color_or_gradient):
        """Автоматически настраивает цвета для кругового прогрессбара"""
        if self.is_gradient(color_or_gradient):
            first_color = self.get_first_gradient_color(color_or_gradient)
            base_color = QColor(first_color)
        else:
            base_color = QColor(color_or_gradient)
        
        # Фон под полосой прогресса (темнее основного цвета)
        widget.setTrackColor(base_color.darker(300))
        
        # Внутренняя область (еще темнее)
        # widget.setBackgroundColor(base_color.darker(300))

    def create_gradient_css(self, gradient, style_type):
        """Создает CSS для градиентного прогрессбара"""
        if style_type == "looper":
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_gradient_border(gradient)};
                    border-radius: 5px;
                    background: {self.adjust_gradient_background(gradient)};
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: {gradient};
                    border-radius: 2px;
                    width: 20px;
                    margin: 1px;
                }}
            """
        else:  # solid или default
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_gradient_border(gradient)};
                    border-radius: 5px;
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: {gradient};
                }}
            """

    def create_solid_css(self, color, style_type):
        """Создает CSS для одноцветного прогрессбара (старая логика)"""
        if style_type == "looper":
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_color(color, brightness=-30)};
                    border-radius: 5px;
                    background: {self.adjust_color(color, brightness=-80)};
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {self.adjust_color(color, brightness=-10)},
                        stop:1 {color}
                    );
                    border-radius: 2px;
                    width: 20px;
                    margin: 1px;
                }}
            """
        else:
            return f"""
                QProgressBar {{
                    border: 1px solid {self.adjust_color(color, brightness=-30)};
                    border-radius: 5px;
                    height: 20px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {self.adjust_color(color, brightness=-10)},
                        stop:1 {color}
                    );
                }}
            """

    def adjust_gradient_border(self, gradient):
        """Создает темную версию градиента для border"""
        # Для простоты используем первый цвет градиента, затемненный
        first_color = self.get_first_gradient_color(gradient)
        return self.adjust_color(first_color, brightness=-30)

    def adjust_gradient_background(self, gradient):
        """Создает очень темную версию градиента для background"""
        first_color = self.get_first_gradient_color(gradient)
        return self.adjust_color(first_color, brightness=-80)

def main():
    try:
        app = QApplication(sys.argv)
        window = UpdateWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Ошибка {e}")

if __name__ == "__main__":
    main()