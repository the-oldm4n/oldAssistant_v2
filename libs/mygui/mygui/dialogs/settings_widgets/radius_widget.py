import json
import os
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QMessageBox, QScrollArea, QSizePolicy, QGridLayout, QSlider, QSpinBox
from PySide6.QtCore import Signal, Qt

from mygui.config import mygui_config
from mygui.dialogs.edit_dialog import EditDialog
from mygui.preview.gradient_preview import GradientPreview
from mygui.widgets.custom_toggle import CustomToggle


class RadiusWidget(QWidget):
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

        title_label = QLabel("Радиус кнопок и окон")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background-color: transparent; font-size: 18px;")
        layout.addWidget(title_label)

            # === Радиус кнопок ===
        btn_radius_layout = QHBoxLayout()
        btn_radius_label = QLabel("Радиус кнопок (px):")
        btn_radius_label.setStyleSheet("background: transparent")
        
        self.btn_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.btn_radius_slider.setStyleSheet("background: transparent")
        self.btn_radius_slider.setRange(0, 15)
        self.btn_radius_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.btn_radius_slider.setTickInterval(1)
        self.btn_radius_slider.valueChanged.connect(self.on_btn_radius_changed)
        
        self.btn_radius_value_label = QLabel("0")
        self.btn_radius_value_label.setObjectName("LabelSliderValue")
        self.btn_radius_value_label.setFixedWidth(25)
        self.btn_radius_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_radius_layout.addWidget(btn_radius_label)
        btn_radius_layout.addWidget(self.btn_radius_slider)
        btn_radius_layout.addWidget(self.btn_radius_value_label)
        layout.addLayout(btn_radius_layout)

        # === Радиус главного окна ===
        main_radius_layout = QHBoxLayout()
        main_radius_label = QLabel("Радиус главного окна (px):")
        main_radius_label.setStyleSheet("background: transparent")
        
        self.main_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.main_radius_slider.setStyleSheet("background: transparent")
        self.main_radius_slider.setRange(0, 20)
        self.main_radius_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.main_radius_slider.setTickInterval(1)
        self.main_radius_slider.valueChanged.connect(self.on_main_radius_changed)
        
        self.main_radius_value_label = QLabel("0")
        self.main_radius_value_label.setObjectName("LabelSliderValue")
        self.main_radius_value_label.setFixedWidth(25)
        self.main_radius_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_radius_layout.addWidget(main_radius_label)
        main_radius_layout.addWidget(self.main_radius_slider)
        main_radius_layout.addWidget(self.main_radius_value_label)
        layout.addLayout(main_radius_layout)

        # === Бордер у главного окна ===
        self.main_border_checkbox = CustomToggle("Показывать бордер у главного окна")
        self.main_border_checkbox.setStyleSheet("background: transparent")
        self.main_border_checkbox.setChecked(self.parent.border_in_main_window)
        self.main_border_checkbox.stateChanged.connect(self.on_border_state_changed)
        layout.addWidget(self.main_border_checkbox)

        layout.addStretch()

    def on_btn_radius_changed(self, value):
        """Обработчик изменения радиуса кнопок"""
        self.btn_radius_value_label.setText(str(value))
        self.parent.border_btn_radius = str(value)
        self.parent.apply_changes(preview=True)

    def on_main_radius_changed(self, value):
        """Обработчик изменения радиуса главного окна"""
        self.main_radius_value_label.setText(str(value))
        self.parent.border_main_radius = str(value)
        self.parent.apply_changes(preview=True)

    def on_border_state_changed(self):
        """Обновляет внутренние переменные и применяет превью"""
        self.parent.border_in_main_window = self.main_border_checkbox.isChecked()
        self.parent.apply_changes(preview=True)

    def set_values(self):
        if hasattr(self, 'btn_radius_slider'):
            self.btn_radius_slider.setValue(self.parent.border_btn_radius)
            self.btn_radius_value_label.setText(str(self.parent.border_btn_radius))
            
        if hasattr(self, 'main_radius_slider'):
            self.main_radius_slider.setValue(self.parent.border_main_radius)
            self.main_radius_value_label.setText(str(self.parent.border_main_radius))