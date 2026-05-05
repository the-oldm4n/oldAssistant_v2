import json
import os
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QMessageBox, QScrollArea, QSizePolicy, QGridLayout, QSlider, QSpinBox
from PySide6.QtCore import Signal, Qt, QPoint

from mygui.config import mygui_config
from mygui.dialogs.color_picker import SimpleColorPicker
from mygui.dialogs.edit_dialog import EditDialog
from mygui.preview.gradient_preview import GradientPreview
from mygui.widgets.custom_toggle import CustomToggle


class TextWidget(QWidget):
    """

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("StackedWidgetPage")
        self.init_ui()

    def init_ui(self):
        content_widget = QWidget()
        content_widget.setObjectName("StackedWidgetContent")
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        title_label = QLabel("Текст на кнопках и в поле ввода")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background-color: transparent; font-size: 18px;")
        layout.addWidget(title_label)

        text_color_layout = QHBoxLayout()
        text_color_label = QLabel('Цвет текста:')
        text_color_label.setStyleSheet("background: transparent")
        
        self.text_color_preview = QLabel()
        self.text_color_preview.setFixedSize(30, 30)
        self.text_color_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.text_color_preview.mousePressEvent = lambda event: self.choose_text_color()
        self.text_color_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        text_edit_color_layout = QHBoxLayout()
        
        text_edit_label = QLabel('Цвет текста в поле ввода')
        text_edit_label.setStyleSheet("background: transparent")
        
        self.text_edit_preview = QLabel()
        self.text_edit_preview.setFixedSize(30, 30)
        self.text_edit_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.text_edit_preview.mousePressEvent = lambda event: self.parent.choose_text_edit_color()
        self.text_edit_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        text_color_layout.addWidget(text_color_label)
        text_color_layout.addWidget(self.text_color_preview)
        text_color_layout.addStretch()
        text_edit_color_layout.addWidget(text_edit_label)
        text_edit_color_layout.addWidget(self.text_edit_preview)
        text_edit_color_layout.addStretch()
        
        layout.addLayout(text_color_layout)
        layout.addLayout(text_edit_color_layout)

        preview_layout = QVBoxLayout()

        # Превью текста в логах       
        self.log_demo = QLabel("Это пример текста в поле ввода")
        self.log_demo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_demo.setMinimumHeight(40)
        self.log_demo.setStyleSheet("""
            background: #1a1a1a; 
            border: 1px solid #333; 
            border-radius: 5px; 
            padding: 5px;
            font-family: 'Courier New', monospace;
        """)
        preview_layout.addWidget(self.log_demo)

        layout.addLayout(preview_layout)

        layout.addStretch()

    def choose_text_color(self):
        """Показывает пикер цвета для текста"""
        preview_pos = self.text_color_preview.mapToGlobal(QPoint(5, 5))
        picker = SimpleColorPicker(self.parent.text_color, self)
        picker.move(preview_pos.x() + self.text_color_preview.width(), preview_pos.y())
        picker.color_changed.connect(self.on_text_color_changed)
        picker.focusOutEvent = lambda event: picker.close()
        picker.exec()
        
    def on_text_color_changed(self, color):
        """Обработчик изменения цвета текста"""
        self.parent.text_color = color
        self.update_color_previews()
        self.parent.apply_changes(preview=True)
    
    def on_text_edit_color_changed(self, color):
        """Обработчик изменения цвета текста в логах"""
        self.parent.text_edit_color = color
        self.update_color_previews()
        self.parent.apply_changes(preview=True)
    
    def choose_text_edit_color(self):
        preview_pos = self.text_edit_preview.mapToGlobal(QPoint(5, 5))
        picker = SimpleColorPicker(self.parent.text_edit_color, self)
        picker.move(preview_pos.x() + self.text_edit_preview.width(), preview_pos.y())
        picker.color_changed.connect(self.on_text_edit_color_changed)
        picker.focusOutEvent = lambda event: picker.close()
        picker.exec()

    def update_color_previews(self):
        """Обновляет цвет превью-лейблов"""
        # Превью для основного текста
        self.text_color_preview.setStyleSheet(
            f"background-color: {self.parent.text_color}; border: 1px solid #ccc; border-radius: 3px;"
        )
        
        # Превью для текста в логах
        self.text_edit_preview.setStyleSheet(
            f"background-color: {self.parent.text_edit_color}; border: 1px solid #ccc; border-radius: 3px;"
        )
       
        # Демо текста в логах
        self.log_demo.setStyleSheet(f"""
            background: #1a1a1a; 
            border: 1px solid #333; 
            border-radius: 5px; 
            padding: 5px;
            font-family: 'Consolas', monospace;
            color: {self.parent.text_edit_color};
        """)