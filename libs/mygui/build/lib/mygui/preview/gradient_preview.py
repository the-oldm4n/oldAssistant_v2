"""Виджет предпросмотра градиента"""
import math
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPainterPath, QPen
from PySide6.QtWidgets import QLabel

class GradientPreview(QLabel):
    """Виджет для предпросмотра градиента с бордером"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.color1 = QColor("#000000")
        self.color2 = QColor("#ffffff")
        self.angle = 0
        self.border_color = QColor("#cccccc")
        self.border_width = 1
        self.border_radius = 2

    def set_gradient(self, color1, color2, angle):
        self.color1 = QColor(color1) if color1 else QColor("#000000")
        self.color2 = QColor(color2) if color2 else QColor("#ffffff")
        self.angle = angle
        self.update()

    def set_border(self, color="#cccccc", width=1, radius=2):
        """Установить параметры бордера"""
        self.border_color = QColor(color)
        self.border_width = width
        self.border_radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Создаем градиент
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        
        # Рассчитываем точки градиента
        rad = math.radians(self.angle)
        x1 = 0.5 - 0.5 * math.cos(rad)
        y1 = 0.5 - 0.5 * math.sin(rad)
        x2 = 0.5 + 0.5 * math.cos(rad)
        y2 = 0.5 + 0.5 * math.sin(rad)
        
        gradient.setColorAt(0, self.color1)
        gradient.setColorAt(1, self.color2)
        gradient.setStart(self.width() * x1, self.height() * y1)
        gradient.setFinalStop(self.width() * x2, self.height() * y2)
        
        path = QPainterPath()
        path.addRoundedRect(
            self.border_width // 2,
            self.border_width // 2,
            self.width() - self.border_width,
            self.height() - self.border_width,
            self.border_radius,
            self.border_radius
        )
        
        painter.fillPath(path, gradient)
        
        if self.border_width > 0:
            pen = QPen(self.border_color)
            pen.setWidth(self.border_width)
            painter.setPen(pen)
            painter.drawPath(path)
        
        painter.end()