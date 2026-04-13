"""Простой пикер цвета"""
import os
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QImage
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame, QWidget

from mygui.paths import ICONS


class SimpleColorPicker(QDialog):
    color_changed = Signal(str)
    def __init__(self, initial_color="#FF0000", parent=None):
        super().__init__(parent)
        self.icon_close_path = os.path.join(ICONS, "close.svg")
        self.color = QColor(initial_color)
        self.setup_ui()
        self.update_all()
    
    def setup_ui(self):
        self.setObjectName("WindowContainer")
        self.setWindowTitle("Выбор цвета")
        self.setFixedSize(280, 270)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)

        layout = QVBoxLayout(self)

        self.setup_color_picker(layout)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(30)
        self.color_preview.setFixedWidth(100)
        self.color_preview.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid #ccc;")

        hex_layout = QHBoxLayout()
        hex_layout.addStretch()
        self.hex_edit = QLineEdit()
        self.hex_edit.textEdited.connect(self.on_hex_changed)
        hex_layout.addWidget(self.hex_edit)
        hex_layout.addWidget(self.color_preview)
        layout.addLayout(hex_layout)

        layout.addStretch()
        
    def set_color(self, color):
        """Установить цвет и обновить все элементы"""
        self.color = color
        self.update_all()
        
    def on_hex_changed(self, text):
        """При изменении HEX"""
        if QColor.isValidColor(text):
            self.color = QColor(text)
            self.update_all()
            self.color_changed.emit(self.color.name())
        
    def on_sv_changed(self, s, v):
        """При изменении Saturation/Value в палитре"""
        h = self.color.hue()
        self.color.setHsv(h, s, v)
        self.update_all()
        self.color_changed.emit(self.color.name())
        
    def on_hs_changed(self, h, s):
        """При изменении Hue/Saturation в палитре"""
        current_v = self.color.value()
        
        # ЕСЛИ НАСЫЩЕННОСТЬ МЕНЬШЕ 2 - ДЕЛАЕМ ЧИСТЫЙ БЕЛЫЙ/СЕРЫЙ
        if s < 2:
            self.color.setHsv(h, 0, current_v)
        else:
            self.color.setHsv(h, s, current_v)
        
        # Обновляем градиент Value ползунка
        if hasattr(self, 'value_slider'):
            self.value_slider.set_base_color(h, s)
        
        self.update_all()
        self.color_changed.emit(self.color.name())


    def on_hue_changed(self, h):
        """При изменении Hue в полосе"""
        s = self.color.saturation()
        v = self.color.value()
        self.color.setHsv(h, s, v)
        
        # Обновляем палитру S/V с новым Hue
        if hasattr(self, 'sv_palette'):
            self.sv_palette.set_hue(h)
        
        self.update_all()
        self.color_changed.emit(self.color.name())

    def on_value_changed(self, v):
        """При изменении Value в ползунке"""
        h = self.color.hue()
        s = self.color.saturation()
        self.color.setHsv(h, s, v)
        self.update_all()
        self.color_changed.emit(self.color.name())
            
    def update_all(self):
        """Обновить все элементы"""
        self.update_slider_value()
        self.update_preview()
        self.update_hex()
        self.update_palette_from_color()
            
    def update_palette_from_color(self):
        """Обновить палитру из текущего цвета"""
        if hasattr(self, 'hs_palette') and hasattr(self, 'value_slider'):
            h = self.color.hue()
            s = self.color.saturation()
            v = self.color.value()

            self.hs_palette.set_color(h, s)
            self.value_slider.set_base_color(h, s)
            self.value_slider.set_value(v)
        
    def update_slider_value(self):
        """Обновить ползунок value"""
        if hasattr(self, 'value_slider'):
            v = self.color.value()
            self.value_slider.set_value(v)
        
    def update_preview(self):
        """Обновить превью цвета"""
        self.color_preview.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid #ccc;")
        
    def update_hex(self):
        """Обновить HEX поле"""
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(self.color.name())
        self.hex_edit.blockSignals(False)
        
    def get_color(self):
        """Получить выбранный цвет"""
        return self.color.name()
    
    def setup_color_picker(self, layout):
        """Палитра Hue + Saturation + Value"""
        picker_layout = QHBoxLayout()
        
        # 1. Квадратная палитра Hue + Saturation
        self.hs_palette = HSPaletteWidget(self)
        self.hs_palette.color_changed.connect(self.on_hs_changed)
        picker_layout.addWidget(self.hs_palette)
        
        # 2. Вертикальный ползунок Value
        self.value_slider = ValueSliderWidget(self)
        self.value_slider.value_changed.connect(self.on_value_changed)
        picker_layout.addWidget(self.value_slider)
        
        layout.addLayout(picker_layout)
        
class SVPaletteWidget(QFrame):
    """Квадратная палитра Saturation (X) vs Value (Y)"""
    color_changed = Signal(int, int)  # s, v
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.hue = 0
        self.saturation = 255
        self.value = 255
        self.is_dragging = False
        self.cursor_pos = QPoint(199, 199)
        self.cached_image = None
        self.generate_cached_image()

    def set_hue(self, hue):
        """Установить Hue и перегенерировать палитру"""
        self.hue = hue
        self.generate_cached_image()
        self.update()

    def generate_cached_image(self):
        """Создать палитру Saturation (X) vs Value (Y)"""
        self.cached_image = QImage(200, 200, QImage.Format_ARGB32)
        painter = QPainter(self.cached_image)
        
        for y in range(200):
            for x in range(200):
                saturation = int((x / 200.0) * 255)  # X ось = Saturation
                value = int(((200 - y) / 200.0) * 255)  # Y ось = Value (инвертировано)
                
                color = QColor()
                color.setHsv(self.hue, saturation, value)
                painter.setPen(color)
                painter.drawPoint(x, y)
        
        painter.end()

    def set_color(self, s, v):
        """Установить позицию курсора из S/V"""
        x = int((s / 255.0) * 199)
        y = int(199 - (v / 255.0) * 199)  # инвертируем Value
        self.cursor_pos = QPoint(x, y)
        self.update()

    def paintEvent(self, event):  # ← ДОБАВИТЬ ЭТОТ МЕТОД
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.cached_image:
            painter.drawImage(0, 0, self.cached_image)
        
        # Курсор
        painter.setPen(QPen(Qt.white, 2))
        painter.drawEllipse(self.cursor_pos, 4, 4)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(self.cursor_pos, 4, 4)
        painter.end()

    def mousePressEvent(self, event):  # ← ДОБАВИТЬ
        self.is_dragging = True
        self.update_color(event.pos())
        
    def mouseMoveEvent(self, event):  # ← ДОБАВИТЬ
        if self.is_dragging:
            self.update_color(event.pos())
            
    def mouseReleaseEvent(self, event):  # ← ДОБАВИТЬ
        self.is_dragging = False

    def update_color(self, pos):
        x = max(0, min(199, pos.x()))
        y = max(0, min(199, pos.y()))
        self.cursor_pos = QPoint(x, y)
        
        saturation = int((x / 200.0) * 255)
        value = int(((200 - y) / 200.0) * 255)  # инвертируем
        
        self.saturation = saturation
        self.value = value
        self.color_changed.emit(saturation, value)
        self.update()


class HSPaletteWidget(QWidget):
    color_changed = Signal(int, int)  # h, s
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.hue = 0
        self.saturation = 255
        self.is_dragging = False
        self.cursor_pos = QPoint(199, 199)
        self.cached_image = None
        self.generate_cached_image()

    def generate_cached_image(self):
        """Создать кэшированное изображение палитры"""
        self.cached_image = QImage(200, 200, QImage.Format_ARGB32)
        painter = QPainter(self.cached_image)
        
        for y in range(200):
            for x in range(200):
                hue = int((x / 200.0) * 359)
                saturation = int(((200 - y) / 200.0) * 255)
                
                # Value=255 для яркого отображения палитры
                color = QColor()
                color.setHsv(hue, saturation, 255)
                painter.setPen(color)
                painter.drawPoint(x, y)
        
        painter.end()

    def set_color(self, h, s):
        """Установить позицию курсора из H/S"""
        x = int((h / 359.0) * 199)
        y = int(199 - (s / 255.0) * 199)
        self.cursor_pos = QPoint(x, y)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Рисуем кэшированное изображение палитры
        if self.cached_image:
            painter.drawImage(0, 0, self.cached_image)
        
        # Рисуем бордер С ПРАВИЛЬНЫМИ КООРДИНАТАМИ
        painter.setPen(QPen(QColor("#cccccc"), 2))
        painter.setBrush(Qt.NoBrush)
        # Смещаем на 1px внутрь чтобы перо не выходило за границы
        painter.drawRect(1, 1, self.width()-2, self.height()-2)
        
        # Курсор поверх всего
        painter.setPen(QPen(Qt.white, 2))
        painter.drawEllipse(self.cursor_pos, 4, 4)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(self.cursor_pos, 4, 4)
        
        painter.end()

    def mousePressEvent(self, event):
        self.is_dragging = True
        self.update_color(event.pos())
        
    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.update_color(event.pos())
            
    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    def update_color(self, pos):
        x = max(0, min(199, pos.x()))
        y = max(0, min(199, pos.y()))

        self.cursor_pos = QPoint(x, y)
        hue = int((x / 200.0) * 359)
        saturation = int(((200 - y) / 200.0) * 255)
        
        self.hue = hue
        self.saturation = saturation
        self.color_changed.emit(hue, saturation)
        self.update()

class ValueSliderWidget(QWidget):
    value_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 200)
        self.value = 255
        self.is_dragging = False
        self.cursor_y = 0
        self.base_hue = 0
        self.base_saturation = 255
        self.cached_images = {}  # Кэш для разных цветов
        
    def set_base_color(self, h, s):
        """Установить базовый цвет для градиента Value"""
        self.base_hue = h
        self.base_saturation = s
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Создаем ключ кэша
        cache_key = f"{self.base_hue}_{self.base_saturation}"
        
        # Используем кэш или создаем новое изображение
        if cache_key not in self.cached_images:
            self.generate_cached_image(cache_key)
        
        # Рисуем кэшированное изображение
        painter.drawImage(0, 0, self.cached_images[cache_key])
        
        # Рисуем бордер
        painter.setPen(QPen(QColor("#cccccc"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(1, 1, self.width()-2, self.height()-2)
        
        # Курсор поверх всего
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, self.cursor_y - 2, 30, 4)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawRect(1, self.cursor_y - 1, 28, 2)
        
        painter.end()

    def generate_cached_image(self, cache_key):
        """Создать кэшированное изображение градиента"""
        image = QImage(30, 200, QImage.Format_ARGB32)
        painter = QPainter(image)
        
        for y in range(200):
            value = int(((200 - y) / 200.0) * 255)
            color = QColor()
            color.setHsv(self.base_hue, self.base_saturation, value)
            painter.setPen(color)
            painter.drawLine(0, y, 30, y)
        
        painter.end()
        self.cached_images[cache_key] = image

    def set_value(self, value):
        """Установить позицию курсора из Value"""
        self.cursor_y = int(199 - (value / 255.0) * 199)
        self.value = value
        self.update()

    def mousePressEvent(self, event):
        self.is_dragging = True
        self.update_value(event.pos())
        
    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.update_value(event.pos())
            
    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    def update_value(self, pos):
        y = max(0, min(199, pos.y()))
        self.cursor_y = y
        self.value = int(((199 - y) / 199.0) * 255)
        self.value_changed.emit(self.value)
        self.update()