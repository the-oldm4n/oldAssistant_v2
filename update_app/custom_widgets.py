from PySide6.QtCore import Property, QPropertyAnimation
from PySide6.QtGui import QColor, Qt, QPen, QColor, QLinearGradient, QBrush, QPainter, \
    QPixmap, QConicalGradient, QRadialGradient
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsColorizeEffect, QProgressBar, QGraphicsEffect
from utils import logger


class CustomProgressBar(QWidget):
    def __init__(self, parent=None, style="default", circle_size=100, line_width=2):
        super().__init__(parent)
        self.style = style
        self.circle_size = circle_size
        self.value = 0
        self.max_value = 100
        self.line_width = line_width
        
        # Цвета для кругового прогрессбара
        self.progress_color = QColor("#3995FF")          # Цвет самой полосы прогресса
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
        self._gradient_effect = None  # Новый эффект для градиентов
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

            # Удаляем градиентный эффект если был
            if self._gradient_effect:
                self._gradient_effect.deleteLater()
                self._gradient_effect = None

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
            logger.error(f"[CUSTOMSVG] Ошибка применения цвета: {e}")
            return False

    def applyGradientEffect(self, gradient_data, strength=1.0):
        """
        БЕЗОПАСНЫЙ метод для применения градиента
        """
        try:
            if self._color_effect:
                self._color_effect.deleteLater()
                self._color_effect = None

            if self._gradient_effect:
                self._gradient_effect.deleteLater()

            self._gradient_effect = GradientColorizeEffect(self)
            self._gradient_effect.setGradient(gradient_data)
            self._gradient_effect.setStrength(strength)
            self.setGraphicsEffect(self._gradient_effect)

            self._forceUpdate()
            return True

        except Exception as e:
            if gradient_data and gradient_data.get('colors'):
                first_color = gradient_data['colors'][0][1]
                return self.applyColorEffect(first_color, strength)
            return False

    def _forceUpdate(self):
        """Принудительное обновление (оригинальный метод - НЕ ТРОГАЕМ)"""
        self.update()
        self.repaint()
        if self._parent_button:
            self._parent_button.update()

    def getEffectColor(self):
        return self._current_color

    def setEffectColor(self, color):
        self.applyColorEffect(color, self._current_strength)

    effectColor = Property(QColor, getEffectColor, setEffectColor)


class GradientColorizeEffect(QGraphicsEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gradient_data = None
        self.strength = 1.0

    def setGradient(self, gradient_data):
        self.gradient_data = gradient_data
        self.update()

    def setStrength(self, strength):
        self.strength = strength
        self.update()

    def draw(self, painter):
        if not self.gradient_data:
            self.drawSource(painter)
            return

        # Получаем pixmap источника (наш черный SVG)
        pixmap = self.sourcePixmap(Qt.DeviceCoordinates)
        if pixmap.isNull():
            return

        # Сохраняем состояние painter
        painter.save()
        painter.setOpacity(self.strength)

        # Создаем градиент
        rect = self.sourceBoundingRect()
        gradient = self._create_gradient(rect)

        # Создаем маску из черного SVG
        mask_pixmap = QPixmap(pixmap.size())
        mask_pixmap.fill(Qt.transparent)
        
        mask_painter = QPainter(mask_pixmap)
        mask_painter.setCompositionMode(QPainter.CompositionMode_Source)
        mask_painter.drawPixmap(0, 0, pixmap)
        mask_painter.end()

        # Рисуем градиент с маской
        gradient_pixmap = QPixmap(pixmap.size())
        gradient_pixmap.fill(Qt.transparent)
        
        gradient_painter = QPainter(gradient_pixmap)
        gradient_painter.fillRect(gradient_pixmap.rect(), QBrush(gradient))
        gradient_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        gradient_painter.drawPixmap(0, 0, mask_pixmap)
        gradient_painter.end()

        # Рисуем результат
        painter.drawPixmap(0, 0, gradient_pixmap)  # offset не нужен
        painter.restore()

    def _create_gradient(self, rect):
        if not self.gradient_data:
            return QLinearGradient(0, 0, 1, 0)

        gradient_type = self.gradient_data.get('type', 'linear')
        colors = self.gradient_data.get('colors', [])

        if gradient_type == 'linear':
            gradient = self._create_linear_gradient(rect)
        elif gradient_type == 'radial':
            gradient = self._create_radial_gradient(rect)
        elif gradient_type == 'conical':
            gradient = self._create_conical_gradient(rect)
        else:
            gradient = QLinearGradient(0, 0, 1, 0)

        # Добавляем цвета
        for pos, color in colors:
            gradient.setColorAt(pos, color)

        return gradient

    def _create_linear_gradient(self, rect):
        direction = self.gradient_data.get('direction', 0)
        
        if isinstance(direction, (int, float)):
            import math
            angle_rad = math.radians(direction)
            x1 = 0.5 - 0.5 * math.cos(angle_rad)
            y1 = 0.5 - 0.5 * math.sin(angle_rad)
            x2 = 0.5 + 0.5 * math.cos(angle_rad)
            y2 = 0.5 + 0.5 * math.sin(angle_rad)
            
            return QLinearGradient(
                rect.width() * x1, rect.height() * y1,
                rect.width() * x2, rect.height() * y2
            )
        else:
            x1, y1, x2, y2 = direction
            return QLinearGradient(
                rect.width() * x1, rect.height() * y1,
                rect.width() * x2, rect.height() * y2
            )

    def _create_radial_gradient(self, rect):
        center = self.gradient_data.get('center', (0.5, 0.5))
        radius = self.gradient_data.get('radius', 0.5)
        
        cx, cy = center
        return QRadialGradient(
            rect.width() * cx, rect.height() * cy,
            min(rect.width(), rect.height()) * radius
        )

    def _create_conical_gradient(self, rect):
        center = self.gradient_data.get('center', (0.5, 0.5))
        angle = self.gradient_data.get('angle', 0)
        
        cx, cy = center
        return QConicalGradient(rect.width() * cx, rect.height() * cy, angle)