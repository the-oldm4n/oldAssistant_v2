"""Виджет для отображения версии"""
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from mygui.core.apply_color import main_apply_colors
from mygui.core.signals import color_signal

class VersionLabel(QWidget):
    def __init__(self, parent=None, version="1.0.0"):
        super().__init__(parent)
        self.version = version
        
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        color_signal.color_changed.connect(self.apply_color)
        self.init_ui()
        self.apply_color()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(f"{self.version}")
        label.setObjectName("VersionLabel")
        layout.addWidget(label)
        
    def apply_color(self):
        self.styles = self.style_manager.load_styles()

        style_sheet = ""
        for widget, styles in self.styles.items():
            if widget.startswith("Q"):
                selector = widget
            else:
                selector = f"#{widget}"

            style_sheet += f"{selector} {{\n"
            for prop, value in styles.items():
                style_sheet += f"    {prop}: {value};\n"
            style_sheet += "}\n"

        self.setStyleSheet(style_sheet)