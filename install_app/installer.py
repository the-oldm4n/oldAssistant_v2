import json
import re
import shutil
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QColor, Qt, QPen, QPainter, QBrush, QLinearGradient
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Property, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, 
    QVBoxLayout, QGraphicsColorizeEffect, QSizePolicy, QProgressBar, QSpacerItem, QFileDialog
)
import sys
from utils import get_path, logger, get_base_directory


class InstallerWindow(QWidget):
    """
    Инсталлятор
    """

    def __init__(self):
        super().__init__()
        self.root_dir = get_base_directory()
        self.update_pack_dir = self.root_dir / "update_pack"
        self.update_file_path = get_path("Update.exe")
        self.install_path = None
        self.setWindowIcon(QIcon(get_path('icon.ico')))
        self.parent_style = self.root_dir / "user_settings" / "color_settings.json"
        self.style_path = get_path('color.json')
        if self.parent_style.exists():
            style = self.parent_style
        else:
            style = self.style_path
        self.svg_path = get_path("logo.svg")
        self.style_manager = ApplyColor(style)
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()
        self.start_installation_process()

    def init_ui(self):
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
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(15, 0, 15, 10)
        content_layout.addStretch()

        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(120, 110)
        self.svg_image.setStyleSheet("background: transparent; border: none;")
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignCenter)
        
        self.progress = SVGProgressBar(
            svg_widget=self.svg_image,
            style="circle",
            circle_size=180,
            show_text=False,
            line_width=3)
        self.progress.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

        # Текст
        self.label = QLabel("Выбор папки установки...")
        self.label.setStyleSheet("background-color: transparent; font-size: 14px")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        content_layout.addWidget(self.label)

        self.button_spacer = QSpacerItem(20, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)
        content_layout.addItem(self.button_spacer)

        # Кнопка выбора папки
        self.folder_button = QPushButton("Выбрать папку")
        self.folder_button.clicked.connect(self.choice_folder_path)
        self.folder_button.setStyleSheet("""width:100px; border-radius:5px""")
        content_layout.addWidget(self.folder_button, alignment=Qt.AlignCenter)

        # Кнопка выхода
        self.error_button = QPushButton("Закрыть")
        self.error_button.clicked.connect(self.quit_application)
        self.error_button.setStyleSheet("""width:100px; border-radius:5px""")
        self.error_button.hide()
        content_layout.addWidget(self.error_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)
        layout.addWidget(self.main_widget, 1)

    def start_installation_process(self):
        """Начало процесса установки"""
        self.set_status("Выберите папку для установки", 0)

    def installer(self):
        try:
            if self.install_path:
                # создание структуры, копирование и запуск файла update.exe
                self.create_installation_structure(self.install_path)
            else:
                self.show_error("Папка не выбрана")
        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            self.show_error("Ошибка установки")

    def choice_folder_path(self):
        """Выбор папки для установки с проверкой на кириллицу"""
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Выберите папку для установки Assistant",
                str(Path.home()),
                QFileDialog.ShowDirsOnly
            )

            if folder:
                # Проверяем путь на наличие кириллицы
                if self.has_cyrillic(folder):
                    self.set_status("Ошибка: путь содержит кириллицу!", 0)
                    # Показываем кнопку снова для повторного выбора
                    self.folder_button.show()
                    return

                self.install_path = Path(folder)
                self.set_status("Подготовка компонентов...", 30)
                self.button_spacer.changeSize(20, 40)
                self.folder_button.hide()
                QTimer.singleShot(1000, self.installer)
            else:
                self.set_status("Папка не выбрана", 0)

        except Exception as e:
            logger.error(f"Ошибка выбора папки: {e}")
            self.show_error("Ошибка выбора папки")

    def has_cyrillic(self, text):
        """Проверяет, содержит ли текст кириллические символы с помощью regex"""
        return bool(re.search('[а-яА-ЯёЁ]', text))

    def create_installation_structure(self, install_path):
        """Создание структуры папок для установки"""
        try:
            self.set_status("Создание структуры установки...", 50)

            install_path = Path(install_path)
            # Создаем путь:
            assistant_dir = install_path / "Assistant"
            assistant_dir.mkdir(parents=True, exist_ok=True)

            # Создаем папку _internal внутри Assistant
            internal_dir = assistant_dir / "_internal"
            internal_dir.mkdir(parents=True, exist_ok=True)

            # Копируем сам Update.exe в папку _internal
            target_exe_path = internal_dir / "Update.exe"
            current_exe_path = self.update_file_path

            if current_exe_path != target_exe_path:
                shutil.copy2(current_exe_path, target_exe_path)

            logger.info(f"Структура создана: {assistant_dir}")

            self.set_status("Запуск обновления...", 100)
            QTimer.singleShot(1000, self.run_update)
        except Exception as e:
            logger.error(f"Ошибка создания структуры: {e}")
            self.show_error("Ошибка установки")

    def run_update(self):
        try:
            if self.install_path:
                internal_dir = self.install_path / "Assistant" / "_internal"
                update_exe_path = internal_dir / "Update.exe"

                if update_exe_path.exists():
                    subprocess.Popen([str(update_exe_path), "--install-mode"])
                    logger.info("Update.exe запущен")
                    self.close()
                else:
                    logger.info("Update.exe не найден")
                    self.show_error("Update.exe не найден")
        except Exception as e:
            logger.error(f"Ошибка при запуске Update.exe: {e}")
            self.show_error("Ошибка запуска")

    def set_status(self, text, progress=None):
        self.label.setText(text)
        if progress is not None:
            self.progress.setValue(progress)

    def show_error(self, message):
        self.label.setText(message)
        self.error_button.show()

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
            if hasattr(self, 'container'):
                self.title_bar_widget.setObjectName("ConfirmDialogContainer")
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
            self.main_widget.setStyleSheet("""border-radius:20px""")
        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def quit_application(self):
        sys.exit(1)


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

    def get_color_from_border(self, widget_key):
        """Извлекает цвет из CSS-свойства border"""
        try:
            if widget_key and widget_key in self.styles:
                style = self.styles[widget_key]
                border_value = style.get("border", "")

                # Ищем цвет в форматах: #RRGGBB, rgb(), rgba()
                import re
                color_match = re.search(
                    r'#(?:[0-9a-fA-F]{3}){1,2}|rgb\([^)]*\)|rgba\([^)]*\)',
                    border_value
                )
                return color_match.group(0) if color_match else "#05B8CC"  # Цвет по умолчанию
        except Exception as e:
            logger.error(f"Ошибка извлечения цвета: {e}")
        return "#05B8CC"  # Возвращаем синий по умолчанию при ошибках

    def apply_progressbar(self, key=None, widget=None, style="solid"):
        """
        Применяет стиль к прогресс-бару
        :param style: стиль заполнения полоски
        :param key: Ключ из стилей для извлечения цвета (например "QPushButton")
        :param widget: Ссылка на виджет QProgressBar
        """
        if not widget or not hasattr(widget, 'setStyleSheet'):
            logger.warning("Не передан виджет или он не поддерживает стилизацию")
            return

        try:
            # Получаем цвет из стилей или используем по умолчанию
            color = self.get_color_from_border(key) if key else "#05B8CC"

            if style == "solid":
                progress_style = f"""
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
            else:
                # Формируем стиль с плавной анимацией
                progress_style = f"""
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
            widget.setStyleSheet(progress_style)

        except Exception as e:
            logger.error(f"Ошибка применения стиля прогресс-бара: {e}")
            # Применяем минимальный рабочий стиль при ошибках
            widget.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                }
                QProgressBar::chunk {
                    background-color: #05B8CC;
                }
            """)

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

def main():
    try:
        app = QApplication(sys.argv)
        window = InstallerWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Ошибка {e}")

if __name__ == "__main__":
    main()