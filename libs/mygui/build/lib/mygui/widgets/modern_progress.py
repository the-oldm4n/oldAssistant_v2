from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Property, QPropertyAnimation, QRectF, QSize, QPointF, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QRadialGradient, QFont, QConicalGradient, QPainterPath
from enum import Enum


class ProgressType(Enum):
    LINEAR = "linear"
    CIRCLE = "circle"

class ModernProgressBar(QWidget):
    def __init__(self, parent=None, progress_type=ProgressType.LINEAR, value=0, max_value=100):
        super().__init__(parent)
        
        # --- Основные параметры ---
        self._type = progress_type
        self._value = 0
        self._max_value = max_value
        self._text_visible = True
        self._text_format = "{value}%"  # Шаблон текста
        
        # --- Настройки для LINEAR ---
        self._linear_height = 30
        self._linear_radius = 15  # Border radius
        
        # --- Настройки для CIRCLE ---
        self._circle_diameter = 150
        self._line_width = 15
        self._start_angle = 90 * 16  # Начало сверху (в градусах * 16)
        
        # --- Цвета и Градиенты ---
        # Можно хранить QColor или QGradient
        self._track_color = QColor(40, 40, 40, 150)
        self._progress_color = QColor("#B40000") 
        self._text_color = QColor(255, 255, 255)
        
        # Флаги, используем ли градиент вместо сплошного цвета
        self._use_progress_gradient = False
        self._progress_gradient = None
        
        # --- Анимация ---
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(500)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Применение начальных размеров
        self._update_geometry()

    # ==========================================
    # СВОЙСТВА (Properties) для анимации и Qt Designer
    # ==========================================
    
    @Property(int)
    def value(self):
        return self._value
    
    @value.setter
    def value(self, val):
        """Сеттер свойства value (имя функции должно совпадать с именем свойства)"""
        val = max(0, min(val, self._max_value))
        if self._value != val:
            self._value = val
            self.update()

    def setValue(self, val):
        """Обычный метод для вызова из кода: bar.setValue(50)"""
        self.value = val

    @Property(int)
    def maximum(self):
        return self._max_value
    
    @maximum.setter
    def maximum(self, val):
        if val > 0:
            self._max_value = val
            self.update()

    def setMaximum(self, val):
        self.maximum = val

    @Property(bool)
    def textVisible(self):
        return self._text_visible
    
    @textVisible.setter
    def textVisible(self, visible):
        """Сеттер свойства textVisible (имя функции должно быть textVisible)"""
        if self._text_visible != visible:
            self._text_visible = visible
            self.update()

    def setTextVisible(self, visible):
        """Обычный метод для вызова из кода: bar.setTextVisible(True)"""
        self.textVisible = visible

    @Property(str)
    def textFormat(self):
        return self._text_format

    @textFormat.setter
    def textFormat(self, fmt):
        self._text_format = fmt
        self.update()

    def setTextFormat(self, fmt):
        self.textFormat = fmt

    # ==========================================
    # МЕТОДЫ НАСТРОЙКИ РАЗМЕРОВ
    # ==========================================

    def set_linear_dimensions(self, height=30, radius=15):
        """Настройка размеров для линейного режима"""
        self._linear_height = height
        self._linear_radius = radius
        self._type = ProgressType.LINEAR
        self._update_geometry()
        self.update()

    def set_circle_dimensions(self, diameter=150, line_width=15):
        """Настройка размеров для кругового режима"""
        self._circle_diameter = diameter
        self._line_width = line_width
        self._type = ProgressType.CIRCLE
        self._update_geometry()
        self.update()

    def _update_geometry(self):
        """Обновление фиксированного размера виджета в зависимости от типа"""
        if self._type == ProgressType.LINEAR:
            # Ширина может быть любой (stretch), высота фиксирована
            self.setFixedHeight(self._linear_height)
            self.setMinimumWidth(50)
        else:
            # Круглый всегда квадратный
            size = self._circle_diameter
            self.setFixedSize(size, size)

    # ==========================================
    # МЕТОДЫ НАСТРОЙКИ ЦВЕТОВ И ГРАДИЕНТОВ
    # ==========================================

    def set_track_color(self, color):
        """Установить цвет фона (трека)"""
        if isinstance(color, str):
            color = QColor(color)
        self._track_color = color
        self._use_track_gradient = False
        self.update()

    def set_progress_color(self, color):
        """Установить сплошной цвет прогресса"""
        if isinstance(color, str):
            color = QColor(color)
        self._progress_color = color
        self._use_progress_gradient = False
        self.update()

    def set_text_color(self, color):
        """Установить цвет текста"""
        if isinstance(color, str):
            color = QColor(color)
        self._text_color = color
        self.update()

    def set_progress_gradient(self, gradient):
        """
        Установить градиент для прогресса.
        Принимает QLinearGradient, QRadialGradient или QConicalGradient.
        """
        self._progress_gradient = gradient
        self._use_progress_gradient = True
        self.update()

    def create_linear_gradient(self, start_color, end_color, direction="horizontal"):
        """Хелпер для создания линейного градиента"""
        c1 = QColor(start_color) if isinstance(start_color, str) else start_color
        c2 = QColor(end_color) if isinstance(end_color, str) else end_color
        
        grad = QLinearGradient()
        if direction == "horizontal":
            grad.setStart(0, 0)
            grad.setFinalStop(self.width(), 0)
        elif direction == "vertical":
            grad.setStart(0, 0)
            grad.setFinalStop(0, self.height())
            
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        
        self.set_progress_gradient(grad)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self._type == ProgressType.LINEAR:
            self._draw_linear(painter)
        else:
            self._draw_circle(painter)
            
        painter.end()

    def _draw_linear(self, painter):
        w = self.width()
        h = self.height()
        radius = min(self._linear_radius, h / 2.0)
        
        # 1. Рисуем фон (Track)
        painter.setBrush(QBrush(self._track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)
        
        # 2. Вычисляем ширину прогресса
        if self._max_value > 0:
            progress_ratio = self._value / self._max_value
        else:
            progress_ratio = 0
            
        progress_w = int(w * progress_ratio)
        
        if progress_w > 0:
            # Создаем маску (clip path), чтобы прогресс обрезался по радиусу родителя
            clip_path = painter.clipPath()
            path = QPainterPath()
            path.addRoundedRect(0, 0, w, h, radius, radius)
            painter.setClipPath(path)
            
            # 3. Рисуем прогресс
            if self._use_progress_gradient and self._progress_gradient:
                # Настраиваем градиент под текущую ширину виджета (если нужно динамически)
                # Для простоты используем заданный градиент, но можно пересчитать координаты
                g = self._progress_gradient
                # Если градиент был создан с относительными координатами 0..1, Qt сам справится.
                # Если с абсолютными, возможно потребуется масштабирование.
                painter.setBrush(QBrush(g))
            else:
                painter.setBrush(QBrush(self._progress_color))
            
            # Рисуем прямоугольник прогресса (маска обрежет углы)
            painter.drawRect(0, 0, progress_w, h)
            
            # Восстанавливаем клип (опционально, но полезно для текста)
            painter.setClipPath(clip_path)
            
        # 4. Рисуем текст
        if self._text_visible:
            self._draw_text(painter, w, h)

    def _draw_circle(self, painter):
        diameter = self._circle_diameter
        radius = diameter / 2.0
        center = QPointF(radius, radius)

        offset = self._line_width / 2.0
        rect = QRectF(offset, offset, diameter - self._line_width, diameter - self._line_width)

        painter.setBrush(Qt.NoBrush)
        pen = QPen(self._track_color)
        pen.setWidth(self._line_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._max_value > 0:
            span_angle = int((self._value / self._max_value) * 360 * 16)
        else:
            span_angle = 0
            
        if span_angle > 0:
            painter.setBrush(Qt.NoBrush)
            
            if self._use_progress_gradient and self._progress_gradient:
                pen.setBrush(QBrush(self._progress_gradient))
            else:
                pen.setColor(self._progress_color)
                
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, -span_angle)

        if self._text_visible:
            self._draw_text(painter, diameter, diameter, is_circle=True)

    def _draw_text(self, painter, w, h, is_circle=False):
        if not self._text_format:
            return
            
        text = self._text_format.format(value=self._value, max=self._max_value)
        
        painter.setPen(self._text_color)
        font = painter.font()
        if is_circle:
            font.setPointSize(int(w / 10))
        else:
            font.setPointSize(int(h / 2.5))
        font.setBold(True)
        painter.setFont(font)
        
        painter.drawText(self.rect(), Qt.AlignCenter, text)
    
    def animate_to(self, target_value, duration=500):
        """Плавно изменить значение до target_value"""
        self._anim.setDuration(duration)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(target_value)
        self._anim.start()

# ==========================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ==========================================

# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)

#     window = QWidget()
#     window.setWindowTitle("Modern ProgressBar Demo")
#     layout = QVBoxLayout(window)
    
#     # --- Пример 1: Линейный с градиентом ---
#     label1 = QLabel("Linear with Gradient & Custom Radius")
#     layout.addWidget(label1)
    
#     bar1 = ModernProgressBar(progress_type=ProgressType.LINEAR)
#     bar1.set_linear_dimensions(height=40, radius=20)
#     # bar1.setValue(75)
#     bar1.create_linear_gradient("#05B8CC", "#00FFAA", direction="horizontal")
#     bar1.animate_to(75, 1000) # Анимация при старте
#     layout.addWidget(bar1)
    
#     # --- Пример 2: Линейный сплошной цвет ---
#     label2 = QLabel("Linear Solid Color")
#     layout.addWidget(label2)
    
#     bar2 = ModernProgressBar(progress_type=ProgressType.LINEAR)
#     bar2.set_linear_dimensions(height=20, radius=10)
#     bar2.set_progress_color("#FF5555")
#     bar2.set_track_color(QColor(50, 50, 50))
#     # bar2.setValue(40)
#     layout.addWidget(bar2)
    
#     # --- Пример 3: Круговой ---
#     label3 = QLabel("Circular Progress")
#     label3.setAlignment(Qt.AlignCenter)
#     layout.addWidget(label3)
    
#     circle_layout = QHBoxLayout()
#     circle_layout.addStretch()
    
#     bar3 = ModernProgressBar(progress_type=ProgressType.CIRCLE)
#     bar3.set_circle_dimensions(diameter=150, line_width=15)
#     bar3.set_progress_color("#FFD700") # Gold
#     bar3.setTextVisible(True)
#     bar3._text_format = "{value}%" 
#     bar3.setValue(0)
    
#     circle_layout.addWidget(bar3)
#     circle_layout.addStretch()
#     layout.addLayout(circle_layout)
    
#     # Кнопки для теста
#     btn_layout = QHBoxLayout()
#     btn_plus = QPushButton("+25%")
#     btn_minus = QPushButton("-25%")
    
#     def add_val():
#         v = min(100, bar3.value + 25)
#         bar3.animate_to(v)
#         bar1.animate_to(min(100, bar1.value + 25))
        
#     def sub_val():
#         v = max(0, bar3.value - 25)
#         bar3.animate_to(v)
#         bar1.animate_to(max(0, bar1.value - 25))
        
#     btn_plus.clicked.connect(add_val)
#     btn_minus.clicked.connect(sub_val)
    
#     btn_layout.addWidget(btn_minus)
#     btn_layout.addWidget(btn_plus)
#     layout.addLayout(btn_layout)
    
#     window.resize(400, 400)
#     window.show()
#     sys.exit(app.exec())