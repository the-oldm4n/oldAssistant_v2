"""Окно настроек цветов и градиентов"""
import json
import math
import os
import re
from PySide6.QtCore import Signal, Qt, QPoint, QRect
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QPushButton, QDialog, QWidget, \
    QHBoxLayout, QComboBox, QApplication, QMainWindow

from mygui.core.apply_color import main_apply_colors
from mygui.core.signals import color_signal, update_presets_signal
from mygui.dialogs.settings_widgets.all_styles_widget import AllStylesWidget
from mygui.dialogs.settings_widgets.background_widget import BackgroundWidget
from mygui.dialogs.settings_widgets.border_widget import BorderWidget
from mygui.dialogs.settings_widgets.buttons_widget import ButtonsWidget
from mygui.dialogs.settings_widgets.radius_widget import RadiusWidget
from mygui.dialogs.settings_widgets.svg_widget import SvgWidget
from mygui.dialogs.settings_widgets.text_widget import TextWidget
from mygui.helpers.custom_stacked_widget import SlidingStackedWidget
from mygui.paths import ICONS
from mygui.widgets.custom_svg import CustomSvgWidget
from mygui.dialogs.color_picker import SimpleColorPicker
from mygui.dialogs.save_preset import SavePresetDialog
from mygui.config import mygui_config


class ColorSettingsWindow(QMainWindow):
    """Окно изменения оформления интерфейса с поддержкой градиентов"""
    colorChanged = Signal()  # Сигнал изменения цвета
    def __init__(self, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        self.main = parent
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.base_presets = mygui_config.presets_path
        self.custom_presets = mygui_config.custom_presets_path
        os.makedirs(self.custom_presets, exist_ok=True)

        self.default_size = 500, 700
        self.setMouseTracking(True)
        self.init_icons()

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
                'widgets': {}
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

    def init_icons(self):
        self.icon_styles_path = os.path.join(ICONS, "styles-icon.svg")
        self.icon_background_path = os.path.join(ICONS, "background-icon.svg")
        self.icon_text_path = os.path.join(ICONS, "text-icon.svg")
        self.icon_border_path = os.path.join(ICONS, "border-icon.svg")
        self.icon_buttons_path = os.path.join(ICONS, "btn-icon.svg")
        self.icon_svg_path = os.path.join(ICONS, "svg-icon.svg")
        self.icon_radius_path = os.path.join(ICONS, "radius-icon.svg")
        self.icon_close_path = os.path.join(ICONS, "close.svg")

    def apply_styles(self):
        """Применяет все стили к окну"""
        try:
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
            return True
        except Exception as e:
            return False

    def init_ui(self):
        self.margin = 7
        self.drag_pos = None
        self.dragging = False
        self.drag_position = None
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.dragging_maximized = False
        self.drag_start_pos = None
        self.drag_start_geometry = None
        self._drag_click_offset = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        self.resize(*self.default_size)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        self.setCentralWidget(self.container)
        self.container.setMouseTracking(True)

        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBarV2")
        self.title_bar.setFixedHeight(40)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 0, 0)
        self.title_layout.setSpacing(5)

        self.title_bar.mousePressEvent = self.title_bar_mouse_press
        self.title_bar.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar.mouseReleaseEvent = self.title_bar_mouse_release

        self.title_label = QLabel("Редактор стилей", self.title_bar)
        self.title_label.setStyleSheet("background: transparent")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton(self.title_bar)
        self.close_btn.setFixedSize(50, 40)
        self.close_btn.setObjectName("TitleBarCloseBtn")
        self.close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(12, 7)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)

        self.content_widget = QWidget(self.container)
        self.content_widget.setObjectName("ContentWidget")

        self.main_content_layout = QVBoxLayout(self.content_widget)
        self.main_content_layout.setContentsMargins(10, 10, 10, 10)
        self.main_content_layout.setSpacing(5)

        self.button_panel = QWidget()
        self.button_panel.setObjectName("TabPanel")
        button_layout = QHBoxLayout(self.button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        self.content_container = SlidingStackedWidget(self)
        
        self.all_styles_widget = AllStylesWidget(self.main, self)
        self.background_widget = BackgroundWidget(self)
        self.text_widget = TextWidget(self)
        self.buttons_widget = ButtonsWidget(self)
        self.svg_widget = SvgWidget(self)
        self.border_widget = BorderWidget(self)
        self.radius_widget = RadiusWidget(self)
        
        self.content_container.add_page(self.all_styles_widget)
        self.content_container.add_page(self.background_widget)
        self.content_container.add_page(self.buttons_widget)
        self.content_container.add_page(self.text_widget)
        self.content_container.add_page(self.svg_widget)
        self.content_container.add_page(self.border_widget)
        self.content_container.add_page(self.radius_widget)
        

        buttons_data = [
            {
                "key": "all_styles",
                "text": "Стили",
                "icon_path": self.icon_styles_path,
                "tooltip": "Выбор стилей",
                "index": 0,
                "widget": self.all_styles_widget
            },
            {
                "key": "background",
                "text": "Фон",
                "icon_path": self.icon_background_path,
                "tooltip": "Задний фон",
                "index": 1,
                "widget": self.background_widget
            },
            {
                "key": "buttons",
                "text": "Кнопки",
                "icon_path": self.icon_buttons_path,
                "tooltip": "Кнопки",
                "index": 2,
                "widget": self.buttons_widget
            },
            {
                "key": "text",
                "text": "Текст",
                "icon_path": self.icon_text_path,
                "tooltip": "Текст",
                "index": 3,
                "widget": self.text_widget
            },
            {
                "key": "svg",
                "text": "SVG",
                "icon_path": self.icon_svg_path,
                "tooltip": "SVG-иконки",
                "index": 4,
                "widget": self.radius_widget
            },
            {
                "key": "border",
                "text": "Обводки",
                "icon_path": self.icon_border_path,
                "tooltip": "Бордер",
                "index": 5,
                "widget": self.border_widget
            },
            {
                "key": "radius",
                "text": "Радиус",
                "icon_path": self.icon_radius_path,
                "tooltip": "Радиус скругления",
                "index": 6,
                "widget": self.radius_widget
            }
        ]
        
        self.nav_buttons = []
        self.nav_svgs = []
        
        for data in buttons_data:
            btn = QPushButton()
            btn.setFixedSize(60, 40)
            btn.setObjectName("TabBtn")
            btn.setToolTip(data["tooltip"])
            
            if data["icon_path"]:
                svg = CustomSvgWidget(data["icon_path"], btn)
                svg.setFixedSize(35, 35)
                svg.move(12, 2)
                self.style_manager.apply_color_svg(svg)
                self.nav_svgs.append(svg)
            
            btn.clicked.connect(lambda checked, idx=data["index"]: self.switch_page(idx, "top"))
            
            self.nav_buttons.append(btn)
            button_layout.addWidget(btn)
        
        button_layout.addStretch()
        
        self.main_content_layout.addWidget(self.button_panel)
        self.main_content_layout.addWidget(self.content_container)

        self.bottom_container = QWidget()
        self.bottom_container.setObjectName("WSBottomContainer")
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(10, 10, 10, 10)
        self.bottom_layout.setSpacing(8)

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

        self.bottom_layout.addWidget(self.save_preset_button)
        self.bottom_layout.addWidget(self.styles_label)
        self.bottom_layout.addWidget(self.preset_combo_box)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.apply_button)

        self.main_content_layout.addWidget(self.bottom_container)

        self.root_layout.addWidget(self.title_bar)
        self.root_layout.addWidget(self.content_widget)

        self.switch_page(0, "top")

        self.centralWidget().adjustSize()
        self.minimum_size = self.centralWidget().minimumSizeHint()
        self.setup_mouse_tracking_for_children(self.container)

    def setup_mouse_tracking_for_children(self, widget):
        """Устанавливает mouse tracking для всех дочерних виджетов"""
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    def switch_page(self, index, direction="right"):
        self.content_container.switch_to(index, direction)
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_colors(self, styles=None, is_preview=False):
        solid_color = None
        gradient = None
        if is_preview:
            _color = styles.get("BasedColors", {}).get("svg", "#0973ff")
            if _color.startswith("qlineargradient"):
                gradient = _color
            else:
                solid_color = _color
        for svg in self.nav_svgs:
            self.style_manager.apply_color_svg(svg, specified_color=solid_color, spec_gradient=gradient)

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

    def toggle_gradient(self, element_type, state):
        """Включает/выключает градиент для конкретного элемента"""
        # state может быть: 0, 2, True, False, Qt.CheckState
        if isinstance(state, Qt.CheckState):
            enabled = state == Qt.CheckState.Checked
        elif isinstance(state, int):
            # 0 = Unchecked, 2 = Checked
            enabled = state == 2
        else:
            # bool или другие типы
            enabled = bool(state)

        # logger.info(f"🎛️ toggle_gradient: {element_type}, state={state}, type={type(state)}, enabled={enabled}")

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
            'borders',
            styles.get("BasedColors", {}).get("border", "#0973ff")
        )
        self.load_element_settings(
            'svg',
            styles.get("BasedColors", {}).get("svg", "#0973ff")
        )

        border_value = styles.get("BasedColors", {}).get("border", "1px solid #0973ff")
        self.load_element_settings('borders', border_value)

        svg_value = styles.get("BasedColors", {}).get("svg", "#0973ff")
        self.svg_color = svg_value

        # Синхронизируем устаревшие переменные с текущими значениями
        self.bg_color = self.gradient_settings['background']['solid_color']
        self.btn_color = self.gradient_settings['buttons']['solid_color']

        border_full_value = styles.get("BasedColors", {}).get("border", "1px solid #0973ff")
        if border_full_value.startswith("1px solid "):
            self.border_color = border_full_value[len("1px solid "):]
        else:
            # Если формат неожиданный, попробуем взять из gradient_settings
            self.border_color = self.gradient_settings['borders']['solid_color']
     
         # Радиус кнопок
        btn_radius_str = styles.get("QPushButton", {}).get("border-radius", "0px")
        self.border_btn_radius = int(btn_radius_str.rstrip("px"))
        
        # Радиус главного окна
        main_radius_str = styles.get("MainWindowWidget", {}).get("border-radius", "0px")
        self.border_main_radius = int(main_radius_str.rstrip("px"))

        self.radius_widget.set_values()

        # Бордер главного окна
        main_border = styles.get("MainWindowWidget", {}).get("border", "none")
        self.border_in_main_window = main_border != "none"
        self.radius_widget.main_border_checkbox.setChecked(self.border_in_main_window)

        buttons_border = styles.get("QPushButton", {}).get("border", "none")
        self.border_in_buttons = buttons_border != "none"
        self.buttons_widget.buttons_border_checkbox.setChecked(self.border_in_buttons)

        self.text_widget.update_color_previews()

        self.apply_changes(preview=True)

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
            parts = css_value.split()
            if len(parts) >= 3:
                color_part = ' '.join(parts[2:])
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

            self.toggle_gradient(element_type,
                                 Qt.CheckState.Checked if settings['enabled'] else Qt.CheckState.Unchecked)
            
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
        # self.text_widget.update_color_previews()
        # self.apply_changes(preview=True)

    def apply_changes(self, preview=False):
        try:
            new_styles = self.reference_style()
            if not preview:
                self.save_new_colors(new_styles)
                self.colorChanged.emit()
                color_signal.color_changed.emit()
            else:
                # Применяем стили только для предпросмотра
                self.setStyleSheet(self.generate_stylesheet(new_styles))
                self.update_colors(styles=new_styles, is_preview=True)
        except Exception as e:
            return None

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
            if widget.startswith("Q"):
                selector = widget
            else:
                selector = f"#{widget}"
            stylesheet += f"{selector} {{\n"
            for prop, value in properties.items():
                stylesheet += f"    {prop}: {value};\n"
            stylesheet += "}\n"
        return stylesheet

    def save_new_colors(self, new_styles):
        """Сохраняет новые стили в color.json."""
        with open(self.color_path, 'w') as json_file:
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
    
    # def get_pressed_gradient_tab_css(self, element_type, darken_amount=30):
    #     """
    #     Генерирует CSS для градиента в состоянии :pressed.
    #     Затемняет оба цвета на заданное количество.
    #     Если градиент отключен, затемняет сплошной цвет.
    #     """
    #     settings = self.gradient_settings[element_type]
    #     if not settings['enabled']:
    #         # Если градиент выключен, используем сплошной цвет и затемняем его
    #         solid_color = settings.get('solid_color', "#000000")
    #         return self._darken_single_color(solid_color, darken_amount)

    #     color1 = settings.get('color1', "#000000")
    #     color2 = settings.get('color2', "#ffffff")
    #     angle = settings.get('angle', 0)

    #     # Затемняем оба цвета
    #     dark_color1 = self._darken_single_color(color1, darken_amount)
    #     dark_color2 = self._darken_single_color(color2, darken_amount)

    #     return self._generate_qlineargradient(dark_color1, dark_color2, angle)

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
    
    def _generate_qlineargradient_rgba(self, color1, color2, angle):
        """
        Вспомогательный метод для генерации строки qlineargradient с цветами в формате RGBA.
        
        Args:
            color1: первый цвет в формате rgba(r,g,b,a)
            color2: второй цвет в формате rgba(r,g,b,a)
            angle: угол градиента в градусах
        """
        rad = math.radians(angle)
        x1 = 0.5 - 0.5 * math.cos(rad)
        y1 = 0.5 - 0.5 * math.sin(rad)
        x2 = 0.5 + 0.5 * math.cos(rad)
        y2 = 0.5 + 0.5 * math.sin(rad)
        
        return f"qlineargradient(x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}, stop:0 {color1}, stop:1 {color2})"

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

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        preset_name = dialog.get_text().strip()

        try:
            os.makedirs(self.custom_presets, exist_ok=True)
            preset_path = os.path.join(self.custom_presets, f"{preset_name}.json")

            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(self.reference_style(), f, indent=4, ensure_ascii=False)

            self.load_presets()
            self.show_message("Пресет сохранен!")
            update_presets_signal.presets_updated.emit()

        except Exception as e:
            self.show_message(f"Ошибка сохранения:\n{str(e)}")

    def load_presets(self):
        """Загружает существующие пресеты в выпадающий список."""
        self.preset_combo_box.clear()
        self.preset_combo_box.addItem("Выбрать пресет")

        if not os.path.exists(self.base_presets):
            os.makedirs(self.base_presets)

        for filename in os.listdir(self.base_presets):
            if filename.endswith('.json'):
                self.preset_combo_box.addItem(filename[:-5])

        for filename in os.listdir(self.custom_presets):
            if filename.endswith('.json'):
                self.preset_combo_box.addItem(filename[:-5])

    def load_preset(self):
        """Загружает выбранный пресет из файла, проверяя обе директории."""
        selected_preset = self.preset_combo_box.currentText()
        if not selected_preset or selected_preset == "Выбрать пресет":
            return

        base_preset_path = os.path.join(self.base_presets, f"{selected_preset}.json")
        custom_preset_path = os.path.join(self.custom_presets, f"{selected_preset}.json")

        preset_path = None
        if os.path.exists(custom_preset_path):
            preset_path = custom_preset_path
        elif os.path.exists(base_preset_path):
            preset_path = base_preset_path
        else:
            self.show_message(f"Пресет '{selected_preset}' не найден ни в одной из папок.")
            return

        try:
            with open(preset_path, 'r', encoding='utf-8') as json_file:
                styles = json.load(json_file)

            self.load_color_settings(styles)

            QApplication.processEvents()
            self.container.repaint()
        except Exception as e:
            self.show_message(f"Ошибка загрузки пресета: {e}")
            
    def reference_style(self):
        """Эталонный стиль на основе текущих переменных"""
        base_styles = {
            "BasedColors": {
                "svg": self.get_css("svg"),
                "border": self.get_css("border"),
                "text": self.get_text_css("text"),
                "text_edit": self.get_text_css("text_edit")
            },
            "QWidget": {
                "background-color": self.get_css("background"),
                "color": self.get_text_css('text'),
                "font-size": "14px"
            },
            "QPushButton": {
                "background-color": self.get_css("button"),
                "color": self.get_text_css('text'),
                "height": "30px",
                "border": self.get_css("border", is_btn_border=True),
                "border-radius": self.get_border_radius_css('button'),
                "font-size": "14px"
            },
            "QPushButton:hover": {
                "background-color": self.get_hover_css('button'),
                "color": self.get_text_css('text'),
                "font-size": "14px"
            },
            "QPushButton:pressed": {
                "background-color": self.get_pressed_css('button', darken=30),
                "padding-left": "3px",
                "padding-top": "3px",
            },
            "QTabBar": {
                "background-color": "transparent"
            },
            "QTabBar::tab": {
                "background-color": self.get_pressed_css('svg', darken=150),
                "color": self.get_text_css('text'),
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
                "background-color": self.get_pressed_css('svg', darken=70),
                "color": self.get_text_css('text'),
                "font-size": "13px",
                "margin-left": "-4px",
            },
            "QTabBar::pane": {
                "background": "transparent",
                "border-bottom": self.get_css("border"),
            },
            "QLineEdit": {
                "background-color": "transparent",
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('button'),
                "padding": "5px"
            },
            "QComboBox": {
                "background-color": "transparent",
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('button'),
                "padding": "5px"
            },
            "QCheckBox": {
                "background-color": "transparent",
                "padding": "2px"
            },
            "QCheckBox::indicator": {
                "width": "12px",
                "height": "12px",
                "border": self.get_css("border"),
                "border-radius": "5px",
                "padding": "5px"
            },
            "QCheckBox::indicator:hover": {
                "width": "11px",
                "height": "11px"
            },
            "QCheckBox::indicator:checked": {
                "background-color": self.get_css("svg"),
            },
            "QTextEdit": {
                "background": "transparent",
                "color": self.get_text_css('text_edit'),
                "border": "none",
                "font-size": "15px"
            },
            "QMainWindow": {
                "background-color": "transparent"
            },
            "QMenu": {
                "background-color": self.get_pressed_css('svg', darken=150, alpha=150),
                "color": "#ffffff",
                "border-radius": "10px",
                "font-size": "13px",
                "padding": "5px",
                "border": "none",
                "margin": "0px"
            },
            "QMenu::item": {
                "background-color": self.get_css("button"),
                "padding": "10px 30px",
                "margin": "1px",
                "border-radius": "5px"
            },
            "QMenu::item:selected": {
                "background-color": self.get_hover_css("button"),
                "border-left": f"2px solid {self.get_css('svg')}"
            },
            "QColorDialog QPushButton": {
                "padding-left": "5px",
                "padding-right": "5px"
            },
            "QSlider::handle:horizontal": {
                "background-color": self.get_css("button"),
                "border": self.get_css("border"),
                "border-radius": "3px",
                "width": "12px",
                "height": "18px",
                "margin": "-7px 0"
            },
            "QSlider::groove:horizontal": {
                "background": self.get_css("border"),
                "height": "8px",
                "border-radius": "4px",
                "margin": "0"
            },
            "QScrollBar:vertical": {
                "border": "none",
                "background": self.get_pressed_css('border', darken=75),
                "width": "8px",
                "border-radius": "4px",
                "margin": "0px"
            },
            "QScrollBar::handle:vertical": {
                "background": self.get_css("border"),
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
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('main')
            },
            "QListWidget::item": {
                "background-color": self.get_pressed_css('svg', darken=150),
                "border": "none",
                "padding": "0px",
                "margin": "0px",
                "outline": "none"
            },
            "QListWidget::item:alternate": {
                "background": "transparent"
            },
            "QListWidget::item:selected": {
                "background": self.get_pressed_css('svg', darken=50),
                "border": "none",
                "outline": "none"
            },
            "QSpinBox": {
                "background-color": "transparent",
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('button'),
                "padding": "5px"
            },
            "QDoubleSpinBox": {
                "background-color": "transparent",
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('button'),
                "padding": "5px"
            },
            "QScrollArea": {
                "background-color": "transparent",
                "border": "none"
            },
            "QGroupBox": {
                "background-color": self.get_pressed_css('svg', darken=250, alpha=130),
                "border": self.get_css("border"),
                "border-radius": "5px",
                "margin-top": "1.0em"
            },
            "QGroupBox::title": {
                "background-color": "transparent",
                "subcontrol-position": "top left",
                "subcontrol-origin": "margin",
                "padding": "0 10px 0 10px",
                "margin-top": "-0.5em"
            },
            "TitleBar": {
                "background": "transparent",
                "border-bottom": self.get_css("border"),
                "border-bottom-left-radius": "0px",
                "border-bottom-right-radius": "0px"
            },
            "MessageContainer": {
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('main')
            },
            "WindowContainer": {
                "border": self.get_css("border", is_main_border=True),
                "border-radius": self.get_border_radius_css('main')
            },
            "MainWindowWidget": {
                "border": self.get_css("border", is_main_border=True),
                "border-radius": self.get_border_radius_css('main')
            },
            "SettingsWidget": {
                "border": "none",
                "border-radius": "10px"
            },
            "ContentWidget": {
                "background-color": "transparent"
            },
            "LabelSliderValue": {
                "background": "transparent",
                "border": self.get_css("border"),
                "border-radius": "3px"
            },
            "HelpWidget": {
                "background":"transparent",
                "border": self.get_css("border"),
                "border-radius": self.get_border_radius_css('main')
            },
            "LogArea": {
                "background": "transparent",
                "color": self.text_edit_color,
                "border": "none",
                "font-size": "15px"
            },
            "SidebarElement": {
                "background": "transparent",
                "color": self.get_text_css('text'),
                "border-radius": "none",
                "border": "none"
            },
            "SidebarElement::hover": {
                "border-top": self.get_css("border"),
                "border-bottom": self.get_css("border")
            },
            "SidebarElement[active='true']": {
                "background": self.get_pressed_css(for_type='svg', darken=100, alpha=100)
            },
            "ToolButton": {
                "background": "transparent",
                "border-radius": "none",
                "border": "none"
            },
            "VersionLabel": {
                "background": self.get_css("border"),
                "color": self.get_text_css('text'),
                "border-radius": "10px",
                "border": "none",
                "padding": "6px",
                "font-size": "13px"
            },
            "VersionLabel::hover": {
                "border": self.get_unique_border(px_value=2, method=self.text_edit_color)
            },
            "UpdateLabel": {
                "background": self.get_css("border"),
                "color": self.get_text_css('text'),
                "border-radius": "10px",
                "border": "none",
                "padding": "6px",
                "font-size": "14px"
            },
            "UpdateLabel::hover": {
                "border": self.get_unique_border(px_value=2, method=self.text_edit_color)
            },
            "UserProfileWidget": {
                "background-color": "transparent",
                "border": self.get_css("border"),
                "border-radius": "17px"
            },
            "UserProfileWidget::hover": {
                "border": self.get_css("border", px_value=2)
            },
            "ScriptStepFrame": {
                "border": self.get_css("border")
            },
            "CreateCommandsWidgets": {
                "background-color": "transparent"
            },
            "CreateRunWidgets": {
                "background-color": "transparent"
            },
            "PrimarySVGBtn": {
                "background-color": "transparent",
                "border": self.get_css("border")
            },
            "PrimarySVGBtn::hover": {
                "background-color": self.get_hover_css('button')
            },
            "CustomButton": {
                "background-color": self.get_css("button"),
                "border": self.get_css("border", is_btn_border=True),
                "border-radius": self.get_border_radius_css('button'),
                "padding-left": "8px",
                "padding-right": "8px"
            },
            "CustomButton:hover": {
                "background-color": self.get_hover_css('button')
            },
            "TitleBarBtn": {
                "background-color": "transparent",
                "border": "none",
                "border-radius": "0px"
            },
            "TitleBarBtn:hover": {
                "background-color": self.get_hover_css('button'),
                "border": "none"
            },
            "TitleBarCloseBtn": {
                "background-color": "transparent",
                "border": "none",
                "border-radius": "0px",
                "border-top-right-radius": self.get_border_radius_css('main'),
            },
            "TitleBarCloseBtn:hover": {
                "background-color": "#E76565",
                "border": "none"
            },
            "TitleBarCloseBtnV2": {
                "background-color": "transparent",
                "border": "1px solid transparent",
                "border-radius": self.get_border_radius_css('button')
            },
            "TitleBarCloseBtnV2:hover": {
                "background-color": "#E76565"
            },
            "ToggleVisiblePSWD": {
                "border": self.get_css('border'),
                "border-left": "none",
            },
            "FullWindowMode": {
                "border": "1px solid transparent",
                "border-radius": "0px"
            },
            "FullWindowMode_CloseBtn": {
                "border-radius": "0px",
                "background-color": "transparent",
                "border": "none"
            },
            "FullWindowMode_CloseBtn:hover": {
                "background-color": "#E76565"
            },
            "FullWindowMode_TitleBar": {
                "border-radius": "0px",
                "background": self.get_pressed_css('svg', darken=200),
                "border": "1px solid transparent"
            },
            "TitleBarLogin": {
                "background": "transparent"
            },
            "LoginContainer": {
                "border": self.get_css('border'),
                "border-radius": "20px"
            },
            "TitleBarV2": {
                "background": self.get_pressed_css('svg', darken=200),
                "border-top": self.get_css('border', is_main_border=True),
                "border-left": self.get_css('border', is_main_border=True),
                "border-right": self.get_css('border', is_main_border=True),
                "border-top-left-radius": self.get_border_radius_css('main'),
                "border-top-right-radius": self.get_border_radius_css('main')
            },
            "TransparentWidget": {
                "background": "transparent"
            },
            "FooterChangelog": {
                "background": self.get_pressed_css('svg', darken=250),
                "border-radius": self.get_border_radius_css('button'),
            },
            "ToastNotif": {
                "background": self.get_pressed_css('svg', darken=200, alpha=240),
                "border-radius": "10px",
            },
            "StackedWidgetPage": {
                "background-color": self.get_pressed_css(for_type='border', darken=250, alpha=150),
                "border-radius": self.get_border_radius_css('main')
            },
            "StackedWidget": {
                "background-color": "transparent"
            },
            "StackedWidgetContent": {
                "background-color": "transparent"
            },
            "GradientGroup": {
                "background-color": "transparent"
            },
            "TabPanel": {
                "background": "transparent"
            },
            "TabBtn": {
                "background": self.get_pressed_css(for_type='border', darken=200),
                "border": "none",
                "border-radius": "0px"
            },
            "TabBtn:hover": {
                "background": self.get_pressed_css(for_type='border', darken=160)
            },
            "TabBtn[active='true']": {
                "background": self.get_pressed_css(for_type='svg', darken=100),
                "border": self.get_css('border')
            },
        }
    
        custom_styles = self.load_custom_styles()

        base_styles.update(custom_styles)

        return base_styles
       
    def update_style_file(self, file_path: str = None):
        """
        Обновляет структуру одного файла стиля.
        Если file_path не указан — обновляется основной файл (self.color_settings_path).
        """
        if file_path is None:
            load_settings = False
            file_path = self.color_path
        else:
            load_settings = True

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current = json.load(f)
                self.styles = current

                if load_settings:
                    self.load_color_settings()
            except Exception as e:
                current = {}
        else:
            current = {}

        reference = self.reference_style()

        merged = self.merge_with_reference(reference)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            return False
        
    def update_all_styles(self, extension: str = ".json"):
        """
        Обновляет все файлы с заданным расширением в обеих папках пресетов:
        - bin/color_presets
        - user_settings/presets
        """
        folders = [
            self.base_presets
        ]

        updated_files = []

        for folder_path in folders:
            if not os.path.exists(folder_path):
                continue

            filenames = [f for f in os.listdir(folder_path) if f.endswith(extension)]
            for filename in filenames:
                full_path = os.path.join(folder_path, filename)
                if self.update_style_file(full_path):
                    updated_files.append(full_path)

        return updated_files
    
    def merge_with_reference(self, reference_style):
        """
        Полная синхронизация со reference_style.
        Все значения берутся из reference_style.
        current_style используется ТОЛЬКО как источник для последующего применения настроек цвета.
        """
        return dict(reference_style)
    
    def get_css(self, for_type="background", px_value=1, is_btn_border=False, is_main_border=False):
        """
        Хендлер для создания css на основе метода get_gradient_css:
        Генерирует CSS для градиента конкретного элемента
        Пример: self.get_gradient_css('background') if self.gradient_settings['background']['enabled'] else self.bg_color
        
        :param for_type: "background", "button", "border", "svg", Исходник цета.
        :param is_btn_border: True/False, Будет ли влиять флаг "Бордер на кнопке" на данный селектор
        """

        if for_type == "background":
            return self.get_gradient_css('background') if self.gradient_settings['background']['enabled'] else self.bg_color
        elif for_type == "button":
            return self.get_gradient_css('buttons') if self.gradient_settings['buttons']['enabled'] else self.btn_color
        elif for_type == "border":

            if is_btn_border:
                return (f"{px_value}px solid {self.get_gradient_css('borders')}" 
                    if self.gradient_settings['borders']['enabled'] else f"{px_value}px solid {self.border_color}"
                    ) if self.border_in_buttons else "none"
            elif is_main_border:
                return (f"{px_value}px solid {self.get_gradient_css('borders')}" 
                    if self.gradient_settings['borders']['enabled'] else f"{px_value}px solid {self.border_color}"
                    ) if self.border_in_main_window else "none"
            else:
                return f"{px_value}px solid {self.get_gradient_css('borders')}" if self.gradient_settings['borders'][
                    'enabled'] else f"{px_value}px solid {self.border_color}"

        elif for_type == "svg":
            return f"{self.get_gradient_css('svg')}" if self.gradient_settings['svg']['enabled'] else f"{self.svg_color}"
        else:
            raise ValueError(f"for_type must be 'background', 'button', 'border', 'svg', got '{for_type}'")
        
    def get_hover_css(self, for_type="background"):
        """
        Хендлер для создания css на основе метода get_hover_gradient_css:
        Генерирует CSS для градиента в состоянии :hover.
        Меняет местами color1 и color2.
        Если градиент отключен, возвращает сплошной цвет.

        :param for_type: "background", "button", "border", "svg", Исходник цета.
        """

        if for_type == "background":
            return self.get_hover_gradient_css('background')
        elif for_type == "button":
            return self.get_hover_gradient_css('buttons')
        elif for_type == "border":
            return self.get_hover_gradient_css('borders')
        elif for_type == "svg":
            return self.get_hover_gradient_css('svg')
        else:
            raise ValueError(f"for_type must be 'background', 'button', 'border', 'svg', got '{for_type}'")

    def get_pressed_css(self, for_type="background", darken=50, alpha=255):
        """
        Хендлер для создания css на основе метода get_pressed_gradient_css_rgba:
        Генерирует CSS для градиента.
        Затемняет оба цвета на заданное количество.
        Добавляет прозрачность если указана.
        Если градиент отключен, затемняет сплошной цвет.
        
        :param for_type: "background", "button", "border", "svg", Исходник цета.
        :param darken: Сила затемнения.
        :param alpha: Прозрачность. По умолчанию непрозрачный.
        """

        if for_type == "background":
            return self.get_pressed_gradient_css_rgba('background', darken, alpha)
        elif for_type == "button":
            return self.get_pressed_gradient_css_rgba('buttons', darken, alpha)
        elif for_type == "border":
            return self.get_pressed_gradient_css_rgba('borders', darken, alpha)
        elif for_type == "svg":
            return self.get_pressed_gradient_css_rgba('svg', darken, alpha)
        else:
            raise ValueError(f"for_type must be 'background', 'button', 'border', 'svg', got '{for_type}'")
        
    def get_border_radius_css(self, border_type="button"):
        """
        Возвращает "{self.border_btn_radius}px" если тип button, 
        иначе "{self.border_main_radius}px"

        :param border_type: "main", "button"

        """

        if border_type == "button":
            return f"{self.border_btn_radius}px"
        elif border_type == "main":
            return f"{self.border_main_radius}px"
        else:
            raise ValueError(f"border_type must be 'button' or 'main', got '{border_type}'")
        
    def get_text_css(self, text_type="text"):
        """
        Два типа текста для разнообразия.
        Возвращает переменную в зависимости от переданного типа.

        :param text_type: "text", "text_edit". Два типа текста для разнообразия.
        """

        if text_type == "text":
            return self.text_color
        elif text_type == "text_edit":
            return self.text_edit_color
        else:
            raise ValueError(f"text_type must be 'text' or 'text_edit', got '{text_type}'")
        
    def get_unique_border(self, for_type="border", px_value=1, method=None):
        if method is None:
            return
        
        if for_type == "border":
            return f"{px_value}px solid {method}"
        else:
            raise ValueError(f"for_type must be 'border' got '{for_type}'")
        
    def load_custom_styles(self):
        """
        Загружает и парсит JSON-файл с кастомными стилями.

        :return: словарь с вычисленными стилями
        """
        file_path = mygui_config.custom_selectors
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_styles = json.load(f)
        except Exception as e:
            print(f"Error loading custom selectors: {e}")
            return {}

        evaluated_styles = {}
        for selector, properties in raw_styles.items():
            if selector.startswith('_'):
                continue
                
            evaluated_styles[selector] = {}
            for prop, value in properties.items():
                evaluated_styles[selector][prop] = self._parse_style_value(value)
        
        return evaluated_styles
    
    def _parse_style_value(self, value):
        """
        Парсит одно значение из JSON и возвращает вычисленный результат.
        
        Поддерживаемые форматы:
        - Статические строки: "30px", "#ffffff"
        - Ссылки на переменные: "bg_color"
        - Вызовы хендлеров: "get_css('button')"
        - Вызовы с параметрами: "get_pressed_css('button', darken=30, alpha=150)"
        - Комбинации: "border_with_gradient('borders') if border_in_buttons else 'none'"
        
        :param value: строка из JSON
        :return: вычисленное значение
        """
        if not isinstance(value, str):
            # Если не строка — возвращаем как есть (число, bool и т.д.)
            return value
        
        # Если строка не содержит вызовов методов или переменных — возвращаем как есть
        # Простая проверка: есть ли в строке что-то похожее на вызов или переменную
        if not any(marker in value for marker in ['get_', 'gradient', 'bg_', 'btn_', 'text_', 'border_', 'radius', 'svg_']):
            return value
        
        try:
            # Создаем безопасный контекст для eval
            # Добавляем все ваши хендлеры и переменные в контекст
            context = {
                # Ваши хендлеры
                'get_css': self.get_css,
                'get_pressed_css': self.get_pressed_css,
                'get_hover_css': self.get_hover_css,
                'get_border_radius_css': self.get_border_radius_css,
                'get_text_css': self.get_text_css,
                'get_unique_border': self.get_unique_border,
                
                # Прямые переменные для удобства
                'bg_color': self.bg_color,
                'btn_color': self.btn_color,
                'text_color': self.text_color,
                'text_edit_color': self.text_edit_color,
                'border_color': self.border_color,
                'svg_color': self.svg_color,
                'border_btn_radius': self.border_btn_radius,
                'border_main_radius': self.border_main_radius,
                'border_in_buttons': self.border_in_buttons,
                'border_in_main_window': self.border_in_main_window,
                
                # Gradient settings для сложных условий
                'gradient_enabled_bg': self.gradient_settings['background']['enabled'],
                'gradient_enabled_btn': self.gradient_settings['buttons']['enabled'],
                'gradient_enabled_border': self.gradient_settings['borders']['enabled'],
                'gradient_enabled_svg': self.gradient_settings['svg']['enabled'],
            }
            
            # Выполняем выражение
            result = eval(value, {"__builtins__": {}}, context)
            return result
            
        except Exception as e:
            print(f"Error evaluating '{value}': {e}")
            return value
        
    def get_cursor_region(self, pos):
        """Определяем область курсора для изменения размера"""
        width = self.width()
        height = self.height()
        x, y = pos.x(), pos.y()
        
        if x <= self.margin and y <= self.margin:
            return "top-left"
        elif x >= width - self.margin and y <= self.margin:
            return "top-right"
        elif x <= self.margin and y >= height - self.margin:
            return "bottom-left"
        elif x >= width - self.margin and y >= height - self.margin:
            return "bottom-right"
        elif x <= self.margin:
            return "left"
        elif x >= width - self.margin:
            return "right"
        elif y <= self.margin:
            return "top"
        elif y >= height - self.margin:
            return "bottom"
        else:
            return "center"

    def title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            window_pos = self.mapFromGlobal(global_pos)
            region = self.get_cursor_region(window_pos)

            if region == "center":
                self.dragging_maximized = True
                self.drag_start_pos = global_pos
                self.drag_start_geometry = self.geometry()
                self._drag_click_offset = None
                event.accept()
                return

            if region in ["top", "top-left", "top-right", "left", "right"]:
                self.drag_direction = region
                self.dragging = True
                self.drag_position = global_pos
                self.initial_geometry = self.geometry()
            elif region == "center":
                self.drag_pos = global_pos - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        global_pos = event.globalPosition().toPoint()
        window_pos = self.mapFromGlobal(global_pos)
        region = self.get_cursor_region(window_pos)

        if hasattr(self, 'dragging_maximized') and self.dragging_maximized:
            if event.buttons() == Qt.MouseButton.LeftButton:
                if self._drag_click_offset is None:
                    rel_x = (self.drag_start_pos.x() - self.drag_start_geometry.x()) / self.drag_start_geometry.width()
                    rel_y = (self.drag_start_pos.y() - self.drag_start_geometry.y()) / self.drag_start_geometry.height()
                    self._drag_click_offset = (rel_x, rel_y)
                
                current_geo = self.geometry()

                new_x = global_pos.x() - int(current_geo.width() * self._drag_click_offset[0])
                new_y = global_pos.y() - int(current_geo.height() * self._drag_click_offset[1])
                
                self.move(new_x, new_y)

                self.drag_pos = global_pos - self.frameGeometry().topLeft()
                self.dragging_maximized = False
                self._drag_click_offset = None
            return

        cursor_map = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "center": Qt.CursorShape.ArrowCursor
        }
        self.setCursor(cursor_map.get(region, Qt.CursorShape.ArrowCursor))

        if self.dragging and self.drag_direction in ["top", "top-left", "top-right", "left", "right"]:
            self.handle_resize(global_pos)
            event.accept()
        elif self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = global_pos - self.drag_pos
            self.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        self.dragging = False
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.dragging_maximized = False
        self.drag_start_pos = None
        self.drag_start_geometry = None
        self._drag_click_offset = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.drag_direction = self.get_cursor_region(pos)

            if self.drag_direction != "center":
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint()
                self.initial_geometry = self.geometry()
                self.reached_min_size = False
                
    def mouseMoveEvent(self, event: QMouseEvent):      
        pos = event.position().toPoint()
        region = self.get_cursor_region(pos)
        
        cursor_map = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "center": Qt.CursorShape.ArrowCursor
        }
        self.setCursor(cursor_map.get(region, Qt.CursorShape.ArrowCursor))
        
        if self.dragging and self.drag_direction != "center":
            self.handle_resize(event.globalPosition().toPoint())

    def enterEvent(self, event):
        """При входе в окно устанавливаем правильный курсор"""
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        """При выходе из окна сбрасываем курсор"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def handle_resize(self, global_pos):
        """Обработка изменения размера с отслеживанием минимального размера"""    
        delta = global_pos - self.drag_position
        new_geometry = QRect(self.initial_geometry)

        old_geometry = QRect(new_geometry)
        
        # Применяем изменения
        if "left" in self.drag_direction:
            new_geometry.setLeft(self.initial_geometry.left() + delta.x())
        
        if "right" in self.drag_direction:
            new_geometry.setRight(self.initial_geometry.right() + delta.x())
        
        if "top" in self.drag_direction:
            new_geometry.setTop(self.initial_geometry.top() + delta.y())
        
        if "bottom" in self.drag_direction:
            new_geometry.setBottom(self.initial_geometry.bottom() + delta.y())

        content_min_width = self.minimum_size.width() + 20  # + отступы
        content_min_height = self.minimum_size.height() + 20
        
        will_shrink = (new_geometry.width() < old_geometry.width() or 
                      new_geometry.height() < old_geometry.height())
        
        reached_min_width = new_geometry.width() <= content_min_width
        reached_min_height = new_geometry.height() <= content_min_height
        
        # Если пытаемся уменьшить, но достигли минимального размера - блокируем
        if will_shrink and (reached_min_width or reached_min_height):
            # Не применяем изменения - оставляем старый размер
            self.reached_min_size = True
            return

        # Если изменения допустимы - применяем
        self.setGeometry(new_geometry)
        self._normal_geometry = new_geometry
        self.reached_min_size = False
        
        if new_geometry.width() > 200 and new_geometry.height() > 200:
            self.setGeometry(new_geometry)

    def show_message(self, message):
        if self.main:
            self.main.show_toast(message)
        else:
            print(message)
    