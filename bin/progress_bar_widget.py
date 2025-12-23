from PySide6.QtWidgets import QProgressBar, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, Property
from PySide6.QtGui import QPainter, QPen, QColor, QLinearGradient, QBrush


class CustomProgressBar(QWidget):
    def __init__(self, parent=None, style="default", circle_size=100, line_width=2, padding=20):
        super().__init__(parent)
        self.style = style
        self.circle_size = circle_size
        self.padding = padding
        self.value = 0
        self.max_value = 100
        self.line_width = line_width
        self._value = 0
        
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
        
    def _get_value(self):
        return self._value

    def _set_value(self, val):
        self._value = val
        self.update()

    # Объявляем свойство 'value'
    value = Property(int, _get_value, _set_value)

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
            diameter = min(self.width(), self.height()) - self.padding
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
    def __init__(self, parent=None, style="default", circle_size=200, svg_widget=None, show_text=True, 
                 line_width=2, padding=20):
        # Передаем line_width в родительский конструктор
        super().__init__(parent, style, circle_size, line_width, padding)
        self.svg_widget = svg_widget
        self.padding = padding
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
            diameter = min(self.width(), self.height()) - self.padding
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