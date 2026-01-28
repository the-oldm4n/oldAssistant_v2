import json
import os
import subprocess
from threading import Thread
from queue import Queue
import wmi
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, \
    QDialog, QLabel, QGridLayout, QStackedWidget, QSizePolicy, QTextEdit, QApplication
from PySide6.QtCore import Qt, QPoint, QSize, QPropertyAnimation, QRect, QTimer, QTime, QEasingCurve

from bin.apply_color_methods import main_apply_colors
from bin.audio_control import controller
from bin.custom_svg_widget import CustomSvgWidget
from bin.custom_widgets import CustomToggleSimple
from bin.frosted_widget import SnowOverlay
from bin.function_list_main import shutdown_windows
from bin.lists import fonts_list
from bin.sensors_monitor import SensorTab
from bin.signals import color_signal, widget_btns_signal
from bin.toggle_mute_discord import ToggleMuteDiscord
from logging_config import debug_logger
from path_builder import get_path


class WindowStateManager:
    def __init__(self, config_path=get_path("user_settings", "widget_state.json")):
        self.config_path = config_path
        self.base_keys = [
            "window_position",
            "window_size", 
            "delay",
            "is_autohide",
            "is_compact",
            "is_pinned",
            "is_locked",
            "is_snow",
            "buttons",
            "font_family",
            "default_buttons",
            "custom_buttons"
        ]
        self.default_state = {
            "window_position": {"x": 100, "y": 100},
            "window_size": {"width": 310, "height": 350},
            "delay": 5,
            "is_autohide": False,
            "is_compact": False,
            "is_pinned": False,
            "is_locked": False, 
            "is_snow": True
        }
        self.save_state(self.load_state())

        # Создаем файл при инициализации, если его нет
        if not os.path.exists(self.config_path):
            self.save_state(self.default_state)

    def get_default_value(self, key):
        """Возвращает значение по умолчанию для ключа"""
        defaults = {
            "window_position": {"x": 100, "y": 100},
            "window_size": {"width": 310, "height": 350},
            "delay": 5,
            "is_autohide": False,
            "is_compact": False,
            "is_pinned": False,
            "is_locked": 0,
            "is_snow": False,
            "buttons": {},
            "font_family": "nova_round",
            "default_buttons": {},
            "custom_buttons": []
        }
        return defaults.get(key, None)

    def load_state(self):
        """Загружает состояние, добавляя отсутствующие поля из default_state"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}

        cleaned_data = {}
        for key in self.base_keys:
            if key in data:
                cleaned_data[key] = data[key]
            else:
                cleaned_data[key] = self.get_default_value(key)    

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

        return cleaned_data

    def save_state(self, state):
        """Сохраняет состояние окна в JSON файл"""
        try:
            # Создаем папку, если ее нет
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
        except IOError as e:
            debug_logger.error(f"[PANEL] Ошибка сохранения состояния: {e}")

    def save_window_state(self, window, pos_x=None, pos_y=None):
        """Специальный метод для сохранения состояния QWidget"""
        # Сначала загружаем существующие данные, чтобы не потерять кнопки
        existing_data = {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except:
            pass  # Если файла нет или ошибка, создаем новый
        
        if pos_x and pos_y:
            state = {
                "window_position": {
                    "x": pos_x,
                    "y": pos_y
                }
            }
            
        else:
            state = {
                "window_position": {
                    "x": window.pos().x(),
                    "y": window.pos().y()
                },
                "window_size": {
                    "width": window.width(),
                    "height": window.height()
                },
                "is_compact": getattr(window, 'is_compact', False),
                "is_pinned": getattr(window, 'is_pinned', False),
                "is_locked": getattr(window, 'is_locked', 0)
            }

        # Объединяем с существующими данными (кнопки и др.)
        existing_data.update(state)

        self.save_state(existing_data)

    def apply_state(self, window):
        """Применяет сохраненное состояние к окну"""
        state = self.load_state()

        window.move(QPoint(state["window_position"]["x"],
                           state["window_position"]["y"]))
        window.resize(QSize(state["window_size"]["width"],
                            state["window_size"]["height"]))

        # Устанавливаем дополнительные состояния
        window.is_compact = state["is_compact"]
        window.is_pinned = state["is_pinned"]
        window.is_locked = state["is_locked"]

        return state
    
    def update_value(self, key, value):
        """Универсальный метод для обновления любого значения"""
        state = self.load_state()
        state[key] = value
        self.save_state(state)
        
    def set_is_snow(self, value):
        """Устанавливает новое значение для is_snow"""
        state = self.load_state()
        state["is_snow"] = bool(value)
        self.save_state(state)

    def get_is_snow(self):
        """Получает текущее значение is_snow"""
        state = self.load_state()
        value = state.get("is_snow", False)
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ("false"):
                return False
            elif value_lower in ("true"):
                return True
        
        return bool(value)



class SmartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        widget_btns_signal.buttons_updated.connect(self.repaint_main_buttons)
        self.buttons_data = {}
        self.player_buttons = {}
        self.title_buttons = {}
        self.is_paused = False
        self.is_muted = False
        self.snow_on_label = None
        self.is_height_compact = False
        color_signal.color_changed.connect(self.update_colors)
        self.notes_file = get_path("user_settings", "notes.txt")
        self.widget_state = get_path("user_settings", "widget_state.json")

        # Пути к иконкам
        self.camera_path = get_path("bin", "icons", "camera.svg")
        self.power_path = get_path("bin", "icons", "power.svg")
        self.open_main_path = get_path("bin", "icons", "open_main.svg")
        self.settings_path = get_path("bin", "icons", "settings.svg")
        self.shortcut_path = get_path("bin", "icons", "shortcut.svg")
        self.next_track = get_path("bin", "icons", "next.svg")
        self.prev_track = get_path("bin", "icons", "prev.svg")
        self.pause_track = get_path("bin", "icons", "pause.svg")
        self.play_track = get_path("bin", "icons", "play.svg")
        self.pin_path = get_path("bin", "icons", "pin.svg")
        self.lock_path = get_path("bin", "icons", "lock.svg")
        self.partial_lock_path = get_path("bin", "icons", "partial_lock.svg")
        self.unlock_path = get_path("bin", "icons", "unlock.svg")
        self.close_path = get_path("bin", "icons", "cancel.svg")
        self.resize_path = get_path("bin", "icons", "resize.svg")
        self.mic_on_path = get_path("bin", "icons", "mic_on.svg")
        self.mic_off_path = get_path("bin", "icons", "mic_off.svg")
        self.youtube_path = get_path("bin", "icons", "logo-youtube.svg")
        self.ohm_path = self.assistant.ohm_path
        self.ohm_namespace = "root\\OpenHardwareMonitor"
        self.cpu_path = get_path("bin", "icons", "hardware-monitor", "cpu.svg")
        self.gpu_path = get_path("bin", "icons", "hardware-monitor", "gpu.svg")
        self.ram_path = get_path("bin", "icons", "hardware-monitor", "ram.svg")
        self.rate_path = get_path("bin", "icons", "hardware-monitor", "rate.svg")
        self.thermo_path = get_path("bin", "icons", "hardware-monitor", "thermo.svg")
        self.percent_path = get_path("bin", "icons", "hardware-monitor", "percent.svg")
        self.power_monitor_path = get_path("bin", "icons", "hardware-monitor", "power.svg")
        self.hardware_monitor_svg = None
        self.icon_paths = {
            'cpu': self.cpu_path,
            'gpu': self.gpu_path,
            'ram': self.ram_path,
            'thermo': self.thermo_path,
            'percent': self.percent_path,
            'power': self.power_monitor_path,
            'clock': self.rate_path
        }
        # Стили
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()

        # Таймер времени
        self.timer_clock = QTimer(self)
        self.timer_clock.timeout.connect(self.update_time)
        self.timer_clock.start(1000)

        # Менеджер состояния
        self.state_manager = WindowStateManager()
        saved_state = self.state_manager.apply_state(self)
        self.is_compact = saved_state["is_compact"]
        self.is_pinned = saved_state["is_pinned"]
        self.is_snow = saved_state["is_snow"]
        self.is_autohide = saved_state["is_autohide"]
        self.delay = saved_state["delay"] * 1000
        self.is_locked = 0
        self.temp_delay = 1
        self.check_widget_pos()

        # Шрифт
        self.fonts_list = fonts_list

        self.init_ui()

        self.load_font_clock()

        # Флаги окна
        base_flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.is_pinned:
            base_flags |= Qt.WindowType.WindowStaysOnTopHint
            self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
        else:
            base_flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self.style_manager.apply_color_svg(self.pin_svg, strength=0.95, specified_color="#ffffff")
        self.setWindowFlags(base_flags)

        self.style_manager.apply_color_svg(self.resize_svg, strength=0.95, specified_color="#FFFFFF")
        self.style_manager.apply_color_svg(self.close_svg, strength=0.95, specified_color="#FFFFFF")

        # Для перетаскивания
        self.old_pos = None
        self.is_dragging = False
        self.current_position = {"x": 0, "y": 0}

        self.load_notes()
        self.animation = None

        # Обновляем время
        self.update_time()
        self.update_ui_for_mode()
        self.update_snow_state()

        self.init_delay_timers()
        QTimer.singleShot(500, lambda: (
            self.hide_timer.start(self.delay) 
            if hasattr(self, 'delay') else None
        ))
        
    def update_snow_state(self):
        """Обновляет состояние снега через show/hide"""
        if self.is_snow:
            if self.snow_on_label is None:
                self.create_snow()
            else:
                self.snow_on_label.show()
        else:
            if self.snow_on_label is not None:
                self.snow_on_label.hide()

    def create_snow(self):
        """Создает снежный эффект (только один раз)"""
        if self.snow_on_label is not None:
            return  # Уже создан
        
        self.snow_on_label = SnowOverlay(
            parent=self.main_container,
            snowflake_count=20,
            fall_speed=0.4,
            flake_size_min=1,
            flake_size_max=3,
            change_interval_sec=60,
            change_probability=0.5,
            preset_type="panel"
        )
        self.snow_on_label.resize(self.main_container.size())
        self.snow_on_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.snow_on_label.raise_()
        self.snow_on_label.setSnowColor(self.style_manager.get_snow_color(), white_balance=40)
        
        # Изначально показываем или скрываем в зависимости от состояния
        if self.is_snow:
            self.snow_on_label.show()
        else:
            self.snow_on_label.hide()

    def remove_snow(self):
        """Теперь просто скрываем снег"""
        if self.snow_on_label is not None:
            self.snow_on_label.hide()

    def toggle_snow(self):
        """Переключает состояние снега"""
        self.is_snow = self.state_manager.get_is_snow()
        self.update_snow_state()

    # Упрощенная версия без лишних проверок
    def set_snow_enabled(self, enabled):
        """Включает/выключает снег"""
        self.is_snow = enabled
        self.state_manager.set_is_snow(self.is_snow)
        
        if self.snow_on_label is not None:
            if enabled:
                self.snow_on_label.show()
            else:
                self.snow_on_label.hide()

    def init_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent")

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        # Основной контент
        self.main_container = QWidget()
        self.main_container.setObjectName("MainContainer")
        self.background_color = self.style_manager.get_transparent_background_from_border(opacity=210, darken_factor=600)
        self.main_container.setStyleSheet(f"""
                #MainContainer {{
                    background: {self.background_color};
                    border-radius: 10px;
                }}
            """)
        
        self.setMouseTracking(True)
        self.main_container.setMouseTracking(True)

        self.content_layout = QVBoxLayout(self.main_container)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(5)

        self.title_bar = self.create_title_bar()
        self.content_layout.addWidget(self.title_bar)

        # Часы
        self.clock_mini = QLabel()
        self.clock_mini.setObjectName("clock_mini")
        self.clock_mini.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.clock_mini)

        self.toggles_layout = QHBoxLayout()

        self.toggle_hide_btns = CustomToggleSimple()
        self.toggle_hide_btns.setToolTip("Автоматически прятать кнопки")
        self.toggle_hide_btns.setChecked(self.is_autohide)
        self.toggle_hide_btns.stateChanged.connect(self.toggle_autohide)
        self.toggles_layout.addWidget(self.toggle_hide_btns, alignment=Qt.AlignmentFlag.AlignLeft)

        self.toggles_layout.addStretch()

        self.hide_btns = CustomToggleSimple()
        self.hide_btns.setToolTip("Показать/свернуть кнопки")
        self.hide_btns.setChecked(self.is_height_compact)
        self.hide_btns.stateChanged.connect(self.hide_main_btns)
        self.toggles_layout.addWidget(self.hide_btns, alignment=Qt.AlignmentFlag.AlignRight)

        self.content_layout.addLayout(self.toggles_layout)

        # Аудио
        self.audio_widget = self.create_audio_controls()
        self.content_layout.addWidget(self.audio_widget, alignment=Qt.AlignmentFlag.AlignCenter)   

        self.content_layout.addStretch()

        # Кнопки
        self.buttons_widget = self.create_main_buttons()
        self.content_layout.addWidget(self.buttons_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Вкладки (по умолчанию скрыты в компактном режиме)
        self.tab_widget = self.create_tabs_widget()
        self.content_layout.addWidget(self.tab_widget)

        self.layout().addWidget(self.main_container)

        self.switch_tab(1)
        if not self.is_compact:
            self.switch_tab(1)

    def init_delay_timers(self):
        # Таймер для автоскрытия
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.auto_hide_buttons)
        
        # Флаг чтобы не скрывать при активном использовании
        self.mouse_over_widget = False

    def enterEvent(self, event):
        """Курсор вошел в область виджета"""
        self.mouse_over_widget = True
        self.hide_timer.stop()  # Останавливаем отсчет
        
        # Показываем кнопки если они скрыты (компактный режим)
        if self.is_height_compact:
            self.hide_main_btns()  # Разворачиваем панель
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Курсор вышел из области виджета"""
        self.mouse_over_widget = False
        
        # Запускаем таймер автоскрытия если включено
        if (self.is_autohide and 
            not self.is_height_compact and 
            self.delay > 0):  # Проверяем что задержка > 0
            
            self.hide_timer.start(self.delay)
        
        super().leaveEvent(event)

    def update_delay(self):
        state = self.state_manager.load_state()
        self.delay = state["delay"] * 1000

        self.is_autohide = (self.delay > 0)
        
        if not self.is_autohide:
            self.hide_timer.stop()
        elif self.hide_timer.isActive():
            self.hide_timer.start(self.delay)

    def toggle_autohide(self):
        if self.delay <= 0:
            self.is_autohide = False
        if not self.is_autohide:
            self.delay = self.temp_delay * 1000
            self.is_autohide = True
        else:
            if self.delay > 0:
                self.temp_delay = self.delay / 1000
            self.delay = 0
            self.is_autohide = False
        self.state_manager.update_value("is_autohide", self.is_autohide)
        self.state_manager.update_value("delay", self.delay / 1000)

    def create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("TitleBarPanel")
        title_bar.setFixedHeight(25)
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.clock_widget = QWidget()
        self.clock_widget.setStyleSheet("background: transparent;")
        clock_layout = QHBoxLayout(self.clock_widget)
        clock_layout.setContentsMargins(0, 0, 0, 0)

        self.clock_title = QLabel()
        self.clock_title.setObjectName("clock_title")
        self.clock_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        clock_layout.addWidget(self.clock_title)
        layout.addWidget(self.clock_widget)
        layout.addStretch()

        # Кнопки
        self.title_config = {
            "pin_btn": {"icon": self.pin_path, 'tooltip': 'Поверх других окон', "action": self.pin_widget},
            "lock_btn": {"icon": self.unlock_path, 'tooltip': 'Запретить перетаскивание', "action": self.lock_state},
            "resize_btn": {"icon": self.resize_path, 'tooltip': 'Компактный режим', "action": self.resize_widget},
            "close_btn": {"icon": self.close_path, 'tooltip': 'Закрыть', "action": self.close},
        }

        for btn_name, config in self.title_config.items():
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setToolTip(config['tooltip'])
            self.back_btn_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=150)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {self.back_btn_color};
                    border-radius: 5px;
                }}
            """)
            svg = CustomSvgWidget(config['icon'], btn)
            svg.setFixedSize(14, 14)
            svg.move(2, 2)
            self.title_buttons[btn_name] = {'button': btn, 'svg': svg}
            self.style_manager.apply_color_svg(svg, strength=0.90)
            btn.clicked.connect(config['action'])
            svg_attr_name = btn_name.replace('_btn', '')
            setattr(self, svg_attr_name + "_svg", svg)
            setattr(self, btn_name, btn)
            layout.addWidget(btn)

        return title_bar

    def create_main_buttons(self, vertical=False):
        self.btns_panel_widget = QWidget()
        self.btns_panel_widget.setStyleSheet("background: transparent;")
        layout_class = QVBoxLayout if vertical else QHBoxLayout
        buttons_layout = layout_class(self.btns_panel_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)

        self.buttons_layout = buttons_layout
        self.buttons_widget = self.btns_panel_widget
        self.buttons_visible = True

        # Стандартные кнопки
        buttons_config = {
            'turnoff_check': {
                'icon': self.power_path,
                'tooltip': 'Выключить Компьютер',
                'action': self.shutdown_system
            },
            'settings_check': {
                'icon': self.settings_path,
                'tooltip': 'Открыть настройки',
                'action': self.open_settings
            },
            'screenshot_check': {
                'icon': self.camera_path,
                'tooltip': 'Скриншот области',
                'action': self.assistant.capture_area
            },
            'open_youtube': {
                'icon': self.youtube_path,
                'tooltip': 'Запустить YouTube',
                'action': lambda: self.assistant.start_default_command("ютуб", "open", "url")
            },
            'microphone_check': {
                'icon': self.mic_on_path,
                'tooltip': 'Переключить мут в Discord',
                'action': self.toggle_mute
            },
            'links_check': {
                'icon': self.shortcut_path,
                'tooltip': 'Открыть папку с ярлыками',
                'action': self.assistant.open_folder_shortcuts
            },
            'resize_check': {
                'icon': self.open_main_path,
                'tooltip': 'Развернуть основное окно',
                'action': self.open_main_window
            }
        }

        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            buttons_order = settings_data.get("buttons", {})
            custom_buttons = settings_data.get("custom_buttons", [])
            
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка чтения настроек: {e}")
            buttons_order = {}
            custom_buttons = []

        # Добавляем кастомные кнопки в buttons_config
        for custom_btn_data in custom_buttons:
            custom_id = custom_btn_data['id']
            checkbox_key = f"custom_{custom_id}"

            def create_action(data):
                name = data['name_command']
                move = data.get('move_command', 'open')
                cmd_type = data['type_command']
                return lambda: self.assistant.start_default_command(name, move, cmd_type)
            
            buttons_config[checkbox_key] = {
                'icon': custom_btn_data['icon_path'],
                'tooltip': custom_btn_data['name'],
                'action': create_action(custom_btn_data.copy()),
                'is_custom': True,
                'custom_data': custom_btn_data
            }

        # Создаем кнопки в порядке из buttons_order
        for checkbox_key, is_visible in buttons_order.items():
            if not is_visible:
                continue
                
            if checkbox_key not in buttons_config:
                continue
                
            config = buttons_config[checkbox_key]
            btn = QPushButton()
            btn.setObjectName("BTNonPanel")
            btn.setFixedSize(40, 40)
            btn.setToolTip(config['tooltip'])
            
            self.back_btn_color = self.style_manager.get_transparent_background_from_border(
                opacity=220, darken_factor=200
            )
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {self.back_btn_color};
                    border-radius: 5px;
                }}
            """)
            
            svg = CustomSvgWidget(config['icon'], btn)
            svg.setFixedSize(30, 30)
            svg.move(5, 5)
            
            # Сохраняем ссылку
            btn_key = checkbox_key.replace('_check', '_btn') if not checkbox_key.startswith('custom_') else f'custom_{checkbox_key.replace("custom_", "")}_btn'
            self.buttons_data[btn_key] = {'button': btn, 'svg': svg}
            
            self.style_manager.apply_color_svg(svg, strength=0.90)
            btn.clicked.connect(config['action'])
            setattr(self, btn_key, btn)
            buttons_layout.addWidget(btn)

        if vertical:
            buttons_layout.addStretch()

        return self.btns_panel_widget

    def create_audio_controls(self):
        widget = QWidget()
        widget.setObjectName("AudioPlayerWidget")
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(0)

        player_config = {
            'prev_btn': {'icon': self.prev_track, 'tooltip': 'Предыдущий трек', 'action': self.prev_track_action},
            'pause_btn': {'icon': self.pause_track, 'tooltip': 'Пауза', 'action': self.pause_track_action},
            'next_btn': {'icon': self.next_track, 'tooltip': 'Следующий трек', 'action': self.next_track_action}
        }

        layout.addStretch()
        for btn_name, config in player_config.items():
            btn = QPushButton()
            btn.setFixedSize(22, 20)
            btn.setToolTip(config['tooltip'])
            self.back_btn_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=200)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {self.back_btn_color};
                    border-radius: 5px;
                }}
            """)
            svg = CustomSvgWidget(config['icon'], btn)
            svg.setFixedSize(22, 20)
            svg.move(0, 0)
            self.player_buttons[btn_name] = {'button': btn, 'svg': svg}
            self.style_manager.apply_color_svg(svg, strength=0.90)
            btn.clicked.connect(config['action'])
            setattr(self, btn_name, btn)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def create_tabs_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Кнопки вкладок
        tab_buttons = QWidget()
        tab_buttons_layout = QHBoxLayout(tab_buttons)
        tab_buttons_layout.setContentsMargins(5, 0, 5, 0)
        tab_buttons_layout.setSpacing(5)

        self.btn_sensors = QPushButton("Датчики")
        self.btn_notes = QPushButton("Заметки")

        tab_style = """
            QPushButton {
                background: rgba(50, 50, 50, 150);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
                font-size: 15px;
            }
            QPushButton:hover {
                background: rgba(70, 70, 70, 200);
            }
            QPushButton:pressed {
                background: rgba(40, 110, 230, 200);
            }
        """
        for btn in [self.btn_sensors, self.btn_notes]:
            btn.setStyleSheet(tab_style)
            btn.setCheckable(True)
            btn.setFixedHeight(25)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        tab_buttons_layout.addWidget(self.btn_sensors)
        tab_buttons_layout.addWidget(self.btn_notes)

        # Контент вкладок
        self.tab_content = QStackedWidget()
        self.tab_content.setStyleSheet("background: transparent; padding: 0 0 20px 0;")

        # Вкладка датчиков
        self.sensors_tab = SensorTab(
            icon_paths=self.icon_paths,
            ohm_path=self.ohm_path
        )
        self.tab_content.addWidget(self.sensors_tab)

        self.sensors_tab.showEvent = self._on_sensor_tab_show
        self.sensors_tab.hideEvent = self._on_sensor_tab_hide

        # Вкладка заметок
        self.notes_tab = QTextEdit("Тут можно писать заметки")
        self.notes_tab.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.notes_tab.setStyleSheet("""
            QTextEdit {
                border: none;
                font-size: 15px;
                color: white;
            }
        """)
        self.tab_content.addWidget(self.notes_tab)

        # Таймер автосохранения
        self.notes_save_timer = QTimer(self)
        self.notes_save_timer.setSingleShot(True)
        self.notes_save_timer.timeout.connect(self.save_notes)
        self.notes_tab.textChanged.connect(self.start_notes_save_timer)

        layout.addWidget(tab_buttons)
        layout.addWidget(self.tab_content)

        self.btn_sensors.clicked.connect(lambda: self.switch_tab(0))
        self.btn_notes.clicked.connect(lambda: self.switch_tab(1))

        return widget

    def relayout_buttons(self, vertical=False):
        """Перестраивает layout кнопок между горизонтальным и вертикальным расположением"""
        try:
            content_layout = self.content_layout
            index = content_layout.indexOf(self.buttons_widget)

            if index != -1:
                item = content_layout.takeAt(index)
                if item:
                    old_widget = item.widget()
                    if old_widget:
                        old_widget.deleteLater()
            self.buttons_widget = self.create_main_buttons(vertical=vertical)

            audio_index = content_layout.indexOf(self.audio_widget)
            if audio_index != -1:
                # Вставляем после audio_widget
                content_layout.insertWidget(audio_index + 1, self.buttons_widget,
                                            alignment=Qt.AlignmentFlag.AlignCenter)
            else:
                content_layout.addWidget(self.buttons_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в relayout_buttons: {e}")

    # Методы для перемещения окна
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not getattr(self, 'is_locked', 0):
            self.old_pos = event.globalPos()
            self.is_dragging = False

            self.is_autohide = False
            self.hide_timer.stop()

            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if hasattr(self, 'old_pos') and self.old_pos and not getattr(self, 'is_locked', 0):
                delta = event.globalPos() - self.old_pos

                # Если движение достаточно большое - начинаем перетаскивание
                if delta.manhattanLength() > 2:
                    new_pos = self.pos() + delta
                    self.move(new_pos)
                    self.old_pos = event.globalPos()
                    
                    self.current_position = {"x": new_pos.x(), "y": new_pos.y()}
                    self.is_dragging = True
                    
                    event.accept()
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.finish_dragging()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def finish_dragging(self):
        """Завершает перетаскивание"""
        if self.is_dragging:

            state = self.state_manager.load_state()
            state["window_position"] = self.current_position
            self.state_manager.save_state(state)

        self.is_dragging = False
        self.old_pos = None

        QTimer.singleShot(100, lambda: setattr(self, 'is_autohide', True))
        if not self.is_height_compact:
            QTimer.singleShot(150, self.start_hide_countdown)
            
    def check_widget_pos(self, min_visibility_percent=15):
        """Проверяет положение виджета используя сохраненные данные"""
        try:
            # Загружаем сохраненное состояние
            state = self.state_manager.load_state()
            saved_x = state["window_position"]["x"]
            saved_y = state["window_position"]["y"]
            saved_width = state["window_size"]["width"]
            saved_height = state["window_size"]["height"]
            
            debug_logger.info(f"[PANEL] Сохраненная позиция: ({saved_x}, {saved_y})")
            debug_logger.info(f"[PANEL] Сохраненный размер: {saved_width}x{saved_height}")
            
            # Создаем прямоугольник виджета на основе сохраненных данных
            widget_rect = QRect(saved_x, saved_y, saved_width, saved_height)
            
            # Проверяем на всех экранах
            screens = QApplication.screens()
            max_visibility = 0
            best_screen = None
            
            for screen in screens:
                screen_geometry = screen.availableGeometry()
                debug_logger.info(f"[PANEL] Экран: {screen_geometry}")
                
                if screen_geometry.intersects(widget_rect):
                    # Вычисляем сколько процентов виджета видно
                    intersection = screen_geometry.intersected(widget_rect)
                    visible_area = intersection.width() * intersection.height()
                    total_area = saved_width * saved_height
                    visibility_percent = (visible_area / total_area) * 100
                    
                    debug_logger.info(f"[PANEL] Видимость на экране: {visibility_percent:.1f}%")
                    
                    # Запоминаем максимальную видимость
                    if visibility_percent > max_visibility:
                        max_visibility = visibility_percent
                        best_screen = screen
            
            debug_logger.info(f"[PANEL] Максимальная видимость виджета: {max_visibility:.1f}%")
            
            # Проверяем достаточно ли видно
            if max_visibility < min_visibility_percent:
                debug_logger.info(f"[PANEL] Видимость менее {min_visibility_percent}%! Центрируем...")
                self.center_widget()
                return False
            else:
                debug_logger.info(f"[PANEL] Виджет в пределах экрана (видимость: {max_visibility:.1f}%)")
                return True
                
        except Exception as e:
            debug_logger.info(f"[PANEL] Ошибка при проверке положения виджета: {e}")
            return False

    def center_widget(self):
        """Центрирует окно на экране"""
        # Сохраняем новую позицию
        self.state_manager.save_window_state(self, pos_x=100, pos_y=100)
        self.state_manager.apply_state(self)

    def load_window_state(self):
        """Загружает состояние окна из JSON"""
        state = self.state_manager.load_state()
        pos = state["window_position"]
        size = state["window_size"]
        self.move(QPoint(pos["x"], pos["y"]))
        self.resize(QSize(size["width"], size["height"]))

    def get_font_size_for_family(self, font_family):
        """Возвращает размер шрифта в зависимости от семейства"""
        font_sizes = {
            'digital': '16px',
            'grape_nuts': '26px',
            'cinzel_decorative': '26px',
            'michroma': '20px',
            'bruno_ace': '20px',
            'jacquard': '40px',
            'nova_round': '23px',
            'orbitron': '20px',
            'special_elite': '26px',
            'metamorphous': '24px',
        }

        # Ищем подходящий размер
        font_lower = font_family.lower()
        for font_name, size in font_sizes.items():
            if font_name in font_lower:
                return size

        return '18px'

    def apply_font_styles(self, font_family, font_name):
        """Применить шрифт с индивидуальным размером для каждого семейства"""
        font_size = self.get_font_size_for_family(font_name)

        debug_logger.info(f"[PANEL] Применение шрифта: {font_family} с размером: {font_size}")

        styles = f"""
            /* Основные часы */
            #clock_mini {{
                font-family: "{font_family}";
                font-size: {font_size};
                font-weight: normal;
                padding: 0px;
                background: transparent;
            }}

            /* Заголовок часов */
            #clock_title {{
                font-family: "{font_family}";
                font-size: {font_size};
                font-weight: normal;
                padding: 0px 5px, 0px 5px;
                background: transparent;
            }}
        """

        if hasattr(self, 'clock_mini') and not self.clock_mini.objectName():
            self.clock_mini.setObjectName("clock_mini")

        if hasattr(self, 'clock_title') and not self.clock_title.objectName():
            self.clock_title.setObjectName("clock_title")

        if hasattr(self, 'clock_widget') and not self.clock_widget.objectName():
            self.clock_widget.setObjectName("clock_widget")

        if hasattr(self, 'clock_mini'):
            self.clock_mini.setStyleSheet(styles)

        if hasattr(self, 'clock_title'):
            self.clock_title.setStyleSheet(styles)

    def load_font_clock(self):
        try:
            state = self.state_manager.load_state()
            font_name = state.get("font_family", "digital")

            if font_name in self.fonts_list:
                font_path = self.fonts_list[font_name]
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        font_family_name = font_families[0]
                        self.apply_font_styles(font_family_name, font_name)
                        debug_logger.info(f"[PANEL] Шрифт '{font_name}' успешно загружен и применен")
                        return True

        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в load_font_clock: {e}")
            self.apply_fallback_styles()
        return False

    def apply_fallback_styles(self):
        """Fallback стили"""
        fallback_styles = """
            #clock_mini {
                font-family: "Arial", "Helvetica", sans-serif;
                font-size: 20px;
                font-weight: normal;
                background: transparent;
            }
            #clock_title {
                font-family: "Arial", "Helvetica", sans-serif;
                font-size: 20px;
                font-weight: normal;
                padding: 0 5px 0 5px;
                background: transparent;
            }
        """

        if hasattr(self, 'clock_mini'):
            if not self.clock_mini.objectName():
                self.clock_mini.setObjectName("clock_mini")
            self.clock_mini.setStyleSheet(fallback_styles)

        if hasattr(self, 'clock_title'):
            if not self.clock_title.objectName():
                self.clock_title.setObjectName("clock_title")
            self.clock_title.setStyleSheet(fallback_styles)

    def toggle_mute(self):
        try:
            toggle = ToggleMuteDiscord()
            if toggle.main():
                self.is_muted = not self.is_muted
                svg = self.buttons_data['microphone_btn']['svg']
                # Меняем иконку в зависимости от состояния
                if self.is_muted:
                    svg.load(self.mic_off_path)
                else:
                    # Возвращаем стандартную иконку
                    svg.load(self.mic_on_path)
                    self.is_muted = False
            else:
                return

            # Применяем цвет к SVG
            self.style_manager.apply_color_svg(svg, strength=0.95)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в toggle_mute: {e}")

    def pin_widget(self):
        try:
            self.is_pinned = not self.is_pinned

            # Получаем текущие флаги (без изменения)
            flags = self.windowFlags()

            # Обновляем флаг поверх окон
            if self.is_pinned:
                flags |= Qt.WindowType.WindowStaysOnTopHint
                self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
            else:
                flags &= ~Qt.WindowType.WindowStaysOnTopHint
                self.style_manager.apply_color_svg(self.pin_svg, strength=0.95, specified_color="#ffffff")

            # Применяем флаги и обновляем окно
            self.setWindowFlags(flags)
            self.show()  # Обязательно после изменения флагов!

            self.state_manager.save_window_state(self)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка pin widget: {e}")

    def update_ui_for_mode(self):
        """Обновляет UI в зависимости от режима"""
        if self.is_compact:
            self.tab_widget.hide()
            self.relayout_buttons(vertical=True)
            self.audio_widget.show()
            self.clock_mini.show()
            self.clock_widget.hide()

        else:
            self.tab_widget.show()
            self.relayout_buttons(vertical=False)

            self.audio_widget.hide()
            self.clock_mini.hide()
            self.clock_widget.show()

    def repaint_main_buttons(self):
        self.hide_main_btns()
        self.recreate_buttons()
        self.load_font_clock()
        self.update_delay()
        self.hide_main_btns()
        self.toggle_snow()

    def recreate_buttons(self):
        """Пересоздает блок с кнопками"""
        if not hasattr(self, 'buttons_widget') or not self.buttons_widget:
            return

        button_index = -1
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item.widget() == self.buttons_widget:
                button_index = i
                break

        if button_index == -1:
            return

        old_buttons_widget = self.buttons_widget

        if self.is_compact:
            self.buttons_widget = self.create_main_buttons(vertical=True)
        else:
            self.buttons_widget = self.create_main_buttons(vertical=False)

        self.content_layout.insertWidget(button_index, self.buttons_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self.content_layout.removeWidget(old_buttons_widget)
        old_buttons_widget.deleteLater()

        if self.is_locked != 0:
            self.buttons_widget.setEnabled(False)

    def start_hide_countdown(self):
        """Запускает отсчет до скрытия кнопок (только если условия выполнены)"""
        if (self.is_autohide and 
            not self.mouse_over_widget and 
            not self.is_height_compact and
            self.delay > 0):  # Добавил проверку задержки
            
            self.hide_timer.start(self.delay)

    def auto_hide_buttons(self):
        """Автоматически скрывает кнопки (вызывается по таймеру)"""
        if (self.is_autohide and 
            not self.mouse_over_widget and 
            not self.is_height_compact):
            self.hide_main_btns()

    def hide_main_btns(self):
        """Переключает компактный режим по высоте (только для скрытия кнопок)"""
        try:
            self.hide_timer.stop()

            if self.animation and self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()

            old_geometry = self.geometry()

            if not hasattr(self, 'is_height_compact'):
                self.is_height_compact = False

            if self.is_height_compact:
                self.buttons_widget.show()
            else:
                self.buttons_widget.hide()

            # Переключаем состояние
            self.is_height_compact = not self.is_height_compact

            # Обновляем кнопку (блокируя сигналы чтобы не было рекурсии)
            if hasattr(self, 'hide_btns'):
                self.hide_btns.blockSignals(True)
                self.hide_btns.setChecked(self.is_height_compact)
                self.hide_btns.blockSignals(False)

            # Сохраняем правый край и ширину
            new_width = old_geometry.width()
            new_x = old_geometry.x()

            # Анимация изменения высоты
            self.animation = QPropertyAnimation(self, b"geometry")
            self.animation.setDuration(300)
            self.animation.setStartValue(old_geometry)
            self.animation.setEndValue(QRect(new_x, old_geometry.y(), new_width, 112))
            self.animation.setEasingCurve(QEasingCurve.Type.InBack)

            def on_animation_finished():
                self.save_state()

            self.animation.finished.connect(on_animation_finished)
            self.animation.start()
            if not self.is_height_compact:
                QTimer.singleShot(1000, self.start_hide_countdown)

        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в toggle_compact_height_mode: {e}")

    def resize_widget(self):
        """Переключает между компактным и нормальным режимом"""
        try:
            self.save_notes()
            if hasattr(self, 'current_tab') and self.current_tab == 0:
                self.close_sensors()
            if self.animation and self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()

            old_geometry = self.geometry()
            # Сначала вычисляются величины исходя из текущей геометрии, а уже после изменяется флаг self.in_compact
            # Поэтому условие инвертированное "if not"
            new_width = 87 if not self.is_compact else max(310, self.buttons_widget.height() + 20) # 20px это отступы
            new_height = self.buttons_widget.width() + 100 if not self.is_compact else 310 # 100px отступы и другие виджеты

            # Сохраняем правый край
            right_edge = old_geometry.x() + old_geometry.width()
            new_x = right_edge - new_width
            # Переключаем состояние
            self.is_compact = not self.is_compact

            # Обновляем UI
            self.update_ui_for_mode()

            # Анимация
            self.animation = QPropertyAnimation(self, b"geometry")
            self.animation.setDuration(200)
            self.animation.setStartValue(old_geometry)
            self.animation.setEndValue(QRect(new_x, old_geometry.y(), new_width, new_height))
            self.animation.setEasingCurve(QEasingCurve.Type.OutBack)

            def on_animation_finished():
                self.save_state()
                if not self.is_compact:
                    self.switch_tab(1)

            self.animation.finished.connect(on_animation_finished)
            self.animation.start()

        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в resize_widget: {e}")

    def shutdown_system(self):
        """Выключает компьютер после подтверждения"""
        try:
            # Проверяем, не открыто ли уже окно подтверждения
            if hasattr(self, 'confirm_dialog') and self.confirm_dialog and self.confirm_dialog.isVisible():
                return
                
            # Создаем кастомное окно вместо QMessageBox
            self.confirm_dialog = QDialog(self)
            self.confirm_dialog.setWindowFlags(
                Qt.WindowType.Dialog | 
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint
            )
            self.confirm_dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.confirm_dialog.setFixedSize(120, 70)
            self.confirm_dialog.setModal(False)

            container = QWidget(self.confirm_dialog)
            container.setObjectName("MessageContainer")
            container.setGeometry(0, 0, self.confirm_dialog.width(), self.confirm_dialog.height())
            container.setStyleSheet(
                "background-color: rgba(30, 30, 32, 0.8);"
                "border-radius: 10px;"
            )
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5)
            container_layout.setSpacing(5)

            label = QLabel("Выключить комп?")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 12px;
                    padding: 0;
                    background-color: transparent;
                }
            """)
            container_layout.addWidget(label)

            # Контейнер для кнопок
            btn_container = QWidget()
            btn_container.setStyleSheet("background: transparent")
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(5)

            # Кнопки
            yes_btn = QPushButton("Да")
            no_btn = QPushButton("Нет")

            btn_style = """
                QPushButton {
                    padding: 3px;
                    width: 30px;
                    height: 20px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: rgba(70, 70, 70, 240);
                }
            """
            yes_btn.setStyleSheet(btn_style)
            no_btn.setStyleSheet(btn_style)

            btn_layout.addStretch()
            btn_layout.addWidget(yes_btn)
            btn_layout.addWidget(no_btn)
            btn_layout.addStretch()

            container_layout.addWidget(btn_container)

            self.apply_styles()

            # Таймер для проверки фокуса
            self.focus_timer = QTimer()
            self.focus_timer.timeout.connect(self.check_dialog_focus)
            self.focus_timer.start(100)

            # Обработчики кнопок
            yes_btn.clicked.connect(self.on_shutdown_yes)
            no_btn.clicked.connect(self.on_shutdown_no)

            # Показываем диалог
            self.confirm_dialog.show()
            self.confirm_dialog.activateWindow()

        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка диалога: {e}")

    def on_shutdown_yes(self):
        """Обработчик кнопки Да"""
        try:
            if hasattr(self, 'confirm_dialog') and self.confirm_dialog:
                self.cleanup_dialog()
                shutdown_windows()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка выключения: {e}")

    def on_shutdown_no(self):
        """Обработчик кнопки Нет"""
        if hasattr(self, 'confirm_dialog') and self.confirm_dialog:
            self.cleanup_dialog()

    def check_dialog_focus(self):
        """Проверяет, активен ли диалог"""
        if (hasattr(self, 'confirm_dialog') and 
            self.confirm_dialog and 
            self.confirm_dialog.isVisible() and
            not self.confirm_dialog.isActiveWindow()):

            self.cleanup_dialog()

    def cleanup_dialog(self):
        """Очищает ресурсы диалога"""
        if hasattr(self, 'confirm_dialog') and self.confirm_dialog:
            if hasattr(self, 'focus_timer') and self.focus_timer.isActive():
                self.focus_timer.stop()
            self.confirm_dialog.reject()
            self.confirm_dialog.deleteLater()
            self.confirm_dialog = None

    def open_settings(self):
        """Переключатель для основного окна и настроек"""
        try:
            if self.assistant.isVisible():
                if not (hasattr(self.assistant, 'mutable_panel') and self.assistant.mutable_panel.isVisible()):
                    self.assistant.open_main_settings()
                else:
                    self.assistant.hide_widget()
                    self.assistant.custom_hide()
            else:
                # Если основное окно скрыто - показываем его
                self.assistant.show()

                # Открываем настройки, только если они еще не открыты
                if not (hasattr(self.assistant, 'mutable_panel') and self.assistant.mutable_panel.isVisible()):
                    self.assistant.open_main_settings()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка при переключении окна настроек: {e}")

    def open_main_window(self):
        try:
            if self.assistant.isVisible():
                self.assistant.custom_hide()
            else:
                self.assistant.proper_show()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка при открытии основного окна через виджет {e}")

    def lock_state(self):
        """Переключает возможность перетаскивания виджета между тремя состояниями"""
        try:
            if not hasattr(self, 'lock_btn') or not hasattr(self, 'lock_svg'):
                return

            # Три состояния: 0-разблокирован, 1-частично заблокирован, 2-полностью заблокирован
            current_state = getattr(self, 'is_locked', 0)
            self.is_locked = (current_state + 1) % 3  # Циклически переключаем 0→1→2→0

            # Меняем иконку и настройки в зависимости от состояния
            if hasattr(self, 'lock_svg'):
                if self.is_locked == 0:
                    # Состояние 0: полностью разблокирован
                    self.lock_svg.load(self.unlock_path)
                    self.lock_btn.setToolTip("Полностью разблокирован")
                    self.lock_title_widget(state=True)
                    # Включаем все виджеты
                    self._set_widgets_enabled(True, True, True)
                    self.style_manager.apply_color_svg(self.lock_svg, strength=0.95)

                elif self.is_locked == 1:
                    # Состояние 1: частично заблокирован
                    self.lock_svg.load(self.partial_lock_path)
                    self.lock_btn.setToolTip("Частично заблокирован")
                    self.lock_title_widget(state=True)
                    # Частично отключаем - например, только audio_widget
                    self._set_widgets_enabled(True, True, True)
                    self.style_manager.apply_color_svg(self.lock_svg, strength=0.95)

                elif self.is_locked == 2:
                    # Состояние 2: полностью заблокирован
                    self.lock_svg.load(self.lock_path)
                    self.lock_btn.setToolTip("Полностью заблокирован")
                    self.lock_title_widget(state=False)
                    # Отключаем все виджеты
                    self._set_widgets_enabled(False, False, False)
                    self.style_manager.apply_color_svg(self.lock_svg, strength=0.95, specified_color="#FF6666")

            # Сохраняем состояние блокировки
            self.save_state()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в методе lock_state: {e}")

    def _set_widgets_enabled(self, audio_enabled, buttons_enabled, tabs_enabled):
        """Вспомогательный метод для управления состоянием виджетов"""
        if hasattr(self, "audio_widget"):
            self.audio_widget.setEnabled(audio_enabled)
        if hasattr(self, "buttons_widget"):
            self.buttons_widget.setEnabled(buttons_enabled)
        if hasattr(self, "tab_widget"):
            self.tab_widget.setEnabled(tabs_enabled)

    def save_state(self):
        self.state_manager.save_window_state(self)

    def lock_title_widget(self, state=True):
        if hasattr(self, "title_bar"):
            # Пропускаем только lock_btn
            if state:
                for btn in self.title_bar.findChildren(QPushButton):
                    if btn != self.lock_btn:
                        btn.setEnabled(True)
            else:
                for btn in self.title_bar.findChildren(QPushButton):
                    if btn != self.lock_btn:
                        btn.setEnabled(False)

    def prev_track_action(self):
        try:
            controller.previous_track()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка при переключении трека: {e}")

    def pause_track_action(self):
        try:
            self.is_paused = not self.is_paused
            svg = self.player_buttons['pause_btn']['svg']
            btn = self.player_buttons['pause_btn']['button']
            # Меняем иконку в зависимости от состояния
            if self.is_paused:
                svg.load(self.play_track)
                btn.setToolTip("Продолжить")
                self.is_paused = True
            else:
                # Возвращаем стандартную иконку
                svg.load(self.pause_track)
                btn.setToolTip("Пауза")
                self.is_paused = False

            # Применяем цвет к SVG
            self.style_manager.apply_color_svg(svg, strength=0.95)
            controller.play_pause()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка при попытке поставить паузу: {e}")

    def next_track_action(self):
        try:
            controller.next_track()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка при переключении трека: {e}")

    def closeEvent(self, event):
        # Сохраняем состояние виджета
        self.save_state()
        self.save_notes()
        self.sensors_tab.stop_monitoring()

        # Проверяем состояние главного окна
        if self.assistant:
            if self.assistant.isVisible() and not self.assistant.isMinimized():
                # Если главное окно видимо и не свернуто - просто закрываем виджет
                pass
            else:
                # В противном случае вызываем специальный метод
                self.assistant.restore_and_hide()
                
        self.deleteLater()
        super().closeEvent(event)

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            # Применяем стили к текущему окну
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

            # Устанавливаем стиль для текущего окна
            self.setStyleSheet(style_sheet)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в методе apply_styles: {e}")
            
    def update_background_style(self):
        """Применяет/обновляет стиль фона"""
        try:
            self.background_color = self.style_manager.get_transparent_background_from_border(opacity=210, darken_factor=800)
            self.main_container.setStyleSheet(f"""
                #MainContainer {{
                    background: {self.background_color};
                    border-radius: 10px;
                }}
            """)
            
            self.back_btn_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=200)
            self.back_btn_title_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=150)
            
            for btn_data in self.buttons_data.values():
                btn = btn_data['button']
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background: {self.back_btn_color};
                        border-radius: 5px;
                    }}
                """)
                
            for btn_data in self.player_buttons.values():
                btn = btn_data['button']
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background: {self.back_btn_color};
                        border-radius: 5px;
                    }}
                """)

            for btn_data in self.title_buttons.values():
                btn = btn_data['button']
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: {self.back_btn_title_color};
                        border-radius: 5px;
                    }}
                """)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка применения фона: {e}")

    def update_colors(self):
        self.styles = self.style_manager.load_styles()
        for name, data in self.player_buttons.items():
            self.style_manager.apply_color_svg(data['svg'], strength=0.90)
        for name, data in self.buttons_data.items():
            self.style_manager.apply_color_svg(data['svg'], strength=0.90)

        self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
        self.style_manager.apply_color_svg(self.lock_svg, strength=0.95)
        self.style_manager.apply_color_svg(self.resize_svg, strength=0.95, specified_color="#FFFFFF")
        self.style_manager.apply_color_svg(self.close_svg, strength=0.95, specified_color="#FFFFFF")
        
        self.update_background_style()
        
        if hasattr(self, "snow_on_label") and self.snow_on_label is not None:
            self.snow_on_label.setSnowColor(self.style_manager.get_snow_color(), white_balance=40)

    def _on_sensor_tab_show(self, event):
        """Когда вкладка показана"""
        self.sensors_tab.start_monitoring()
        super(type(self.sensors_tab), self.sensors_tab).showEvent(event)
    
    def _on_sensor_tab_hide(self, event):
        """Когда вкладка скрыта"""
        self.sensors_tab.stop_monitoring()
        super(type(self.sensors_tab), self.sensors_tab).hideEvent(event)

    def switch_tab(self, index):
        """Переключает вкладки и подсвечивает активную кнопку"""
        if not hasattr(self, 'tab_content'):
            return

        if hasattr(self, 'current_tab') and self.current_tab == 0:
            self.close_sensors()

        self.tab_content.setCurrentIndex(index)
        self.tab_content.show()
        self.current_tab = index

        if index == 0:
            self.tab_content.setCurrentIndex(index)
            self.open_sensors()
        else:
            self.tab_content.setCurrentIndex(index)
            self.tab_content.show()

        for btn in [self.btn_sensors, self.btn_notes]:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(50, 50, 50, 150);
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: rgba(70, 70, 70, 200);
                }
            """)

        active_btn = [self.btn_sensors, self.btn_notes][index]
        active_btn.setStyleSheet("""
            QPushButton {
                background: rgba(40, 110, 230, 200);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }
        """)

    def update_time(self):
        current_time = QTime.currentTime()
        if self.is_compact:
            time_str = current_time.toString("hh:mm")
            self.clock_mini.setText(time_str)
        else:
            time_str = current_time.toString("hh:mm:ss")
            self.clock_title.setText(time_str)

    def open_sensors(self):
        try:
            self.sensors_tab.show()
            if hasattr(self, 'sensor_tab'):
                self.sensors_tab.start_monitoring()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в open_sensors: {e}")

    def close_sensors(self):
        try:
            if hasattr(self, 'sensor_tab'):
                self.sensors_tab.stop_monitoring()
            self.sensors_tab.hide()
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка в close_sensors: {e}")

    def start_notes_save_timer(self):
        """Запускает таймер автосохранения при изменении текста"""
        self.notes_save_timer.start(5000)  # 5 секунд

    def save_notes(self):
        """Сохраняет заметки в файл"""
        try:
            notes_text = self.notes_tab.toPlainText()
            os.makedirs(os.path.dirname(self.notes_file), exist_ok=True)
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                f.write(notes_text)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка сохранения заметок: {e}")

    def load_notes(self):
        """Загружает заметки из файла"""
        try:
            if os.path.exists(self.notes_file):
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    notes_text = f.read()
                    self.notes_tab.setPlainText(notes_text)
        except Exception as e:
            debug_logger.error(f"[PANEL] Ошибка загрузки заметок: {e}")
            self.notes_tab.setPlainText("Тут можно писать заметки")
