from PySide6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QWidget, QSlider
from PySide6.QtCore import Qt

from mygui.core.signals import sidebar_animated_signal
from mygui.config import mygui_config


class OtherSettingsWidget(QWidget):
    """

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("StackedWidgetPage")
        self.init_ui()
        self.set_values()

    def init_ui(self):
        content_widget = QWidget()
        content_widget.setObjectName("StackedWidgetContent")
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        title_label = QLabel("Прочие настройки")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background-color: transparent; font-size: 18px;")
        layout.addWidget(title_label)

        sidebar_delay_layout = QHBoxLayout()
        sidebar_delay_label = QLabel("Задержка перед анимацией сайдбара (мс):")
        sidebar_delay_label.setStyleSheet("background: transparent")
        
        self.sidebar_delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.sidebar_delay_slider.setSingleStep(50)
        self.sidebar_delay_slider.setPageStep(50)
        self.sidebar_delay_slider.setStyleSheet("background: transparent")
        self.sidebar_delay_slider.setRange(50, 2000)
        self.sidebar_delay_slider.valueChanged.connect(self.on_delay_changed)
        
        self.sidebar_delay_label = QLabel("50")
        self.sidebar_delay_label.setObjectName("LabelSliderValue")
        self.sidebar_delay_label.setFixedWidth(50)
        self.sidebar_delay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(sidebar_delay_label)
        sidebar_delay_layout.addWidget(self.sidebar_delay_slider)
        sidebar_delay_layout.addWidget(self.sidebar_delay_label)
        layout.addLayout(sidebar_delay_layout)

        layout.addStretch()

    def on_delay_changed(self, value):
        """Обработчик изменения задержки анимации"""
        self.sidebar_delay_label.setText(str(value))
        mygui_config.update(property_name="sidebar_delay", value=value)
        sidebar_animated_signal.update_delay.emit(value)

    def set_values(self):
        delay = mygui_config.sidebar_delay
        if hasattr(self, 'sidebar_delay_label'):
            self.sidebar_delay_label.setText(str(delay))

        if hasattr(self, 'sidebar_delay_slider'):
            self.sidebar_delay_slider.setValue(delay)
