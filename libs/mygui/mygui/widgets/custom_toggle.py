from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget,QWidget
from PySide6.QtCore import Signal, QPropertyAnimation, Qt, QRectF, QPointF, QEasingCurve,\
    Property
from PySide6.QtGui import QColor, QBrush, QPen, QLinearGradient, QPainter,\
    QPainterPath

from mygui.core.apply_color import main_apply_colors
from mygui.core.signals import color_signal


class _CustomToggle(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        self._checked = checked
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self._color = QColor(color)
        self._update_colors()
        color_signal.color_changed.connect(self.set_color)
        
        
        self._morph_progress = 1.0 if checked else 0.0
        self._rotation_angle = 0.0
        
        # Анимации
        self.morph_animation = QPropertyAnimation(self, b"morph_progress")
        self.morph_animation.setDuration(400)
        self.morph_animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        self.rotation_animation = QPropertyAnimation(self, b"rotation_angle")
        self.rotation_animation.setDuration(400)
        self.rotation_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.setFixedSize(45, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.set_color()

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._start_animation()
            self.stateChanged.emit(2 if checked else 0)
            self.toggled.emit(checked)
    
    def isChecked(self):
        return self._checked
    
    def toggle(self):
        self.setChecked(not self._checked)
    
    def _start_animation(self):
        self.morph_animation.stop()
        self.rotation_animation.stop()
        
        self.morph_animation.setStartValue(self._morph_progress)
        self.morph_animation.setEndValue(1.0 if self._checked else 0.0)
        
        if self._checked:
            self.rotation_animation.setStartValue(self._rotation_angle)
            self.rotation_animation.setEndValue(1080)
        else:
            self.rotation_animation.setStartValue(self._rotation_angle)
            self.rotation_animation.setEndValue(0)
        
        self.morph_animation.start()
        self.rotation_animation.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
    
    def set_color(self):
        """Устанавливает цвет или градиент"""
        self.styles = self.style_manager.load_styles()
        color_data = self.style_manager.get_gradient_color()
        
        if isinstance(color_data, list):
            # Градиент - список цветов
            self._gradient_colors = color_data
            self._color = color_data[0]  # Первый цвет как основной
        else:
            # Один цвет
            self._color = QColor(color_data)
            self._gradient_colors = None
        
        self._update_colors()
        self.update()

    def _update_colors(self):
        """Вычисляет более темный цвет для фона"""
        # Более темный цвет для фона
        self.bg_color = self._get_darker_color(self._color)
        self.borger_color = self._color

    def _get_darker_color(self, color):
        """Возвращает более темную версию цвета"""
        darker = QColor(color)
        darker = darker.darker(110)
        return darker
    
    @Property(float)
    def morph_progress(self):
        return self._morph_progress
    
    @morph_progress.setter
    def morph_progress(self, value):
        self._morph_progress = value
        self.update()
    
    @Property(float)
    def rotation_angle(self):
        return self._rotation_angle
    
    @rotation_angle.setter
    def rotation_angle(self, value):
        self._rotation_angle = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фоновая дорожка
        bg_rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        painter.setBrush(QColor(240, 240, 240))
        painter.setPen(QPen(self.borger_color, 1))
        painter.drawRoundedRect(bg_rect, 11, 11)
        
        # Активная дорожка
        if self._morph_progress > 0:
            active_width = (self.width() - 4) * self._morph_progress
            
            # Определяем brush ДО отрисовки
            if hasattr(self, '_gradient_colors') and self._gradient_colors:
                # Градиент
                gradient = QLinearGradient(2, 2, active_width, self.height() - 4)
                for i, color in enumerate(self._gradient_colors):
                    gradient.setColorAt(i / (len(self._gradient_colors) - 1), color)
                brush = QBrush(gradient)
            else:
                # Обычный цвет
                active_color = self.bg_color
                active_color.setAlpha(220)
                brush = QBrush(active_color)
            
            # Отрисовка
            if active_width < 22:
                active_rect = QRectF(2, 2, 22, self.height() - 4)
                painter.setBrush(brush)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(active_rect, 11, 11)
                
                if active_width < 22:
                    clip_rect = QRectF(2 + active_width, 2, 22 - active_width, self.height() - 4)
                    painter.setClipRect(clip_rect)
                    painter.setBrush(QColor(240, 240, 240))
                    painter.setPen(QPen(self.borger_color, 1))
                    painter.drawRoundedRect(bg_rect, 11, 11)
                    painter.setClipping(False)
            else:
                active_rect = QRectF(2, 2, active_width, self.height() - 4)
                painter.setBrush(brush)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(active_rect, 11, 11)
        
        # Позиция крестика/галочки
        icon_x = 15 + (self.width() - 30) * self._morph_progress
        icon_pos = QPointF(icon_x, self.height() / 2)
        
        painter.save()
        painter.translate(icon_pos)
        
        if self._morph_progress < 0.8:
            # Вращаем крестик
            rotation = self._rotation_angle if self._checked else -self._rotation_angle
            painter.rotate(rotation)
            
            # Крестик такого же размера как галочка
            cross_alpha = 255 * (1.0 - self._morph_progress * 1.2) if self._checked else 255
            cross_color = QColor(100, 100, 100, int(cross_alpha))
            painter.setPen(QPen(cross_color, 2))
            
            # Уменьшаем размер крестика до размера галочки
            size = 4
            painter.drawLine(-size, -size, size, size)
            painter.drawLine(size, -size, -size, size)
        else:
            # Галочка
            check_color = QColor(255, 255, 255)
            painter.setPen(QPen(check_color, 2))
            
            path = QPainterPath()
            path.moveTo(-4, 0)
            path.lineTo(-1, 3)
            path.lineTo(5, -3)
            painter.drawPath(path)
        
        painter.restore()
 
 
class CustomToggle(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, text="", parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Тогл
        self.toggle = _CustomToggle(self, checked, color)
        self.toggle.stateChanged.connect(self.stateChanged)
        self.toggle.toggled.connect(self.toggled)
        
        # Лейбл
        self.label = QLabel(text)
        self.label.setStyleSheet("background: transparent")
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.mousePressEvent = self._on_label_click
        
        layout.addWidget(self.toggle)
        layout.addWidget(self.label)
        layout.addStretch()
    
    def _on_label_click(self, event):
        self.toggle.toggle()
        event.accept()
    
    def setChecked(self, checked):
        self.toggle.setChecked(checked)
    
    def isChecked(self):
        return self.toggle.isChecked()
    
    def setText(self, text):
        self.label.setText(text)
    
    def text(self):
        return self.label.text()
    
    def toggle(self):
        self.toggle.toggle()
    
    def set_primary_color(self, hex_color):
        self.toggle.set_primary_color(hex_color)