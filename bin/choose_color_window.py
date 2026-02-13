import json
import math
import os
import re
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPainterPath, QCursor, QPen, QImage
from PySide6.QtWidgets import QLabel, QVBoxLayout, QPushButton, QSpinBox, QSlider, QDialog, QWidget, QTabWidget, \
    QHBoxLayout, QComboBox, QApplication, QLineEdit, QFrame
from bin.apply_color_methods import main_apply_colors
from bin.custom_svg_widget import CustomSvgWidget
from bin.custom_widgets import CustomToggle
from bin.signals import color_signal, update_presets_signal
from logging_config import debug_logger
from path_builder import get_path


class ColorSettingsWindow(QDialog):
    """Окно изменения оформления интерфейса с поддержкой градиентов"""

    colorChanged = Signal()  # Сигнал изменения цвета

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.color_settings_path = self.assistant.color_path
        self.base_presets = get_path("bin", 'color_presets')
        self.custom_presets = get_path('user_settings', 'presets')
        os.makedirs(self.custom_presets, exist_ok=True)

        # Настройка окна без рамки
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(450, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Инициализация переменных для цветов и прочего
        self.bg_color = ""
        self.btn_color = ""
        self.text_color = ""
        self.text_edit_color = ""
        self.border_color = ""
        self.svg_color = ""
        self.border_btn_radius = None
        self.border_main_radius = None
        self.border_in_main_window = False
        self.border_in_buttons = False

        # Настройки градиентов
        self.gradient_settings = {
            'background': {
                'enabled': False,
                'solid_color': "#000000",
                'color1': "",
                'color2': "",
                'angle': 0,
                'widgets': {}  # Будет заполнено в init_ui
            },
            'buttons': {
                'enabled': False,
                'color1': "",
                'color2': "",
                'angle': 0,
                'widgets': {}
            },
            'borders': {
                'enabled': False,
                'color1': "",
                'color2': "",
                'angle': 0,
                'widgets': {}
            },
            'svg': {
                'enabled': False,
                'color1': "",
                'color2': "",
                'angle': 0,
                'widgets': {}
            }
        }

        self.init_ui()
        self.load_color_settings()
        self.apply_styles()
        
    # def __setattr__(self, name, value):
    #     if name in ['border_btn_radius', 'border_main_radius']:
    #         old_value = getattr(self, name, 'NOT_SET')
    #         print(f"🚨 ПЕРЕЗАПИСЬ {name}: {old_value} -> {value} (тип: {type(value)})")
    #         import traceback
    #         traceback.print_stack(limit=10)
    #     super().__setattr__(name, value)

    def apply_styles(self):
        """Применяет все стили к окну"""
        try:
            self.styles = self.style_manager.load_styles()
            
            if hasattr(self, 'info_svg'):
                self.style_manager.apply_color_svg(self.info_svg)

            if hasattr(self, 'title_bar'):
                self.title_bar.setObjectName("TitleBar")
            if hasattr(self, 'content_widget'):
                self.content_widget.setObjectName("ContentWidget")
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
        except Exception as e:
            debug_logger.error(f"[COLORSET] Ошибка в методе apply_styles: {e}")

    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            # Получаем новую позицию основного окна
            new_pos = event.globalPos() - self.drag_pos
            self.move(new_pos)

            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()
        
    def open_info(self):
        video_path = get_path("bin", "guides", "styles_panel.mp4")
        self.assistant.open_video(video_path)

    def init_ui(self):
        # Основной контейнер
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        self.container.setGeometry(0, 0, self.width(), self.height())

        # Кастомный заголовок
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setGeometry(1, 1, self.width() - 2, 35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 5, 10, 5)
        self.title_layout.setSpacing(5)

        self.title_bar.mousePressEvent = self.title_bar_mouse_press
        self.title_bar.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar.mouseReleaseEvent = self.title_bar_mouse_release

        self.title_label = QLabel("Редактор стилей", self.title_bar)
        self.title_label.setStyleSheet("background: transparent")
        self.title_layout.addWidget(self.title_label)
        
        self.info_btn = QPushButton("", self.title_bar)
        self.info_btn.setFixedSize(30, 30)
        self.info_btn.clicked.connect(self.open_info)
        self.info_svg = CustomSvgWidget(self.assistant.icon_guide_path, self.info_btn)
        self.info_svg.setFixedSize(20, 20)
        self.info_svg.move(5, 5)
        self.info_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.info_btn)

        self.close_btn = QPushButton("", self.title_bar)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.assistant.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)

        # Основной контент
        self.content_widget = QWidget(self.container)
        self.content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)
        self.content_widget.setObjectName("ContentWidget")

        # Главный layout для content_widget
        self.main_content_layout = QVBoxLayout(self.content_widget)
        self.main_content_layout.setContentsMargins(5, 5, 5, 5)
        self.main_content_layout.setSpacing(5)

        # Контейнер для вкладок и связанных элементов
        self.tabs_container = QWidget()
        self.tabs_container.setObjectName("WSTabsContainer")
        self.tabs_layout = QVBoxLayout(self.tabs_container)
        self.tabs_layout.setContentsMargins(5, 5, 5, 5)
        self.tabs_layout.setSpacing(0)

        # Создаем вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("TabWidget")

        # Вкладки
        self.bg_tab = QWidget()
        self.bg_tab.setObjectName("WSBgTabWidget")
        self.init_gradient_tab(self.bg_tab, 'background', 'Фон')

        self.text_tab = QWidget()
        self.add_text_color_section(self.text_tab)

        self.btn_tab = QWidget()
        self.init_gradient_tab(self.btn_tab, 'buttons', 'Кнопки')

        self.border_tab = QWidget()
        self.init_gradient_tab(self.border_tab, 'borders', 'Обводки')
        
        self.radius_tab = QWidget()
        self.change_radius_tab(self.radius_tab)

        self.svg_tab = QWidget()
        self.init_svg_tab(self.svg_tab, 'svg', 'Иконки')

        self.tab_widget.addTab(self.bg_tab, "Фон")
        self.tab_widget.addTab(self.text_tab, "Текст")
        self.tab_widget.addTab(self.btn_tab, "Кнопки")
        self.tab_widget.addTab(self.border_tab, "Обводки")
        self.tab_widget.addTab(self.radius_tab, "Радиус обводки")
        self.tab_widget.addTab(self.svg_tab, "Иконки")

        self.tabs_layout.addWidget(self.tab_widget)

        # Контейнер для нижних элементов
        self.bottom_container = QWidget()
        self.bottom_container.setObjectName("WSBottomContainer")
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(10, 10, 10, 10)
        self.bottom_layout.setSpacing(8)

        # Нижние элементы
        self.save_preset_button = QPushButton('Сохранить стиль')
        self.save_preset_button.clicked.connect(self.save_preset)

        self.styles_label = QLabel('Стили:')
        self.styles_label.setStyleSheet("background: transparent")

        self.preset_combo_box = QComboBox()
        self.load_presets()
        self.preset_combo_box.setCurrentIndex(0)
        self.preset_combo_box.currentIndexChanged.connect(self.load_preset)

        self.apply_button = QPushButton('Применить')
        self.apply_button.clicked.connect(lambda: self.apply_changes(preview=False))

        # Добавляем элементы в нижний контейнер
        self.bottom_layout.addWidget(self.save_preset_button)
        self.bottom_layout.addWidget(self.styles_label)
        self.bottom_layout.addWidget(self.preset_combo_box)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.apply_button)

        # Добавляем основные части в главный layout
        self.main_content_layout.addWidget(self.tabs_container)
        self.main_content_layout.addWidget(self.bottom_container)

    def init_gradient_tab(self, tab, element_type, title):
        """Инициализирует вкладку для настройки градиента конкретного элемента"""
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Чекбокс для включения градиента
        checkbox = CustomToggle(f'Использовать градиент для {title.lower()}')
        checkbox.setStyleSheet("background-color: transparent")
        checkbox.stateChanged.connect(lambda state: self.toggle_gradient(element_type, state))
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
        solid_color_preview.mousePressEvent = lambda event: self.choose_solid_color(element_type)
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
        self.color1_preview.mousePressEvent = lambda event: self.choose_gradient_color(element_type, 1)
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
        self.color2_preview.mousePressEvent = lambda event: self.choose_gradient_color(element_type, 2)
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
        angle_slider.valueChanged.connect(lambda angle: self.update_gradient_angle(element_type, angle))
        gradient_layout.addWidget(angle_slider)
        angle_spin = QSpinBox()
        angle_spin.setStyleSheet("background: transparent")
        angle_spin.setRange(0, 360)
        angle_spin.setSuffix('°')
        angle_spin.valueChanged.connect(lambda angle: self.update_gradient_angle(element_type, angle))
        gradient_layout.addWidget(angle_spin)

        # Связываем слайдер и спинбокс
        angle_slider.valueChanged.connect(angle_spin.setValue)
        angle_spin.valueChanged.connect(angle_slider.setValue)

        layout.addWidget(gradient_group)  # Добавляем группу в основной layout

        # Превью градиента
        preview = GradientPreview()
        layout.addWidget(preview)

        if element_type == "buttons":
            self.buttons_border_checkbox = CustomToggle("Показывать бордер у кнопок")
            self.buttons_border_checkbox.setStyleSheet("background: transparent")
            self.buttons_border_checkbox.setChecked(self.border_in_buttons)
            self.buttons_border_checkbox.stateChanged.connect(self.on_border_btn_state_changed)
            layout.addWidget(self.buttons_border_checkbox)

        layout.addStretch()

        # Сохраняем ссылки на элементы для обновления
        self.gradient_settings[element_type]['widgets'] = {
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
        self.toggle_gradient(element_type, checkbox.isChecked())

    def init_svg_tab(self, tab, element_type, title):
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Чекбокс для включения градиента
        checkbox = CustomToggle(f'Использовать градиент для {title.lower()}')
        checkbox.setStyleSheet("background-color: transparent")
        checkbox.stateChanged.connect(lambda state: self.toggle_gradient(element_type, state))
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
        solid_color_preview.mousePressEvent = lambda event: self.choose_solid_color(element_type)
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
        self.color1_preview.mousePressEvent = lambda event: self.choose_gradient_color(element_type, 1)
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
        self.color2_preview.mousePressEvent = lambda event: self.choose_gradient_color(element_type, 2)
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
        angle_slider.valueChanged.connect(lambda angle: self.update_gradient_angle(element_type, angle))
        gradient_layout.addWidget(angle_slider)
        angle_spin = QSpinBox()
        angle_spin.setStyleSheet("background: transparent")
        angle_spin.setRange(0, 360)
        angle_spin.setSuffix('°')
        angle_spin.valueChanged.connect(lambda angle: self.update_gradient_angle(element_type, angle))
        gradient_layout.addWidget(angle_spin)

        # Связываем слайдер и спинбокс
        angle_slider.valueChanged.connect(angle_spin.setValue)
        angle_spin.valueChanged.connect(angle_slider.setValue)

        layout.addWidget(gradient_group)

        # Превью
        preview = GradientPreview()
        layout.addWidget(preview)

        layout.addStretch()

        # Сохраняем ссылки на элементы для обновления
        self.gradient_settings[element_type]['widgets'] = {
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
        self.toggle_gradient(element_type, checkbox.isChecked())
        
    def change_radius_tab(self, tab):
        """Добавляет секцию настроек радиуса"""
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

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
        self.main_border_checkbox.setChecked(self.border_in_main_window)
        self.main_border_checkbox.stateChanged.connect(self.on_border_state_changed)
        layout.addWidget(self.main_border_checkbox)

        layout.addStretch()
        
    def on_btn_radius_changed(self, value):
        """Обработчик изменения радиуса кнопок"""
        self.btn_radius_value_label.setText(str(value))
        self.border_btn_radius = str(value)
        self.apply_changes(preview=True)

    def on_main_radius_changed(self, value):
        """Обработчик изменения радиуса главного окна"""
        self.main_radius_value_label.setText(str(value))
        self.border_main_radius = str(value)
        self.apply_changes(preview=True)
        
    def on_border_state_changed(self):
        """Обновляет внутренние переменные и применяет превью"""
        self.border_in_main_window = self.main_border_checkbox.isChecked()
        self.apply_changes(preview=True)

    def on_border_btn_state_changed(self):
        """Обновляет внутренние переменные и применяет превью"""
        self.border_in_buttons = self.buttons_border_checkbox.isChecked()
        self.apply_changes(preview=True)

    def add_text_color_section(self, tab):
        """Добавляет секцию настроек текста"""
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        text_color_layout = QHBoxLayout()
        text_color_label = QLabel('Цвет текста:')
        text_color_label.setStyleSheet("background: transparent")
        
        self.text_color_preview = QLabel()
        self.text_color_preview.setFixedSize(30, 30)
        self.text_color_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.text_color_preview.mousePressEvent = lambda event: self.choose_text_color()
        self.text_color_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        text_edit_color_layout = QHBoxLayout()
        
        text_edit_label = QLabel('Цвет текста в логах и подсказках:')
        text_edit_label.setStyleSheet("background: transparent")
        
        self.text_edit_preview = QLabel()
        self.text_edit_preview.setFixedSize(30, 30)
        self.text_edit_preview.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
        self.text_edit_preview.mousePressEvent = lambda event: self.choose_text_edit_color()
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
        self.log_demo = QLabel("Это пример текста в логах\nОтвет ассистента: Ну привет")
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
        picker = SimpleColorPicker(self.text_color, self)
        picker.move(preview_pos.x() + self.text_color_preview.width(), preview_pos.y())
        picker.color_changed.connect(self.on_text_color_changed)
        picker.focusOutEvent = lambda event: picker.close()
        picker.exec()
        
    def on_text_color_changed(self, color):
        """Обработчик изменения цвета текста"""
        self.text_color = color
        self.update_color_previews()
        self.apply_changes(preview=True)
    
    def on_text_edit_color_changed(self, color):
        """Обработчик изменения цвета текста в логах"""
        self.text_edit_color = color
        self.update_color_previews()
        self.apply_changes(preview=True)
    
    def choose_text_edit_color(self):
        preview_pos = self.text_edit_preview.mapToGlobal(QPoint(5, 5))
        picker = SimpleColorPicker(self.text_edit_color, self)
        picker.move(preview_pos.x() + self.text_edit_preview.width(), preview_pos.y())
        picker.color_changed.connect(self.on_text_edit_color_changed)
        picker.focusOutEvent = lambda event: picker.close()
        picker.exec()
    
    def choose_solid_color(self, element_type):
        """Выбор сплошного цвета (когда градиент выключен)"""
        current_color = self.gradient_settings[element_type].get('solid_color', "#000000")
        
        # Получаем позицию превью для отображения пикера
        widgets = self.gradient_settings[element_type]['widgets']
        preview_pos = widgets['solid_color_preview'].mapToGlobal(QPoint(0, 0))
        
        picker = SimpleColorPicker(current_color, self)
        picker.move(preview_pos.x() + widgets['solid_color_preview'].width(), preview_pos.y())
        picker.color_changed.connect(lambda color: self.on_solid_color_changed(element_type, color))
        picker.focusOutEvent = lambda event: picker.close()
        
        picker.exec()

    def on_solid_color_changed(self, element_type, color):
        """Обработчик изменения сплошного цвета"""
        self.gradient_settings[element_type]['solid_color'] = color

        if element_type == 'background':
            self.bg_color = color
        elif element_type == 'buttons':
            self.btn_color = color
        elif element_type == 'borders':
            self.border_color = color
        elif element_type == 'svg':
            self.svg_color = color

        widgets = self.gradient_settings[element_type]['widgets']
        widgets['solid_color_preview'].setStyleSheet(f"background-color: {color}; border: 1px solid #ccc; border-radius: 3px;")

        self.update_gradient_preview(element_type)
        self.apply_changes(preview=True)
    
    def update_color_previews(self):
        """Обновляет цвет превью-лейблов"""
        # Превью для основного текста
        self.text_color_preview.setStyleSheet(
            f"background-color: {self.text_color}; border: 1px solid #ccc; border-radius: 3px;"
        )
        
        # Превью для текста в логах
        self.text_edit_preview.setStyleSheet(
            f"background-color: {self.text_edit_color}; border: 1px solid #ccc; border-radius: 3px;"
        )
       
        # Демо текста в логах
        self.log_demo.setStyleSheet(f"""
            background: #1a1a1a; 
            border: 1px solid #333; 
            border-radius: 5px; 
            padding: 5px;
            font-family: 'Consolas', monospace;
            color: {self.text_edit_color};
        """)

    def toggle_gradient(self, element_type, state):
        """Включает/выключает градиент для конкретного элемента"""
        from PySide6.QtCore import Qt

        # state может быть: 0, 2, True, False, Qt.CheckState
        if isinstance(state, Qt.CheckState):
            enabled = state == Qt.CheckState.Checked
        elif isinstance(state, int):
            # 0 = Unchecked, 2 = Checked (в PySide6!)
            enabled = state == 2
        else:
            # bool или другие типы
            enabled = bool(state)

        # debug_logger.info(f"🎛️ toggle_gradient: {element_type}, state={state}, type={type(state)}, enabled={enabled}")

        self.gradient_settings[element_type]['enabled'] = enabled

        widgets = self.gradient_settings[element_type]['widgets']

        if enabled:
            # Градиент ВКЛ - скрываем solid, показываем градиент
            widgets['solid_color_container'].setVisible(False)
            widgets['gradient_group'].setVisible(True)
            widgets['preview'].setVisible(True)
        else:
            # Градиент ВЫКЛ - показываем solid, скрываем градиент
            widgets['solid_color_container'].setVisible(True)
            widgets['gradient_group'].setVisible(False)
            widgets['preview'].setVisible(False)

        if enabled and self.gradient_settings[element_type]['color1'] and self.gradient_settings[element_type][
            'color2']:
            self.update_gradient_preview(element_type)

        self.apply_changes(preview=True)
    
    def choose_gradient_color(self, element_type, color_num):
        """Выбор цвета градиента для конкретного элемента"""
        current_color = self.gradient_settings[element_type].get(f'color{color_num}', "#000000")
        
        # Получаем позицию превью для отображения пикера
        widgets = self.gradient_settings[element_type]['widgets']
        preview_widget = widgets[f'color{color_num}_preview']
        preview_pos = preview_widget.mapToGlobal(QPoint(0, 0))
        
        picker = SimpleColorPicker(current_color, self)
        picker.move(preview_pos.x() + preview_widget.width(), preview_pos.y())
        picker.color_changed.connect(lambda color: self.on_gradient_color_changed(element_type, color_num, color))
        picker.focusOutEvent = lambda event: picker.close()
        
        picker.exec()

    def on_gradient_color_changed(self, element_type, color_num, color):
        """Обработчик изменения цвета градиента"""
        self.gradient_settings[element_type][f'color{color_num}'] = color
        widgets = self.gradient_settings[element_type]['widgets']
        preview_widget = widgets[f'color{color_num}_preview']
        preview_widget.setStyleSheet(f"background-color: {color}; border: 1px solid #ccc; border-radius: 3px;")
        self.update_gradient_preview(element_type)
        self.apply_changes(preview=True)

    def update_gradient_angle(self, element_type, angle):
        """Обновляет угол градиента для конкретного элемента"""
        self.gradient_settings[element_type]['angle'] = angle
        self.update_gradient_preview(element_type)
        self.apply_changes(preview=True)

    def update_gradient_preview(self, element_type):
        """Обновляет превью в зависимости от режима"""
        settings = self.gradient_settings[element_type]
        preview = settings['widgets']['preview']

        if settings['enabled']:
            # Режим градиента
            if settings.get('color1') and settings.get('color2'):
                preview.set_gradient(settings['color1'], settings['color2'], settings.get('angle', 0))
            else:
                # Если цвета не заданы, показываем дефолтный градиент
                preview.set_gradient("#000000", "#ffffff", 0)
        else:
            # Режим сплошного цвета - показываем solid color в превью
            color = settings.get('solid_color', "#000000")
            preview.set_gradient(color, color, 0)

    def set_preview_color(self, *colors, angle_degrees: float = 0) -> str:
        """
        Создает строку линейного градиента QSS (Qt Style Sheets) для 1-3 цветов и угла.
        
        Args:
            *colors: От 1 до 3 цветов в формате HEX (например, "#8eacff", "#ff0000")
            angle_degrees (float): Угол градиента в градусах (0-360), по умолчанию 0
        
        Returns:
            str: Строка градиента для использования в QSS
        
        Raises:
            ValueError: Если передано больше 3 цветов или меньше 1 цвета
            
        Examples:
            >>> create_gradient_string("#8eacff", "#7979ff", angle_degrees=0)
            'qlineargradient(x1:0.00, y1:0.50, x2:1.00, y2:0.50, stop:0 #8eacff, stop:1 #7979ff)'
            
            >>> create_gradient_string("#ff0000", "#00ff00", "#0000ff", angle_degrees=45)
            'qlineargradient(x1:0.00, y1:1.00, x2:1.00, y2:0.00, stop:0 #ff0000, stop:0.5 #00ff00, stop:1 #0000ff)'
            
            >>> create_gradient_string("#ffffff", angle_degrees=90)
            'qlineargradient(x1:0.50, y1:1.00, x2:0.50, y2:0.00, stop:0 #ffffff, stop:1 #ffffff)'
        """
        # Проверяем количество цветов
        if not colors:
            raise ValueError("Должен быть передан хотя бы один цвет")
        if len(colors) > 3:
            raise ValueError("Максимально поддерживается 3 цвета")
        
        # Приводим угол к диапазону 0-360 градусов
        angle = angle_degrees % 360
        
        # Переводим угол в радианы для вычислений
        angle_rad = math.radians(angle)
        
        # Вычисляем координаты начальной и конечной точек
        x1 = 0.5 + 0.5 * math.cos(angle_rad + math.pi)
        y1 = 0.5 + 0.5 * math.sin(angle_rad + math.pi)
        x2 = 0.5 + 0.5 * math.cos(angle_rad)
        y2 = 0.5 + 0.5 * math.sin(angle_rad)
        
        # Формируем остановки в зависимости от количества цветов
        if len(colors) == 1:
            # Один цвет - равномерная заливка
            stops = [f"stop:0 {colors[0]}", f"stop:1 {colors[0]}"]
        elif len(colors) == 2:
            # Два цвета - равномерный переход
            stops = [f"stop:0 {colors[0]}", f"stop:1 {colors[1]}"]
        else:  # 3 цвета
            # Три цвета - равномерное распределение
            stops = [
                f"stop:0 {colors[0]}",
                f"stop:0.5 {colors[1]}",
                f"stop:1 {colors[2]}"
            ]
        
        # Форматируем строку градиента
        stops_str = ", ".join(stops)
        gradient_str = (
            f"qlineargradient("
            f"x1:{x1:.2f}, "
            f"y1:{y1:.2f}, "
            f"x2:{x2:.2f}, "
            f"y2:{y2:.2f}, "
            f"{stops_str})"
        )
        
        return gradient_str

    def load_color_settings(self, styles=None):
        """Загружает текущие цвета из файла настроек."""
        # Основные цвета
        if styles is None:
            styles = self.styles
        
        self.text_color = styles.get("QPushButton", {}).get("color", "#ffffff")
        self.text_edit_color = styles.get("QTextEdit", {}).get("color", "#ffffff")

        self.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")

        # Загружаем настройки для каждого элемента
        self.load_element_settings(
            'background',
            styles.get("QWidget", {}).get("background-color", "#1d2028")
        )
        self.load_element_settings(
            'buttons',
            styles.get("QPushButton", {}).get("background-color", "#293f85")
        )
        self.load_element_settings(
            'svg',
            styles.get("BasedColors", {}).get("svg", "#0973ff")
        )

        border_value = styles.get("BasedColors", {}).get("border", "1px solid #0973ff")
        self.load_element_settings('borders', border_value)

        svg_value = styles.get("BasedColors", {}).get("svg", "#0973ff")
        self.load_element_settings('svg', svg_value)

        # Синхронизируем устаревшие переменные с текущими значениями
        self.bg_color = self.gradient_settings['background']['solid_color']
        self.btn_color = self.gradient_settings['buttons']['solid_color']

        border_full_value = styles.get("BasedColors", {}).get("border", "1px solid #0973ff")
        if border_full_value.startswith("1px solid "):
            self.border_color = border_full_value[len("1px solid "):]
        else:
            # Если формат неожиданный, попробуем взять из gradient_settings
            self.border_color = self.gradient_settings['borders']['solid_color']

        self.svg_color = svg_value
            
         # Радиус кнопок
        btn_radius_str = styles.get("QPushButton", {}).get("border-radius", "0px")
        self.border_btn_radius = int(btn_radius_str.rstrip("px"))
        
        # Радиус главного окна
        main_radius_str = styles.get("MainWindowWidget", {}).get("border-radius", "0px")
        self.border_main_radius = int(main_radius_str.rstrip("px"))
        
        # Устанавливаем значения в слайдеры
        if hasattr(self, 'btn_radius_slider'):
            self.btn_radius_slider.setValue(self.border_btn_radius)
            self.btn_radius_value_label.setText(str(self.border_btn_radius))
            
        if hasattr(self, 'main_radius_slider'):
            self.main_radius_slider.setValue(self.border_main_radius)
            self.main_radius_value_label.setText(str(self.border_main_radius))

        # Бордер главного окна
        main_border = styles.get("MainWindowWidget", {}).get("border", "none")
        self.border_in_main_window = main_border != "none"
        self.main_border_checkbox.setChecked(self.border_in_main_window)

        buttons_border = styles.get("QPushButton", {}).get("border", "none")
        self.border_in_buttons = buttons_border != "none"
        self.buttons_border_checkbox.setChecked(self.border_in_buttons)

        self.update_color_previews()
        debug_logger.info(f"[COLORSET] Стили загружены в переменные!")

    def load_element_settings(self, element_type, css_value):
        """Загружает настройки элемента (градиент или сплошной цвет)"""
        settings = self.gradient_settings[element_type]
        widgets = settings.get('widgets', {})

        # Сброс настроек
        settings.update({
            'enabled': False,
            'solid_color': "#000000",
            'color1': "#000000",
            'color2': "#000000",
            'angle': 0
        })

        # Для border нужно сначала извлечь цвет/градиент из строки
        if element_type == 'borders':
            # Извлекаем цвет или градиент из "1px solid ..."
            parts = css_value.split()
            if len(parts) >= 3:
                color_part = ' '.join(parts[2:])  # Берем всё после "1px solid"
                # Убираем возможные скобки в конце
                color_part = color_part.rstrip(');,')
            else:
                color_part = "#000000"
        else:
            color_part = css_value

        if color_part.startswith("qlineargradient") or css_value.startswith("qlineargradient"):
            # Режим градиента
            settings['enabled'] = True
            try:
                # Парсим координаты
                coord_pattern = r"([xy][12]):([\d.]+)"
                coords = dict(re.findall(coord_pattern, color_part))

                if len(coords) == 4:
                    x1, y1, x2, y2 = map(float, [coords['x1'], coords['y1'], coords['x2'], coords['y2']])
                    dx, dy = x2 - x1, y2 - y1
                    settings['angle'] = int(math.degrees(math.atan2(dy, dx)) % 360)

                # Парсим цвета
                color_pattern = r"stop:\d+\s+(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})"
                colors = re.findall(color_pattern, color_part)

                if len(colors) >= 2:
                    settings['color1'], settings['color2'] = colors[0], colors[1]

            except Exception as e:
                debug_logger.error(f"[COLORSET] Ошибка парсинга градиента для {element_type}: {e}")
                settings['enabled'] = False
        else:
            # Режим сплошного цвета
            settings['solid_color'] = color_part if color_part.startswith('#') else "#000000"
            settings['enabled'] = False
            if element_type == 'background':
                self.bg_color = settings['solid_color']
            elif element_type == 'buttons':
                self.btn_color = settings['solid_color']
            elif element_type == 'borders':
                self.border_color = settings['solid_color']
            elif element_type == 'svg':
                self.svg_color = settings['solid_color']

        # Обновляем UI если виджеты уже созданы
        if widgets:
            widgets['checkbox'].setChecked(settings['enabled'])
            # ЯВНО ВЫЗЫВАЕМ toggle_gradient ПОСЛЕ setChecked
            # Это необходимо, чтобы обновить видимость gradient_group и доступность других элементов
            # в соответствии с загруженным значением settings['enabled']
            self.toggle_gradient(element_type,
                                 Qt.CheckState.Checked if settings['enabled'] else Qt.CheckState.Unchecked)
            # ОБНОВЛЯЕМ ЦВЕТА ПРЕВЬЮ
            if 'color1_preview' in widgets:
                color1 = settings.get('color1', "#000000")
                widgets['color1_preview'].setStyleSheet(
                    f"background-color: {color1}; border: 1px solid #ccc; border-radius: 3px;"
                )
            
            if 'color2_preview' in widgets:
                color2 = settings.get('color2', "#000000") 
                widgets['color2_preview'].setStyleSheet(
                    f"background-color: {color2}; border: 1px solid #ccc; border-radius: 3px;"
                )
            
            if 'solid_color_preview' in widgets:
                solid_color = settings.get('solid_color', "#000000")
                widgets['solid_color_preview'].setStyleSheet(
                    f"background-color: {solid_color}; border: 1px solid #ccc; border-radius: 3px;"
                )

            if settings['enabled']:
                widgets['slider'].setValue(settings['angle'])
                widgets['spinbox'].setValue(settings['angle'])

            self.update_gradient_preview(element_type)

        QApplication.processEvents()
        self.container.repaint()
        self.update_color_previews()
        self.apply_changes(preview=True)

    def apply_changes(self, preview=False):
        try:
            new_styles = self.reference_style()

            if not preview:
                self.save_color_settings(new_styles)
                self.colorChanged.emit()
                color_signal.color_changed.emit()
            else:
                # Применяем стили только для предпросмотра
                self.setStyleSheet(self.generate_stylesheet(new_styles))
        except Exception as e:
            self.assistant.show_notification_message(f"Ошибка при применении изменений в превью-окне: {e}")
            debug_logger.error(f"[COLORSET] Ошибка при применении изменений в превью-окне: {e}")

    def get_gradient_css(self, element_type):
        """Генерирует CSS для градиента конкретного элемента"""
        settings = self.gradient_settings[element_type]
        if not settings['color1'] or not settings['color2']:
            return ""

        rad = math.radians(settings['angle'])
        x1 = 0.5 - 0.5 * math.cos(rad)
        y1 = 0.5 - 0.5 * math.sin(rad)
        x2 = 0.5 + 0.5 * math.cos(rad)
        y2 = 0.5 + 0.5 * math.sin(rad)

        return (
            f"qlineargradient("
            f"x1:{x1:.2f}, y1:{y1:.2f}, "
            f"x2:{x2:.2f}, y2:{y2:.2f}, "
            f"stop:0 {settings['color1']}, "
            f"stop:1 {settings['color2']})"
        )

    def generate_stylesheet(self, styles):
        """Генерирует строку CSS с правильными селекторами"""
        stylesheet = ""
        for widget, properties in styles.items():
            # Определяем правильный селектор
            if widget.startswith("Q"):  # Стандартные Qt виджеты
                selector = widget
            else:  # Кастомные ObjectName
                selector = f"#{widget}"

            stylesheet += f"{selector} {{\n"
            for prop, value in properties.items():
                stylesheet += f"    {prop}: {value};\n"
            stylesheet += "}\n"
        return stylesheet

    def save_color_settings(self, new_styles):
        """Сохраняет новые стили в color_settings.json."""
        with open(self.color_settings_path, 'w') as json_file:
            json.dump(new_styles, json_file, indent=4)

    def get_hover_gradient_css(self, element_type):
        """
        Генерирует CSS для градиента в состоянии :hover.
        Меняет местами color1 и color2.
        Если градиент отключен, возвращает сплошной цвет.
        """
        settings = self.gradient_settings[element_type]
        if not settings['enabled']:
            # Если градиент выключен, используем сплошной цвет и затемняем его
            solid_color = settings.get('solid_color', "#000000")
            # Используем существующий метод для затемнения
            return self._darken_single_color(solid_color, 10)

        color1 = settings.get('color1', "#000000")
        color2 = settings.get('color2', "#ffffff")
        angle = settings.get('angle', 0)

        # Меняем местами цвета
        return self._generate_qlineargradient(color2, color1, angle)
    
    def get_pressed_gradient_tab_css(self, element_type, darken_amount=30):
        """
        Генерирует CSS для градиента в состоянии :pressed.
        Затемняет оба цвета на заданное количество.
        Если градиент отключен, затемняет сплошной цвет.
        """
        settings = self.gradient_settings[element_type]
        if not settings['enabled']:
            # Если градиент выключен, используем сплошной цвет и затемняем его
            solid_color = settings.get('solid_color', "#000000")
            return self._darken_single_color(solid_color, darken_amount)

        color1 = settings.get('color1', "#000000")
        color2 = settings.get('color2', "#ffffff")
        angle = settings.get('angle', 0)

        # Затемняем оба цвета
        dark_color1 = self._darken_single_color(color1, darken_amount)
        dark_color2 = self._darken_single_color(color2, darken_amount)

        return self._generate_qlineargradient(dark_color1, dark_color2, angle)

    def get_pressed_gradient_css(self, element_type, darken_amount=30):
        """
        Генерирует CSS для градиента в состоянии :pressed.
        Затемняет оба цвета на заданное количество.
        Если градиент отключен, затемняет сплошной цвет.
        """
        settings = self.gradient_settings[element_type]
        if not settings['enabled']:
            # Если градиент выключен, используем сплошной цвет и затемняем его
            solid_color = settings.get('solid_color', "#000000")
            return self._darken_single_color(solid_color, darken_amount)

        color1 = settings.get('color1', "#000000")
        color2 = settings.get('color2', "#ffffff")
        angle = settings.get('angle', 0)

        # Затемняем оба цвета
        dark_color1 = self._darken_single_color(color1, darken_amount)
        dark_color2 = self._darken_single_color(color2, darken_amount)

        return self._generate_qlineargradient(dark_color1, dark_color2, angle)

    def _generate_qlineargradient(self, color1, color2, angle):
        """Вспомогательный метод для генерации строки qlineargradient."""
        rad = math.radians(angle)
        x1 = 0.5 - 0.5 * math.cos(rad)
        y1 = 0.5 - 0.5 * math.sin(rad)
        x2 = 0.5 + 0.5 * math.cos(rad)
        y2 = 0.5 + 0.5 * math.sin(rad)
        return f"qlineargradient(x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}, stop:0 {color1}, stop:1 {color2})"

    def _darken_single_color(self, color_str, amount):
        """Использование встроенного метода Qt."""
        if not color_str or not color_str.startswith('#'):
            return "#000000"
        
        color = QColor(color_str)
        
        # QColor.darker() принимает множитель (по умолчанию 200 = в 2 раза темнее)
        # Преобразуем amount в множитель
        factor = 100 + amount  # Например, amount=50 → factor=150 (на 50% темнее)
        
        darkened = color.darker(factor)
        return darkened.name()
    
    def get_pressed_gradient_css_rgba(self, element_type, darken_amount=30, alpha=None):
        """
        Генерирует CSS для градиента в состоянии :pressed в формате RGBA.
        Затемняет оба цвета на заданное количество.
        Если градиент отключен, затемняет сплошной цвет.
        
        Args:
            element_type: тип элемента
            darken_amount: степень затемнения (по умолч. 30)
            alpha: прозрачность (0-255 или None для сохранения исходной)
        """
        settings = self.gradient_settings[element_type]
        if not settings['enabled']:
            # Если градиент выключен, используем сплошной цвет и затемняем его
            solid_color = settings.get('solid_color', "#000000")
            return self._darken_single_color_rgba(solid_color, darken_amount, alpha)
        
        color1 = settings.get('color1', "#000000")
        color2 = settings.get('color2', "#ffffff")
        angle = settings.get('angle', 0)
        
        # Затемняем оба цвета и получаем в формате rgba
        dark_color1 = self._darken_single_color_rgba(color1, darken_amount, alpha)
        dark_color2 = self._darken_single_color_rgba(color2, darken_amount, alpha)
        
        return self._generate_qlineargradient_rgba(dark_color1, dark_color2, angle)

    def _darken_single_color_rgba(self, color_str, amount, alpha=None):
        """
        Затемняет цвет и возвращает его в формате rgba.
        
        Args:
            color_str: HEX цвет (#RRGGBB или #RRGGBBAA)
            amount: степень затемнения (0-100)
            alpha: прозрачность (0-255) или None для сохранения исходной
        """
        if not color_str or not color_str.startswith('#'):
            return "rgba(0, 0, 0, 1)"
        
        color = QColor(color_str)
        
        # Затемняем цвет
        factor = 100 + amount
        darkened = color.darker(factor)
        
        # Получаем компоненты
        r = darkened.red()
        g = darkened.green()
        b = darkened.blue()
        
        # Определяем альфа-канал
        if alpha is not None:
            # Если передана конкретная прозрачность
            a = alpha
        else:
            # Сохраняем исходную прозрачность
            a = darkened.alpha()
        
        # Нормализуем альфу для CSS (0-1)
        a_normalized = a / 255.0
        a_normalized = round(a_normalized, 2)
        
        return f"rgba({r}, {g}, {b}, {a_normalized})"

    def get_gradient_css_rgba(self, element_type, state="normal", alpha=None):
        """
        Универсальный метод для получения градиента в формате RGBA.
        
        Args:
            element_type: тип элемента
            state: состояние (normal, pressed, hover, disabled)
            alpha: прозрачность (0-255 или None для сохранения исходной)
        """
        settings = self.gradient_settings[element_type]
        
        if not settings['enabled']:
            solid_color = settings.get('solid_color', "#000000")
            return self._darken_single_color_rgba(solid_color, 0, alpha)
        
        color1 = settings.get('color1', "#000000")
        color2 = settings.get('color2', "#ffffff")
        angle = settings.get('angle', 0)
        
        # Применяем затемнение в зависимости от состояния
        darken_amount = 0
        if state == "pressed":
            darken_amount = 30
        elif state == "hover":
            darken_amount = 15
        elif state == "disabled":
            darken_amount = 0
            alpha = alpha or 150  # полупрозрачный для disabled
        
        # Затемняем цвета
        dark_color1 = self._darken_single_color_rgba(color1, darken_amount, alpha)
        dark_color2 = self._darken_single_color_rgba(color2, darken_amount, alpha)
        
        return self._generate_qlineargradient_rgba(dark_color1, dark_color2, angle)

    def get_solid_color_rgba(self, element_type, state="normal", alpha=None):
        """
        Получает сплошной цвет в формате RGBA.
        """
        settings = self.gradient_settings[element_type]
        solid_color = settings.get('solid_color', "#000000")
        
        darken_amount = 0
        if state == "pressed":
            darken_amount = 30
        elif state == "hover":
            darken_amount = 15
        
        return self._darken_single_color_rgba(solid_color, darken_amount, alpha)

    def save_preset(self):
        """Сохраняет текущие стили как новый пресет."""
        dialog = SavePresetDialog(self)

        if dialog.exec_() != QDialog.DialogCode.Accepted:
            return  # Пользователь отменил действие

        preset_name = dialog.get_text().strip()

        try:
            os.makedirs(self.custom_presets, exist_ok=True)
            preset_path = os.path.join(self.custom_presets, f"{preset_name}.json")

            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(self.reference_style(), f, indent=4, ensure_ascii=False)

            self.load_presets()
            self.assistant.show_notification_message("Пресет сохранен!")
            update_presets_signal.presets_updated.emit()

        except Exception as e:
            self.assistant.show_notification_message(f"Ошибка сохранения:\n{str(e)}")

    def load_presets(self):
        """Загружает существующие пресеты в выпадающий список."""
        self.preset_combo_box.clear()
        self.preset_combo_box.addItem("Выбрать пресет")

        # Проверяем, существует ли директория, если нет - создаем
        if not os.path.exists(self.base_presets):
            os.makedirs(self.base_presets)

        # Загружаем все файлы .json из директории пресетов
        for filename in os.listdir(self.base_presets):
            if filename.endswith('.json'):
                self.preset_combo_box.addItem(filename[:-5])  # Добавляем имя файла без .json

        for filename in os.listdir(self.custom_presets):
            if filename.endswith('.json'):
                self.preset_combo_box.addItem(filename[:-5])  # Добавляем имя файла без .json

    def load_preset(self):
        """Загружает выбранный пресет из файла, проверяя обе директории."""
        selected_preset = self.preset_combo_box.currentText()
        if not selected_preset or selected_preset == "Выбрать пресет":
            return  # Пресет не выбран

        # Формируем пути к файлам в обеих папках
        base_preset_path = os.path.join(self.base_presets, f"{selected_preset}.json")
        custom_preset_path = os.path.join(self.custom_presets, f"{selected_preset}.json")

        # Проверяем, в какой папке есть файл (приоритет у custom_presets)
        preset_path = None
        if os.path.exists(custom_preset_path):
            preset_path = custom_preset_path
        elif os.path.exists(base_preset_path):
            preset_path = base_preset_path
        else:
            self.assistant.show_notification_message(f"Пресет '{selected_preset}' не найден ни в одной из папок.")
            return

        try:
            with open(preset_path, 'r', encoding='utf-8') as json_file:
                styles = json.load(json_file)
    
            self.load_color_settings(styles)

            QApplication.processEvents()
            self.container.repaint()

        except Exception as e:
            self.assistant.show_notification_message(f"Ошибка загрузки пресета: {e}")
            
    def reference_style(self):
        """Эталонный стиль на основе текущих переменных"""
        return {
                    "BasedColors": {
                        "svg": f"{self.get_gradient_css('svg')}" if self.gradient_settings['svg'][
                            'enabled'] else f"{self.svg_color}",
                        "border": f"1px solid {self.get_gradient_css('borders')}" 
                            if self.gradient_settings['borders']['enabled'] 
                            else f"1px solid {self.border_color}"
                    },
                    "QWidget": {
                        "background-color": self.get_gradient_css('background') if self.gradient_settings['background'][
                            'enabled'] else self.bg_color,
                        "color": self.text_color,
                        "font-size": "14px"
                    },
                    "QPushButton": {
                        "background-color": self.get_gradient_css('buttons') if self.gradient_settings['buttons'][
                            'enabled'] else self.btn_color,
                        "color": self.text_color,
                        "height": "30px",
                        "border": (
                            f"1px solid {self.get_gradient_css('borders')}" 
                            if self.gradient_settings['borders']['enabled'] 
                            else f"1px solid {self.border_color}"
                            ) 
                            if self.border_in_buttons else "none",
                        "border-radius": f"{self.border_btn_radius}px",
                        "font-size": "14px"
                    },
                    "QPushButton:hover": {
                        "background-color": self.get_hover_gradient_css('buttons'),
                        "color": self.text_color,
                        "font-size": "14px"
                    },
                    "QPushButton:pressed": {
                        "background-color": self.get_pressed_gradient_css('buttons', 30),
                        "padding-left": "3px",
                        "padding-top": "3px",
                    },
                    "QTabBar": {
                        "background-color": "transparent"
                    },
                    "QTabBar::tab": {
                        "background-color": self.get_pressed_gradient_css('svg', darken_amount=150),
                        "color": self.text_color,
                        "height": "30px",
                        "border":"none",
                        "border-radius": "5px",
                        "font-size": "13px",
                        "margin": "0",
                        "padding": "3px",
                        "padding-left": "8px",
                        "padding-right": "8px"
                    },
                    "QTabBar::tab:selected": {
                        "background-color": self.get_pressed_gradient_css('svg', darken_amount=70),
                        "color": self.text_color,
                        "font-size": "13px",
                        "margin-left": "-4px",
                    },
                    "QTabBar::pane": {
                        "background": "transparent",
                        "border-bottom": f"1px solid {self.get_gradient_css('borders')}" 
                            if self.gradient_settings['borders']['enabled'] 
                            else f"1px solid {self.border_color}",
                    },
                    "WSTabsContainer": {
                        "background": "transparent",
                        "border-radius": "10px"
                    },
                    "WSBottomContainer": {
                        "background-color": "transparent"
                    },
                    "WSMainTabBar": {
                        "background-color": "transparent"
                    },
                    "WMLeftContainer": {
                        "background-color": "transparent"
                    },
                    "WMLeftButtonsPanel": {
                        "background-color": "transparent"
                    },
                    "WMSettingsWidget": {
                        "background-color": "transparent"
                    },
                    "WMSettingsContent": {
                        "background-color": "transparent"
                    },
                    "WM_MutablePanel": {
                        "background-color": "transparent"
                    },
                    "TabWidget": {
                        "background": "transparent"
                    },
                    "TabWidget::pane": {
                        "background": "transparent"
                    },
                    "QLineEdit": {
                        "background-color": "transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_btn_radius}px",
                        "padding": "5px"
                    },
                    "QComboBox": {
                        "background-color": "transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_btn_radius}px",
                        "padding": "5px"
                    },
                    "QCheckBox": {
                        "background-color": "transparent",
                        "padding": "2px"
                    },
                    "QCheckBox::indicator": {
                        "width": "12px",
                        "height": "12px",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": "5px",
                        "padding": "5px"
                    },
                    "QCheckBox::indicator:hover": {
                        "width": "11px",
                        "height": "11px"
                    },
                    "QCheckBox::indicator:checked": {
                        "background-color": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"{self.border_color}",
                    },
                    "QTextEdit": {
                        "background": "transparent",
                        "color": self.text_edit_color,
                        "border": "none",
                        "font-size": "15px"
                    },
                    "label_message": {
                        "color": self.text_color,
                        "font-size": "13px"
                    },
                    "clock_mini": {
                        "color": self.text_edit_color
                    },
                    "clock_title": {
                        "color": self.text_edit_color
                    },
                    "TitleBar": {
                        "background": "transparent",
                        "border-bottom": f"1px solid {self.get_gradient_css('borders')}" if
                        self.gradient_settings['borders']['enabled'] else f"1px solid {self.border_color}",
                        "border-bottom-left-radius": "0px",
                        "border-bottom-right-radius": "0px"
                    },
                    "TrayButton": {
                        "background-color": self.get_gradient_css('buttons') if self.gradient_settings['buttons'][
                            'enabled'] else self.btn_color,
                        "color": self.text_color,
                        "height": "30px",
                        "border": (
                            f"1px solid {self.get_gradient_css('borders')}"
                            if self.gradient_settings['borders']['enabled']
                            else f"1px solid {self.border_color}"
                            )
                            if self.border_in_buttons else "none",
                        "border-radius": f"{self.border_btn_radius}px",
                        "font-size": "13px"
                    },
                    "TrayButton:hover": {
                        "background-color": "#0790EC",
                        "border": "1px solid #0790EC"
                    },
                    "CloseButton": {
                        "background-color": self.get_gradient_css('buttons') if self.gradient_settings['buttons'][
                            'enabled'] else self.btn_color,
                        "color": self.text_color,
                        "height": "30px",
                        "border": (
                            f"1px solid {self.get_gradient_css('borders')}"
                            if self.gradient_settings['borders']['enabled']
                            else f"1px solid {self.border_color}"
                            )
                            if self.border_in_buttons else "none",
                        "border-radius": f"{self.border_btn_radius}px",
                        "font-size": "13px"
                    },
                    "CloseButton:hover": {
                        "background-color": "#E04F4F",
                        "border": "1px solid #E04F4F"
                    },
                    "MessageContainer": {
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_main_radius}px"
                    },
                    "WindowContainer": {
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_main_radius}px"
                    },
                    "MainWindowWidget": {
                        "border": (
                            f"1px solid {self.get_gradient_css('borders')}" 
                            if self.gradient_settings['borders']['enabled'] else 
                            f"1px solid {self.border_color}"
                        ) if self.border_in_main_window else "none",
                        "border-radius": f"{self.border_main_radius}px"
                    },
                    "SettingsWidget": {
                        "border": "none",
                        "border-radius": "10px"
                    },
                    "ContentWidget": {
                        "background-color": "transparent"
                    },
                    "QMainWindow": {
                        "background-color": "transparent",
                        "border": "none"
                    },
                    "QMenu": {
                        "background-color": self.get_gradient_css('background') if self.gradient_settings['background'][
                            'enabled'] else self.bg_color,
                        "color": "#ffffff",
                        "font-size": "13px",
                        "padding": "5px",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "margin": "0px"
                    },
                    "QMenu::item": {
                        "background-color": self.get_gradient_css('buttons') if self.gradient_settings['buttons'][
                            'enabled'] else self.btn_color,
                        "padding": "8px 30px",
                        "margin": "1px",
                        "border-radius": f"{self.border_btn_radius}px",
                        "border-left": f"1px solid {self.get_pressed_gradient_css('borders', 50)}",
                        "border-right": f"1px solid {self.get_pressed_gradient_css('borders', 50)}"
                    },
                    "QMenu::item:selected": {
                        "border-radius": f"{self.border_btn_radius}px",
                        "background-color": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"{self.border_color}",
                        "color": "#ffffff"
                    },
                    "QColorDialog QPushButton": {
                        "padding-left": "5px",
                        "padding-right": "5px"
                    },
                    "QSlider::handle:horizontal": {
                        "background-color": self.get_gradient_css('buttons') if self.gradient_settings['buttons'][
                            'enabled'] else self.btn_color,
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": "3px",
                        "width": "12px",
                        "height": "18px",
                        "margin": "-7px 0"
                    },
                    "QSlider::groove:horizontal": {
                        "background": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "height": "8px",
                        "border-radius": "4px",
                        "margin": "0"
                    },
                    "LabelSliderValue": {
                        "background": "transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": "3px"
                    },
                    "QScrollBar:vertical": {
                        "border": "none",
                        "background": self.get_pressed_gradient_css('borders', darken_amount=75),
                        "width": "8px",
                        "border-radius": "4px",
                        "margin": "0px"
                    },
                    "QScrollBar::handle:vertical": {
                        "background": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"{self.border_color}",
                        "border-radius": "4px",
                        "min-height": "20px",
                        "margin": "0px"
                    },
                    "QScrollBar::add-line:vertical": {
                        "border": "none",
                        "background": "none",
                        "height": "0px",
                        "width": "0px"
                    },
                    "QScrollBar::sub-line:vertical": {
                        "border": "none",
                        "background": "none",
                        "height": "0px",
                        "width": "0px"
                    },
                    "QScrollBar::add-page:vertical": {
                        "background": "none"
                    },
                    "QScrollBar::sub-page:vertical": {
                        "background": "none"
                    },
                    "QListWidget": {
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_main_radius}px"
                    },
                    "HelpWidget": {
                        "background":"transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_main_radius}px"
                    },
                    "LogArea": {
                        "background": "transparent",
                        "color": self.text_edit_color,
                        "border": "none",
                        "font-size": "15px"
                    },
                    "SidebarElement": {
                        "background": "transparent",
                        "color": self.text_color,
                        "border-radius": "none",
                        "border": "none"
                    },
                    "SidebarElement::hover": {
                        "border-top": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-bottom": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}"
                    },
                    "ToolButton": {
                        "background": "transparent",
                        "border-radius": "none",
                        "border": "none"
                    },
                    "VersionLabel": {
                        "background": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"{self.border_color}",
                        "color": self.text_color,
                        "border-radius": "10px",
                        "border": "none",
                        "padding": "6px",
                        "font-size": "13px"
                    },
                    "VersionLabel::hover": {
                        "border": f"2px solid {self.text_edit_color}"
                    },
                    "UpdateLabel": {
                        "background": f"{self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"{self.border_color}",
                        "color": self.text_color,
                        "border-radius": "10px",
                        "border": "none",
                        "padding": "6px",
                        "font-size": "14px"
                    },
                    "UpdateLabel::hover": {
                        "border": f"2px solid {self.text_edit_color}"
                    },
                    "UserProfileWidget": {
                        "background-color": "transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": "17px"
                    },
                    "UserProfileWidget::hover": {
                        "border": f"2px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"2px solid {self.border_color}"
                    },
                    "ScriptStepFrame": {
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}"
                    },
                    "QSpinBox": {
                        "background-color": "transparent",
                        "border": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}",
                        "border-radius": f"{self.border_btn_radius}px",
                        "padding": "5px"
                    },
                    "CreateCommandsWidgets": {
                        "background-color": "transparent"
                    },
                    "CreateRunWidgets": {
                        "background-color": "transparent"
                    },
                    "TitleBarPanel": {
                        "background-color": "transparent",
                        "border-bottom": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}"
                    },
                    "AudioPlayerWidget": {
                        "background-color": "transparent",
                        "border-top": f"1px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                            'enabled'] else f"1px solid {self.border_color}"
                    },
                    "QScrollArea": {
                        "background-color": "transparent",
                        "border": "none"
                    }
        }
       
    def update_style_file(self, file_path: str = None):
        """
        Обновляет структуру одного файла стиля.
        Если file_path не указан — обновляется основной файл (self.color_settings_path).
        """
        if file_path is None:
            load_settings = False
            file_path = self.color_settings_path
        else:
            load_settings = True
        # Загружаем текущий стиль из файла
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current = json.load(f)
                self.styles = current

                if load_settings:
                    self.load_color_settings()
                debug_logger.info(f"[COLORSET] Стиль загружен из: {file_path}")
            except Exception as e:
                debug_logger.warning(f"[COLORSET] Не удалось загрузить {file_path}: {e}")
                current = {}
        else:
            current = {}

        # Генерируем эталонный стиль
        reference = self.reference_style()

        # Сливаем с сохранением порядка
        merged = self.merge_with_reference(reference)

        # Сохраняем обратно
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=4, ensure_ascii=False)
            debug_logger.info(f"[COLORSET] Обновлён файл: {file_path}")
            return True
        except Exception as e:
            debug_logger.error(f"[COLORSET] Ошибка записи в {file_path}: {e}")
            return False
        
    def update_all_styles(self, extension: str = ".json"):
        """
        Обновляет все файлы с заданным расширением в обеих папках пресетов:
        - bin/color_presets
        - user_settings/presets
        """
        folders = [
            get_path("bin", "color_presets"),
            get_path("user_settings", "presets")
        ]

        updated_files = []

        for folder_path in folders:
            if not os.path.exists(folder_path):
                debug_logger.warning(f"[COLORSET] Папка не найдена: {folder_path}")
                continue

            filenames = [f for f in os.listdir(folder_path) if f.endswith(extension)]
            for filename in filenames:
                full_path = os.path.join(folder_path, filename)
                if self.update_style_file(full_path):
                    updated_files.append(full_path)

        debug_logger.info(f"[COLORSET] Обновлено файлов: {len(updated_files)} в папках: {folders}")
        return updated_files
    
    def merge_with_reference(self, reference_style):
        """
        Полная синхронизация со reference_style.
        Все значения берутся из reference_style.
        current_style используется ТОЛЬКО как источник для последующего применения настроек цвета.
        """
        return dict(reference_style)


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


class SavePresetDialog(QDialog):
    """Кастомное диалоговое окно ввода с валидацией"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(320, 170)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.init_ui()

    def init_ui(self):
        # Основной контейнер
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        self.container.setGeometry(0, 0, self.width(), self.height())

        # Кастомный заголовок
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setGeometry(1, 1, self.width() - 2, 35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 5, 10, 5)
        self.title_layout.setSpacing(5)

        self.title_label = QLabel('Сохранить пресет', self.title_bar)
        self.title_label.setStyleSheet("background: transparent")
        self.title_label.setGeometry(10, 5, 200, 20)
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton("", self.title_bar)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)
        self.parent_window.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")

        # Основное содержимое
        self.content_widget = QWidget(self.container)
        self.content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)
        self.content_widget.setObjectName("ContentWidget")

        # Поле ввода
        self.input_field = QLineEdit(self.content_widget)
        self.input_field.setPlaceholderText('Введите имя пресета:')

        # Label для ошибок
        self.error_label = QLabel(self.content_widget)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        # Кнопки
        self.ok_button = QPushButton('Сохранить', self.content_widget)
        self.ok_button.setStyleSheet("padding: 1px 10px;")
        self.ok_button.setObjectName("AcceptButton")
        self.ok_button.clicked.connect(self.try_accept)

        self.cancel_button = QPushButton('Закрыть', self.content_widget)
        self.cancel_button.setStyleSheet("padding: 1px 10px;")
        self.cancel_button.setObjectName("RejectButton")
        self.cancel_button.clicked.connect(self.reject)

        # Размещение элементов
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)  # Уменьшили отступ

        main_layout.addWidget(self.input_field)
        main_layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.set_position_strategy()

    def try_accept(self):
        """Пытается закрыть окно, если ввод корректен."""
        preset_name = self.get_text()
        if not preset_name:
            self.show_error("Имя не может быть пустым!")
            return

        conflict_paths = [
            os.path.join(self.parent().base_presets, f"{preset_name}.json"),
            os.path.join(self.parent().custom_presets, f"{preset_name}.json")
        ]

        if any(os.path.exists(path) for path in conflict_paths):
            self.show_error(f"Пресет '{preset_name}' уже существует!")
            return

        self.accept()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_text(self):
        """Возвращает очищенный текст из поля ввода."""
        return self.input_field.text().strip()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()  # Закрываем только это окно
        else:
            super().keyPressEvent(event)

    def set_position_strategy(self):
        """Выбирает стратегию позиционирования окна"""
        self.position_strategy = self.center_to_parent()

    def ensure_on_screen(self):
        # Получаем экран, на котором находится окно
        screen = self.screen()
        if not screen:
            # Если окно еще не показано, берем основной экран
            screen = QApplication.primaryScreen()

        screen_geometry = screen.availableGeometry()

        if not screen_geometry.contains(self.geometry()):
            self.move(
                min(screen_geometry.right() - self.width(), max(screen_geometry.left(), self.x())),
                min(screen_geometry.bottom() - self.height(), max(screen_geometry.top(), self.y()))
            )

    def center_to_parent(self):
        """Центрирует по горизонтали и позиционирует чуть ниже заголовка родителя"""
        if not self.parent():
            return

        parent_rect = self.parent().geometry()
        title_bar_height = 20  # Высота заголовка родительского окна (может потребоваться подстройка)

        # Центрируем по горизонтали и позиционируем вертикально чуть ниже заголовка
        new_x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
        new_y = parent_rect.y() + title_bar_height + 15

        self.move(new_x, new_y)

        # Проверяем, чтобы окно не выходило за пределы экрана
        self.ensure_on_screen()

    def mousePressEvent(self, event):
        """Перетаскивание окна за заголовок"""
        if event.button() == Qt.MouseButton.LeftButton and event.y() < 30:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Перетаскивание окна за заголовок"""
        if hasattr(self, 'drag_position') and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

class SimpleColorPicker(QDialog):
    color_changed = Signal(str)
    def __init__(self, initial_color="#FF0000", parent=None):
        super().__init__(parent)
        self.icon_close_path = get_path("bin", "icons", "close.svg")
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