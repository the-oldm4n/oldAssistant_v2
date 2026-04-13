import os
import re
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QFrame, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import Signal, QPropertyAnimation, Qt, QRectF, QPointF, QEasingCurve,\
    Property, QParallelAnimationGroup, QAbstractAnimation
from PySide6.QtGui import QColor, QCursor, QBrush, QPen, QLinearGradient, QPainter,\
    QPainterPath, QRadialGradient
from mygui import main_apply_colors, color_signal
from log_config import debuglog


class _CustomToggleSimple(QWidget):
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

        self.morph_animation = QPropertyAnimation(self, b"morph_progress")
        self.morph_animation.setDuration(400)
        self.morph_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.setFixedSize(36, 12)
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
        
        self.morph_animation.setStartValue(self._morph_progress)
        self.morph_animation.setEndValue(1.0 if self._checked else 0.0)
        
        self.morph_animation.start()
    
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
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Фоновая дорожка - полупрозрачный серый
        bg_rect = QRectF(1, 1, width - 2, height - 2)
        painter.setBrush(QColor(100, 100, 100, 60))  # Полупрозрачный серый (альфа=60)
        painter.setPen(QPen(self.borger_color, 1))
        painter.drawRoundedRect(bg_rect, (height - 2) / 2, (height - 2) / 2)
        
        # Активная дорожка
        if self._morph_progress > 0:
            active_width = (width - 2) * self._morph_progress
            
            # Определяем brush
            if hasattr(self, '_gradient_colors') and self._gradient_colors:
                gradient = QLinearGradient(1, 1, active_width, height - 2)
                for i, color in enumerate(self._gradient_colors):
                    gradient.setColorAt(i / (len(self._gradient_colors) - 1), color)
                brush = QBrush(gradient)
            else:
                active_color = self.bg_color
                active_color.setAlpha(220)
                brush = QBrush(active_color)
            
            # Рисуем активную часть поверх фона
            active_rect = QRectF(1, 1, active_width, height - 2)
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(active_rect, (height - 2) / 2, (height - 2) / 2)
 
 
class CustomToggleSimple(QWidget):
    stateChanged = Signal(int)
    toggled = Signal(bool)
    
    def __init__(self, text="", parent=None, checked=False, color="#4686FD"):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Тогл
        self.toggle = _CustomToggleSimple(self, checked, color)
        self.toggle.stateChanged.connect(self.stateChanged)
        self.toggle.toggled.connect(self.toggled)
        layout.addWidget(self.toggle)
        
        # Лейбл
        if text:
            self.label = QLabel(text)
            self.label.setStyleSheet("background: transparent;")
            self.label.setCursor(Qt.PointingHandCursor)
            self.label.mousePressEvent = self._on_label_click
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