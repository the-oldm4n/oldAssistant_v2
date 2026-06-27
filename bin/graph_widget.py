from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QLinearGradient, QFont, QPainterPath
from PySide6.QtWidgets import QWidget

class SimpleGraph(QWidget):
    """Современный график с линией и точками на чистом Qt"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setStyleSheet("background: transparent;")
        
        # Цвета по умолчанию
        self.line_color = QColor(0, 180, 255)      # Цвет линии
        self.fill_color_start = QColor(0, 180, 255, 80)   # Начало градиента
        self.fill_color_end = QColor(0, 180, 255, 5)      # Конец градиента
        self.point_color = QColor(0, 180, 255)     # Цвет точки
        self.point_border_color = QColor(255, 255, 255)  # Цвет обводки точки
        self.point_size = 4                       # Размер точки (радиус)
        self.glow_size = 10                       # Размер свечения
        
        # Данные по умолчанию
        self.labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        self.values = [0, 0, 0, 0, 0, 0, 0]
        self.max_value = 1
        
    def update_colors(self, line_color=None, fill_color_start=None, fill_color_end=None,
                      point_color=None, point_border_color=None):
        """
        Обновляет цвета графика
        
        Args:
            line_color: QColor или str (hex) - цвет линии
            fill_color_start: QColor или str (hex) - начало градиента заливки
            fill_color_end: QColor или str (hex) - конец градиента заливки
            point_color: QColor или str (hex) - цвет точки
            point_border_color: QColor или str (hex) - цвет обводки точки
        """
        if line_color is not None:
            self.line_color = self._to_qcolor(line_color)
        
        if fill_color_start is not None:
            color = self._to_qcolor(fill_color_start)
            color.setAlpha(80)  # Полупрозрачный
            self.fill_color_start = color
        
        if fill_color_end is not None:
            color = self._to_qcolor(fill_color_end)
            color.setAlpha(5)   # Почти прозрачный
            self.fill_color_end = color
        
        if point_color is not None:
            self.point_color = self._to_qcolor(point_color)
        
        if point_border_color is not None:
            self.point_border_color = self._to_qcolor(point_border_color)
        
        self.update()  # Перерисовываем график
    
    def set_point_size(self, size=4):
        """Устанавливает размер точек (радиус)"""
        self.point_size = size
        self.glow_size = size * 3  # Свечение в 3 раза больше
        self.update()
    
    def _to_qcolor(self, color):
        """Преобразует цвет в QColor"""
        if isinstance(color, QColor):
            return QColor(color)
        elif isinstance(color, str):
            # Если hex строка
            if color.startswith('#'):
                return QColor(color)
            # Если название цвета
            return QColor(color)
        else:
            return QColor(0, 180, 255)  # Fallback
        
    def set_data(self, labels, values):
        """Обновляет данные графика"""
        self.labels = labels
        self.values = values
        if not values or all(v == 0 for v in values):
            self.max_value = 1
        else:
            self.max_value = max(values)
        self.update()
        
    def paintEvent(self, event):
        if not self.values:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Отступы
        left = 40
        right = 20
        top = 30
        bottom = 35
        width = self.width() - left - right
        height = self.height() - top - bottom
        
        if height <= 0:
            return
        
        # Проверяем, все ли значения равны 0
        all_zero = all(v == 0 for v in self.values)
        
        if all_zero:
            # Рисуем подписи дней
            step = width / (len(self.values) - 1) if len(self.values) > 1 else width
            
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.setFont(QFont("Arial", 9))
            
            for i, label in enumerate(self.labels):
                x = left + i * step
                painter.drawText(
                    QRectF(x - 20, top + height + 8, 40, 20),
                    Qt.AlignmentFlag.AlignCenter,
                    label
                )
            
            # Рисуем горизонтальную линию (ось X)
            painter.setPen(QPen(QColor(80, 80, 80), 1))
            painter.drawLine(
                QPointF(left, top + height),
                QPointF(left + width, top + height)
            )
            
            # Подпись нуля
            painter.setPen(QPen(QColor(120, 120, 120)))
            painter.setFont(QFont("Arial", 7))
            painter.drawText(
                QRectF(5, top + height - 8, 30, 15),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "0"
            )
            
            # Рисуем текст "Нет данных"
            painter.setPen(QPen(QColor(150, 150, 150, 150)))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(
                QRectF(0, 0, self.width(), self.height() - 30),
                Qt.AlignmentFlag.AlignCenter,
                "Нет данных за неделю"
            )
            return
        
        # Вычисляем координаты точек
        points = []
        step = width / (len(self.values) - 1) if len(self.values) > 1 else width
        
        for i, value in enumerate(self.values):
            x = left + i * step
            y = top + height - (value / self.max_value) * height
            points.append(QPointF(x, y))
        
        # 1. Рисуем ЗАПОЛНЕННУЮ ОБЛАСТЬ под линией (градиент)
        path = QPainterPath()
        path.moveTo(points[0])
        
        for point in points[1:]:
            path.lineTo(point)
        
        path.lineTo(points[-1].x(), top + height)
        path.lineTo(points[0].x(), top + height)
        path.closeSubpath()
        
        # Градиент для заливки (используем цвета из self)
        gradient = QLinearGradient(0, top, 0, top + height)
        gradient.setColorAt(0, self.fill_color_start)
        gradient.setColorAt(0.5, self.fill_color_start)
        gradient.setColorAt(1, self.fill_color_end)
        
        painter.fillPath(path, gradient)
        
        # 2. Рисуем ОСНОВНУЮ ЛИНИЮ
        pen = QPen(self.line_color, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        if len(points) > 1:
            path_line = QPainterPath()
            path_line.moveTo(points[0])
            
            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                
                if i == 0:
                    path_line.lineTo(p2)
                else:
                    cp1 = QPointF(
                        (p1.x() + p2.x()) / 2,
                        p1.y()
                    )
                    cp2 = QPointF(
                        (p1.x() + p2.x()) / 2,
                        p2.y()
                    )
                    path_line.cubicTo(cp1, cp2, p2)
            
            painter.drawPath(path_line)
        else:
            painter.drawPoint(points[0])
        
        # 3. Рисуем ТОЧКИ
        for i, point in enumerate(points):
            # Внешнее свечение
            glow_color = QColor(self.point_color)
            glow_color.setAlpha(30)
            painter.setBrush(glow_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, self.glow_size, self.glow_size)
            
            # Основная точка
            painter.setBrush(self.point_color)
            painter.setPen(QPen(self.point_border_color, 2))
            painter.drawEllipse(point, self.point_size, self.point_size)
            
            # Значение над точкой
            painter.setPen(QPen(QColor(220, 220, 220)))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            
            text_rect = QRectF(point.x() - 15, point.y() - 28, 30, 18)
            painter.setBrush(QColor(0, 0, 0, 100))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(text_rect, 4, 4)
            
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(self.values[i])
            )
            
            # Подпись под графиком
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                QRectF(point.x() - 20, top + height + 8, 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                self.labels[i] if i < len(self.labels) else ""
            )
        
        # 4. ГОРИЗОНТАЛЬНАЯ ЛИНИЯ (ось X)
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawLine(
            QPointF(left, top + height),
            QPointF(left + width, top + height)
        )
        
        # 5. ПОДПИСИ ЗНАЧЕНИЙ
        if self.max_value > 0:
            painter.setFont(QFont("Arial", 7))
            
            # Подпись максимального значения слева
            painter.setPen(QPen(QColor(120, 120, 120)))
            painter.drawText(
                QRectF(5, top - 5, 30, 15),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(self.max_value)
            )
            
            # Подпись нуля
            painter.drawText(
                QRectF(5, top + height - 8, 30, 15),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "0"
            )