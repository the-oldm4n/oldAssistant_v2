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


class BackgroundWidget(QWidget):
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title_label = QLabel("Задний фон")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background-color: transparent; font-size: 18px;")
        layout.addWidget(title_label)

        checkbox = CustomToggle(f'Использовать градиент для фона')
        checkbox.setStyleSheet("background-color: transparent")
        checkbox.stateChanged.connect(lambda state: self.parent.toggle_gradient("background", state))
        layout.addWidget(checkbox)
        
        solid_color_container = QWidget()
        solid_color_container.setStyleSheet("background-color: transparent")
        solid_color_layout = QHBoxLayout(solid_color_container)
        solid_color_layout.setContentsMargins(0, 0, 0, 0)

        solid_color_label = QLabel("Текущий цвет:")
        solid_color_label.setStyleSheet("background-color: transparent")
        solid_color_layout.addWidget(solid_color_label)
        
        solid_color_preview = QLabel()
        solid_color_preview.setFixedSize(30, 30)
        solid_color_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        solid_color_preview.mousePressEvent = lambda event: self.parent.choose_solid_color("background")
        solid_color_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        solid_color_layout.addWidget(solid_color_preview)
        solid_color_layout.addStretch()
        
        layout.addWidget(solid_color_container)

        # Контейнер для элементов градиента (скрывается при отключении)
        gradient_group = QWidget()
        gradient_group.setObjectName("GradientGroup")
        gradient_layout = QVBoxLayout(gradient_group)
        gradient_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопки выбора цветов
        two_colors_layout = QHBoxLayout()
        
        color1_layout = QHBoxLayout()
        color1_label = QLabel("Цвет 1:")
        color1_label.setStyleSheet("background-color: transparent")
        color1_layout.addWidget(color1_label)
        
        self.color1_preview = QLabel()
        self.color1_preview.setFixedSize(30, 30)
        self.color1_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.color1_preview.mousePressEvent = lambda event: self.parent.choose_gradient_color("background", 1)
        self.color1_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        color1_layout.addWidget(self.color1_preview)
        color1_layout.addStretch()
        
        color2_layout = QHBoxLayout()
        color2_label = QLabel("Цвет 2:")
        color2_label.setStyleSheet("background-color: transparent")
        color2_layout.addWidget(color2_label)
        
        self.color2_preview = QLabel()
        self.color2_preview.setFixedSize(30, 30)
        self.color2_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.color2_preview.mousePressEvent = lambda event: self.parent.choose_gradient_color("background", 2)
        self.color2_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        color2_layout.addWidget(self.color2_preview)
        color2_layout.addStretch()
        
        two_colors_layout.addLayout(color1_layout)
        two_colors_layout.addLayout(color2_layout)
        
        gradient_layout.addLayout(two_colors_layout)

        # Управление углом
        angle_label = QLabel(f'Угол градиента (0-360°):')
        angle_label.setStyleSheet("background: transparent")
        gradient_layout.addWidget(angle_label)
        angle_slider = QSlider(Qt.Orientation.Horizontal)
        angle_slider.setStyleSheet("background: transparent")
        angle_slider.setRange(0, 360)
        angle_slider.setTickInterval(45)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        angle_slider.valueChanged.connect(lambda angle: self.parent.update_gradient_angle("background", angle))
        gradient_layout.addWidget(angle_slider)
        angle_spin = QSpinBox()
        angle_spin.setStyleSheet("background: transparent")
        angle_spin.setRange(0, 360)
        angle_spin.setSuffix('°')
        angle_spin.valueChanged.connect(lambda angle: self.parent.update_gradient_angle("background", angle))
        gradient_layout.addWidget(angle_spin)

        # Связываем слайдер и спинбокс
        angle_slider.valueChanged.connect(angle_spin.setValue)
        angle_spin.valueChanged.connect(angle_slider.setValue)

        layout.addWidget(gradient_group)  # Добавляем группу в основной layout

        # Превью градиента
        preview = GradientPreview()
        layout.addWidget(preview)

        # if "background" == "buttons":
        #     self.buttons_border_checkbox = CustomToggle("Показывать бордер у кнопок")
        #     self.buttons_border_checkbox.setStyleSheet("background: transparent")
        #     self.buttons_border_checkbox.setChecked(self.border_in_buttons)
        #     self.buttons_border_checkbox.stateChanged.connect(self.on_border_btn_state_changed)
        #     layout.addWidget(self.buttons_border_checkbox)

        layout.addStretch()

        # Сохраняем ссылки на элементы для обновления
        self.parent.gradient_settings["background"]['widgets'] = {
            'checkbox': checkbox,
            'solid_color_container': solid_color_container,
            'color1_preview': self.color1_preview,
            'color2_preview': self.color2_preview,
            'solid_color_preview': solid_color_preview,
            'gradient_group': gradient_group,
            'slider': angle_slider,
            'spinbox': angle_spin,
            'preview': preview
        }

        # Инициализируем состояние
        self.parent.toggle_gradient("background", checkbox.isChecked())