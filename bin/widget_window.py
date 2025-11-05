import json
import os
import subprocess
import wmi
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, \
    QDialog, QLabel, QGridLayout, QStackedWidget, QSizePolicy, QTextEdit, QApplication, QGraphicsBlurEffect
from PySide6.QtCore import Qt, QPoint, QSize, QPropertyAnimation, QRect, QTimer, QTime, QEasingCurve

from bin.apply_color_methods import ApplyColor
from bin.audio_control import controller
from bin.custom_svg_widget import CustomSvgWidget
from bin.frosted_widget import SnowOverlay
from bin.function_list_main import shutdown_windows
from bin.lists import fonts_list
from bin.signals import color_signal, widget_btns_signal
from bin.toggle_mute_discord import ToggleMuteDiscord
from logging_config import debug_logger
from path_builder import get_path


class WindowStateManager:
    def __init__(self, config_path=get_path("user_settings", "widget_state.json")):
        self.config_path = config_path
        self.default_state = {
            "window_position": {"x": 100, "y": 100},
            "window_size": {"width": 300, "height": 350},
            "is_compact": False,
            "is_pinned": False,
            "is_locked": False, 
            "is_snow": True
        }

        # Создаем файл при инициализации, если его нет
        if not os.path.exists(self.config_path):
            self.save_state(self.default_state)

    def load_state(self):
        """Загружает состояние окна из JSON файла"""
        try:
            with open(self.config_path, 'r') as f:
                state = json.load(f)
                # Объединяем с default_state для обратной совместимости
                return {**self.default_state, **state}
        except (json.JSONDecodeError, IOError) as e:
            debug_logger.error(f"Ошибка загрузки состояния: {e}, используются значения по умолчанию")
            return self.default_state.copy()

    def save_state(self, state):
        """Сохраняет состояние окна в JSON файл"""
        try:
            # Создаем папку, если ее нет
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w') as f:
                json.dump(state, f, indent=4)
        except IOError as e:
            debug_logger.error(f"Ошибка сохранения состояния: {e}")

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
        # Загружаем текущее состояние
        state = self.load_state()
        # Обновляем значение
        state["is_snow"] = bool(value)
        # Сохраняем обратно
        self.save_state(state)


class SmartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        widget_btns_signal.buttons_updated.connect(self.repaint_main_buttons)
        self.buttons_data = {}
        self.player_buttons = {}
        self.is_paused = False
        self.is_muted = False
        self.snow_on_label = None

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
        self.active_pin_path = get_path("bin", "icons", "active_pin.svg")
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

        # Стили
        self.style_manager = ApplyColor(self)
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
        self.is_locked = 0
        self.check_widget_pos()

        # Шрифт
        self.fonts_list = fonts_list

        self.init_ui()

        self.load_font_clock()

        # Флаги окна
        base_flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.is_pinned:
            base_flags |= Qt.WindowType.WindowStaysOnTopHint
            self.pin_svg.load(self.active_pin_path)
            self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
        self.setWindowFlags(base_flags)

        # Для перетаскивания
        self.old_pos = None
        self.is_dragging = False
        self.current_position = {"x": 0, "y": 0}

        # Таймеры
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensors)

        self.load_notes()
        self.animation = None

        # Обновляем время
        self.update_time()
        self.update_ui_for_mode()
        self.update_snow_state()
        
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
        self.snow_on_label.setSnowColor(self.style_manager.get_snow_color(), alpha=150, white_balance=40)
        
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
        self.is_snow = not self.is_snow
        self.state_manager.set_is_snow(self.is_snow)
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
        self.main_container.setStyleSheet("""
                    #MainContainer {
                        background: rgba(30, 30, 30, 180);
                        border-radius: 10px;
                    }
                """)
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

        # Аудио
        self.audio_widget = self.create_audio_controls()
        self.content_layout.addWidget(self.audio_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кнопка-тогл для переключения показа основных кнопок
        self.hide_btns = QPushButton()
        self.hide_btns.setStyleSheet("height: 5px; border-radius: 2px; background: transparent")
        self.hide_btns.clicked.connect(self.hide_main_btns)
        self.content_layout.addWidget(self.hide_btns)

        # Кнопки
        self.buttons_widget = self.create_main_buttons()
        self.content_layout.addWidget(self.buttons_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Вкладки (по умолчанию скрыты в компактном режиме)
        self.tab_widget = self.create_tabs_widget()
        self.content_layout.addWidget(self.tab_widget)

        self.layout().addWidget(self.main_container)

        if not self.is_compact:
            self.switch_tab(1)

    def create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(25)
        title_bar.setStyleSheet("""
            #TitleBar {
                background: transparent;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border-bottom: 1px solid rgba(70, 70, 70, 100);
            }
        """)
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

        # Кнопки
        self.pin_btn = QPushButton()
        self.pin_btn.setFixedSize(20, 20)
        self.pin_btn.setToolTip("Поверх других окон")
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(40, 110, 230, 80%);
            }
        """)
        self.pin_svg = CustomSvgWidget(self.pin_path, self.pin_btn)
        self.pin_svg.setFixedSize(13, 13)
        self.pin_svg.move(3, 3)
        self.pin_svg.setStyleSheet("background: transparent; border: none;")
        self.pin_btn.clicked.connect(self.pin_widget)
        self.pin_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.lock_btn = QPushButton()
        self.lock_btn.setFixedSize(20, 20)
        self.lock_btn.setToolTip("Запретить перетаскивание")
        self.lock_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(40, 110, 230, 80%);
            }
        """)
        self.lock_svg = CustomSvgWidget(self.unlock_path, self.lock_btn)
        self.lock_svg.setFixedSize(13, 13)
        self.lock_svg.move(3, 3)
        self.lock_svg.setStyleSheet("background: transparent; border: none;")
        self.lock_btn.clicked.connect(self.lock_state)
        self.lock_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.resize_btn = QPushButton()
        self.resize_btn.setFixedSize(20, 20)
        self.resize_btn.setToolTip("Компактный режим")
        self.resize_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(40, 110, 230, 80%);
            }
        """)
        self.resize_svg = CustomSvgWidget(self.resize_path, self.resize_btn)
        self.resize_svg.setFixedSize(13, 13)
        self.resize_svg.move(3, 3)
        self.resize_svg.setStyleSheet("background: transparent; border: none;")
        self.resize_btn.clicked.connect(self.resize_widget)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setToolTip("Закрыть")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(230, 37, 37, 80%);
            }
        """)
        self.close_svg = CustomSvgWidget(self.close_path, self.close_btn)
        self.close_svg.setFixedSize(13, 13)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent; border: none;")
        self.close_btn.clicked.connect(self.close)

        # Применяем цвет
        for svg in [self.pin_svg, self.lock_svg, self.resize_svg, self.close_svg]:
            self.style_manager.apply_color_svg(svg, strength=0.90)

        # Добавляем в layout
        layout.addStretch()
        for btn in [self.pin_btn, self.lock_btn, self.resize_btn, self.close_btn]:
            layout.addWidget(btn)

        return title_bar

    def create_main_buttons(self, vertical=False):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout_class = QVBoxLayout if vertical else QHBoxLayout
        buttons_layout = layout_class(widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)

        # Сохраняем ссылку на layout для управления видимостью
        self.buttons_layout = buttons_layout
        self.buttons_widget = widget
        self.buttons_visible = True  # Флаг видимости кнопок

        # Соответствие ключей чекбоксов и кнопок
        checkbox_to_button_map = {
            'turnoff_check': 'power_btn',
            'settings_check': 'settings_btn',
            'screenshot_check': 'screen_btn',
            'microphone_check': 'mic_toggle_btn',
            'links_check': 'link_btn',
            'resize_check': 'open_main_btn',
            'open_youtube': 'open_youtube'
        }

        buttons_config = {
            'power_btn': {
                'icon': self.power_path,
                'tooltip': 'Выключить Компьютер',
                'action': self.shutdown_system
            },
            'settings_btn': {
                'icon': self.settings_path,
                'tooltip': 'Открыть настройки',
                'action': self.open_settings
            },
            'screen_btn': {
                'icon': self.camera_path,
                'tooltip': 'Скриншот области',
                'action': self.assistant.capture_area
            },
            'mic_toggle_btn': {
                'icon': self.mic_on_path,
                'tooltip': 'Переключить мут в Discord',
                'action': self.toggle_mute
            },
            'link_btn': {
                'icon': self.shortcut_path,
                'tooltip': 'Открыть папку с ярлыками',
                'action': self.assistant.open_folder_shortcuts
            },
            'open_main_btn': {
                'icon': self.open_main_path,
                'tooltip': 'Развернуть основное окно',
                'action': self.open_main_window
            },
            'open_youtube': {
                'icon': self.youtube_path,
                'tooltip': 'Запустить YouTube',
                'action': lambda: self.assistant.start_default_command("ютуб", "open")
            }
        }

        # Загружаем порядок и состояния из файла
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            if "buttons" in settings_data:
                # Создаем список ВИДИМЫХ кнопок в порядке из файла
                ordered_buttons = []
                for checkbox_key, is_visible in settings_data["buttons"].items():
                    if checkbox_key in checkbox_to_button_map and is_visible:
                        button_key = checkbox_to_button_map[checkbox_key]
                        if button_key in buttons_config:
                            ordered_buttons.append(button_key)
            else:
                # Если нет настроек, все кнопки видимы в стандартном порядке
                ordered_buttons = list(buttons_config.keys())
        except:
            # Если ошибка чтения файла, все кнопки видимы в стандартном порядке
            ordered_buttons = list(buttons_config.keys())

        # Создаем только ВИДИМЫЕ кнопки в нужном порядке
        for btn_name in ordered_buttons:
            config = buttons_config[btn_name]
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setToolTip(config['tooltip'])
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background: rgba(90, 90, 90, 0.7);
                    border-radius: 5px;
                }
            """)
            svg = CustomSvgWidget(config['icon'], btn)
            svg.setFixedSize(30, 30)
            svg.move(5, 5)
            self.buttons_data[btn_name] = {'button': btn, 'svg': svg}
            self.style_manager.apply_color_svg(svg, strength=0.90)
            btn.clicked.connect(config['action'])
            setattr(self, btn_name, btn)
            buttons_layout.addWidget(btn)

        if vertical:
            buttons_layout.addStretch()

        return widget

    def create_audio_controls(self):
        widget = QWidget()
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
            btn.setFixedSize(25, 20)
            btn.setToolTip(config['tooltip'])
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background: rgba(90, 90, 90, 0.7);
                }
            """)
            svg = CustomSvgWidget(config['icon'], btn)
            svg.setFixedSize(20, 20)
            svg.move(3, 0)
            self.player_buttons[btn_name] = {'button': btn, 'svg': svg}
            self.style_manager.apply_color_svg(svg, strength=0.90)
            btn.clicked.connect(config['action'])
            setattr(self, btn_name, btn)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def create_sensors_tab(self):
        """Создаёт вкладку с датчиками (CPU, GPU, RAM)"""
        widget = QWidget()
        widget.setObjectName("SensorsTab")
        widget.setStyleSheet("background: transparent; color: white;")

        layout = QGridLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Заголовки
        cpu_label = QLabel("CPU")
        gpu_label = QLabel("GPU")
        ram_label = QLabel("RAM")

        for label in [cpu_label, gpu_label, ram_label]:
            label.setStyleSheet("font-weight: bold; color: #ddd;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(cpu_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(gpu_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ram_label, 0, 2, Qt.AlignmentFlag.AlignCenter)

        # CPU датчики
        self.cpu_temp_label = QLabel("🌡--°C")
        self.cpu_core_label = QLabel("📈--%")
        self.cpu_watt_label = QLabel("⚡--W")
        self.cpu_clock_label = QLabel("⚙--МГц")

        layout.addWidget(self.cpu_temp_label, 1, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cpu_core_label, 2, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cpu_watt_label, 3, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cpu_clock_label, 4, 0, Qt.AlignmentFlag.AlignCenter)

        # GPU датчики
        self.gpu_temp_label = QLabel("🌡--°C")
        self.gpu_core_label = QLabel("📈--%")
        self.gpu_watt_label = QLabel("⚡--W")
        self.gpu_clock_label = QLabel("⚙--МГц")

        layout.addWidget(self.gpu_temp_label, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gpu_core_label, 2, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gpu_watt_label, 3, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gpu_clock_label, 4, 1, Qt.AlignmentFlag.AlignCenter)

        # RAM датчики
        self.ram_usage_label = QLabel("💾--Гб")
        self.ram_over_label = QLabel("💾--Гб")

        layout.addWidget(self.ram_usage_label, 1, 2, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.ram_over_label, 2, 2, Qt.AlignmentFlag.AlignCenter)

        # Пустые ячейки для выравнивания
        empty = QLabel("")
        layout.addWidget(empty, 3, 2)
        layout.addWidget(QLabel(""), 4, 2)

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
        self.sensors_tab = self.create_sensors_tab()
        self.tab_content.addWidget(self.sensors_tab)

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

        # Собираем
        layout.addWidget(tab_buttons)
        layout.addWidget(self.tab_content)

        # Подключаем переключение
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
            debug_logger.error(f"Ошибка в relayout_buttons: {e}")

    # Методы для перемещения окна
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not getattr(self, 'is_locked', 0):
            self.old_pos = event.globalPos()
            self.is_dragging = False  # Флаг для отслеживания начала перемещения

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos') and self.old_pos and not getattr(self, 'is_locked', 0):
            delta = event.globalPos() - self.old_pos
            new_pos = self.pos() + delta
            self.move(new_pos)
            self.old_pos = event.globalPos()

            # Сохраняем текущие координаты в переменные (но не в файл)
            self.current_position = {"x": new_pos.x(), "y": new_pos.y()}
            self.is_dragging = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            # Сохраняем окончательные координаты в файл
            state = self.state_manager.load_state()
            state["window_position"] = self.current_position
            self.state_manager.save_state(state)
            self.is_dragging = False
            
    def check_widget_pos(self, min_visibility_percent=15):
        """Проверяет положение виджета используя сохраненные данные"""
        try:
            # Загружаем сохраненное состояние
            state = self.state_manager.load_state()
            saved_x = state["window_position"]["x"]
            saved_y = state["window_position"]["y"]
            saved_width = state["window_size"]["width"]
            saved_height = state["window_size"]["height"]
            
            debug_logger.info(f"Сохраненная позиция: ({saved_x}, {saved_y})")
            debug_logger.info(f"Сохраненный размер: {saved_width}x{saved_height}")
            
            # Создаем прямоугольник виджета на основе сохраненных данных
            widget_rect = QRect(saved_x, saved_y, saved_width, saved_height)
            
            # Проверяем на всех экранах
            screens = QApplication.screens()
            max_visibility = 0
            best_screen = None
            
            for screen in screens:
                screen_geometry = screen.availableGeometry()
                debug_logger.info(f"Экран: {screen_geometry}")
                
                if screen_geometry.intersects(widget_rect):
                    # Вычисляем сколько процентов виджета видно
                    intersection = screen_geometry.intersected(widget_rect)
                    visible_area = intersection.width() * intersection.height()
                    total_area = saved_width * saved_height
                    visibility_percent = (visible_area / total_area) * 100
                    
                    debug_logger.info(f"Видимость на экране: {visibility_percent:.1f}%")
                    
                    # Запоминаем максимальную видимость
                    if visibility_percent > max_visibility:
                        max_visibility = visibility_percent
                        best_screen = screen
            
            debug_logger.info(f"Максимальная видимость виджета: {max_visibility:.1f}%")
            
            # Проверяем достаточно ли видно
            if max_visibility < min_visibility_percent:
                debug_logger.info(f"Видимость менее {min_visibility_percent}%! Центрируем...")
                self.center_widget()
                return False
            else:
                debug_logger.info(f"Виджет в пределах экрана (видимость: {max_visibility:.1f}%)")
                return True
                
        except Exception as e:
            debug_logger.info(f"Ошибка при проверке положения виджета: {e}")
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

        debug_logger.info(f"Применение шрифта: {font_family} с размером: {font_size}")

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

        # ✅ ОБЯЗАТЕЛЬНО УСТАНАВЛИВАЕМ objectName ПЕРЕД применением стилей
        if hasattr(self, 'clock_mini') and not self.clock_mini.objectName():
            self.clock_mini.setObjectName("clock_mini")

        if hasattr(self, 'clock_title') and not self.clock_title.objectName():
            self.clock_title.setObjectName("clock_title")

        if hasattr(self, 'clock_widget') and not self.clock_widget.objectName():
            self.clock_widget.setObjectName("clock_widget")

        # ✅ ПРИМЕНЯЕМ СТИЛИ К КОНКРЕТНЫМ ВИДЖЕТАМ
        if hasattr(self, 'clock_mini'):
            self.clock_mini.setStyleSheet(styles)

        if hasattr(self, 'clock_title'):
            self.clock_title.setStyleSheet(styles)

    def load_font_clock(self):
        try:
            # Загружаем состояние
            state = self.state_manager.load_state()

            # Получаем название шрифта из файла
            font_name = state.get("font_family", "digital")

            # ✅ Ищем путь к шрифту в fonts_list
            if font_name in self.fonts_list:
                font_path = self.fonts_list[font_name]

                # Загружаем шрифт
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        font_family_name = font_families[0]  # переименовали переменную

                        self.apply_font_styles(font_family_name, font_name)

                        debug_logger.info(f"Шрифт '{font_name}' успешно загружен и применен")
                        return True

        except Exception as e:
            debug_logger.error(f"Ошибка в load_font_clock: {e}")
            # Fallback через стили
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
                svg = self.buttons_data['mic_toggle_btn']['svg']
                # Меняем иконку в зависимости от состояния
                if self.is_muted:
                    svg.load(self.mic_off_path)
                    self.is_muted = True
                else:
                    # Возвращаем стандартную иконку
                    svg.load(self.mic_on_path)
                    self.is_muted = False
            else:
                return

            # Применяем цвет к SVG
            self.style_manager.apply_color_svg(svg, strength=0.95)
        except Exception as e:
            debug_logger.error(f"Ошибка в toggle_mute: {e}")

    def pin_widget(self):
        try:
            self.is_pinned = not self.is_pinned

            # Получаем текущие флаги (без изменения)
            flags = self.windowFlags()

            # Обновляем флаг поверх окон
            if self.is_pinned:
                flags |= Qt.WindowType.WindowStaysOnTopHint
                self.pin_svg.load(self.active_pin_path)
                self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
            else:
                flags &= ~Qt.WindowType.WindowStaysOnTopHint
                self.pin_svg.load(self.pin_path)

            # Применяем флаги и обновляем окно
            self.setWindowFlags(flags)
            self.show()  # Обязательно после изменения флагов!

            self.state_manager.save_window_state(self)
        except Exception as e:
            debug_logger.error(f"Ошибка {e}")

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
        self.hide_main_btns()
        self.toggle_snow()

    def recreate_buttons(self):
        """Пересоздает блок с кнопками"""
        if not hasattr(self, 'buttons_widget') or not self.buttons_widget:
            return

        # Находим позицию кнопок в layout
        button_index = -1
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            if item.widget() == self.buttons_widget:
                button_index = i
                break

        if button_index == -1:
            return

        # Сохраняем старый виджет
        old_buttons_widget = self.buttons_widget

        # Создаем новые кнопки
        if self.is_compact:
            self.buttons_widget = self.create_main_buttons(vertical=True)
        else:
            self.buttons_widget = self.create_main_buttons(vertical=False)

        # Вставляем новые кнопки на ту же позицию
        self.content_layout.insertWidget(button_index, self.buttons_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Удаляем старые кнопки
        self.content_layout.removeWidget(old_buttons_widget)
        old_buttons_widget.deleteLater()

        if self.is_locked != 0:
            self.buttons_widget.setEnabled(False)

    def hide_main_btns(self):
        """Переключает компактный режим по высоте (только для скрытия кнопок)"""
        try:
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

            # Сохраняем правый край и ширину
            new_width = old_geometry.width()
            new_x = old_geometry.x()

            # Анимация изменения высоты
            self.animation = QPropertyAnimation(self, b"geometry")
            self.animation.setDuration(300)
            self.animation.setStartValue(old_geometry)
            self.animation.setEndValue(QRect(new_x, old_geometry.y(), new_width, 70))
            self.animation.setEasingCurve(QEasingCurve.Type.InBack)

            def on_animation_finished():
                self.save_state()

            self.animation.finished.connect(on_animation_finished)
            self.animation.start()

        except Exception as e:
            debug_logger.error(f"Ошибка в toggle_compact_height_mode: {e}")

    def resize_widget(self):
        """Переключает между компактным и нормальным режимом"""
        try:
            self.save_notes()
            if hasattr(self, 'current_tab') and self.current_tab == 0:
                self.close_sensors()
            if self.animation and self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()

            old_geometry = self.geometry()
            new_width = 90 if not self.is_compact else 300
            new_height = 300 if not self.is_compact else 350

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
            debug_logger.error(f"Ошибка в resize_widget: {e}")

    def shutdown_system(self):
        """Выключает компьютер после подтверждения"""
        try:
            # Создаем кастомное окно вместо QMessageBox
            confirm_dialog = QDialog(self)
            confirm_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            confirm_dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            confirm_dialog.setFixedSize(120, 70)

            container = QWidget(confirm_dialog)
            container.setObjectName("MessageContainer")
            container.setGeometry(0, 0, confirm_dialog.width(), confirm_dialog.height())
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

            # Обработчики кнопок
            yes_btn.clicked.connect(lambda: confirm_dialog.accept())
            no_btn.clicked.connect(lambda: confirm_dialog.reject())

            # Показываем и ждем результат
            if confirm_dialog.exec_() == QDialog.DialogCode.Accepted:
                try:
                    shutdown_windows()
                except Exception as e:
                    debug_logger.error(f"Ошибка выключения: {e}")

        except Exception as e:
            debug_logger.error(f"Ошибка диалога: {e}")

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
            debug_logger.error(f"Ошибка при переключении окна настроек: {e}")

    def open_main_window(self):
        try:
            if self.assistant.isVisible():
                self.assistant.custom_hide()
            else:
                self.assistant.proper_show()
        except Exception as e:
            debug_logger.error(f"Ошибка при открытии основного окна через виджет {e}")

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
            debug_logger.error(f"Ошибка в методе lock_state: {e}")

    def _set_widgets_enabled(self, audio_enabled, buttons_enabled, tabs_enabled):
        """Вспомогательный метод для управления состоянием виджетов"""
        if hasattr(self, "audio_widget"):
            self.audio_widget.setEnabled(audio_enabled)
        if hasattr(self, "buttons_widget"):
            self.buttons_widget.setEnabled(buttons_enabled)
        if hasattr(self, "hide_btns"):
            self.hide_btns.setEnabled(buttons_enabled)
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
            debug_logger.error(f"Ошибка при переключении трека: {e}")

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
            debug_logger.error(f"Ошибка при попытке поставить паузу: {e}")

    def next_track_action(self):
        try:
            controller.next_track()
        except Exception as e:
            debug_logger.error(f"Ошибка при переключении трека: {e}")

    def closeEvent(self, event):
        # Сохраняем состояние виджета
        self.save_state()
        self.save_notes()

        if hasattr(self, 'wmi_conn'):
            self.close_ohm()
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
                if widget.startswith("Q"):  # Для стандартных виджетов (например, QMainWindow, QPushButton)
                    selector = widget
                else:  # Для виджетов с objectName (например, TitleBar, CentralWidget)
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            # Устанавливаем стиль для текущего окна
            self.setStyleSheet(style_sheet)
        except Exception as e:
            debug_logger.error(f"Ошибка в методе apply_styles: {e}")

    def update_colors(self):
        self.styles = self.style_manager.load_styles()
        for name, data in self.player_buttons.items():
            self.style_manager.apply_color_svg(data['svg'], strength=0.90)
        for name, data in self.buttons_data.items():
            self.style_manager.apply_color_svg(data['svg'], strength=0.90)

        self.style_manager.apply_color_svg(self.pin_svg, strength=0.95)
        self.style_manager.apply_color_svg(self.lock_svg, strength=0.95)
        
        if hasattr(self, "snow_on_label"):
            self.snow_on_label.setSnowColor(self.style_manager.get_snow_color(), alpha=150, white_balance=40)

    def set_default_sensor_values(self):
        """Устанавливает значения по умолчанию для всех датчиков"""
        self.cpu_temp_label.setText("🌡--°C")
        self.cpu_core_label.setText("📈--%")
        self.cpu_watt_label.setText("⚡--W")
        self.cpu_clock_label.setText("⚙️--МГц")
        self.gpu_temp_label.setText("🌡--°C")
        self.gpu_core_label.setText("📈--%")
        self.gpu_watt_label.setText("⚡--W")
        self.gpu_clock_label.setText("⚙️--МГц")
        self.ram_usage_label.setText("💾--Гб")
        self.ram_over_label.setText("💾--Гб")

    def switch_tab(self, index):
        """Переключает вкладки и подсвечивает активную кнопку"""
        if not hasattr(self, 'tab_content'):
            return

        if hasattr(self, 'current_tab') and self.current_tab == 0:
            self.close_sensors()

            # Переключаем вкладку
        self.tab_content.setCurrentIndex(index)
        self.tab_content.show()
        self.current_tab = index  # Запоминаем текущую вкладку

        if index == 0:
            self.set_default_sensor_values()
            self.tab_content.setCurrentIndex(index)
            self.tab_content.show()
            self.open_sensors()  # Затем запускаем обновление
        else:
            self.tab_content.setCurrentIndex(index)
            self.tab_content.show()

        # Сбрасываем стиль всех кнопок
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

        # Подсвечиваем активную кнопку
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
            self.init_ohm()
            self.sensor_timer.start(1000)
        except Exception as e:
            debug_logger.error(f"Ошибка в open_sensors: {e}")

    def close_sensors(self):
        try:
            self.sensor_timer.stop()
            self.close_ohm()
        except Exception as e:
            debug_logger.error(f"Ошибка в close_sensors: {e}")

    def init_ohm(self):
        """Запускает OpenHardwareMonitor и подключается к WMI"""
        try:
            self.set_default_sensor_values()
            self.assistant.load_settings()
            self.ohm_path = self.assistant.ohm_path
            # 1. Проверка существования файла OHM
            if not os.path.exists(self.ohm_path):
                error_msg = (f"Файл OpenHardwareMonitor не найден\n"
                             f"Укажите корректный путь к файлу в настройках")
                self.assistant.show_notification_message(error_msg)
                debug_logger.error(error_msg)
                return  # Прекращаем выполнение если файла нет

            # 2. Проверка уже запущенного процесса
            tasks = subprocess.check_output('tasklist', shell=True).decode('cp866', errors='ignore')
            if "OpenHardwareMonitor.exe" in tasks:
                debug_logger.debug("OpenHardwareMonitor уже запущен")
                return

            # 3. Запуск с повышенными правами через PowerShell
            debug_logger.debug(f"Попытка запуска OHM: {self.ohm_path}")
            result = subprocess.run([
                "powershell",
                "-Command",
                f'Start-Process "{self.ohm_path}" -WindowStyle Hidden -Verb runAs'

            ],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            # 4. Проверка результата запуска
            if result.returncode != 0:
                error_msg = f"Ошибка запуска OHM (код {result.returncode}): {result.stderr.decode('cp866')}"
                debug_logger.error(error_msg)
                return

            # 5. Подключение к WMI (с задержкой для инициализации OHM)
            try:
                self.wmi_conn = wmi.WMI(namespace=self.ohm_namespace)
                debug_logger.debug("Успешное подключение к WMI")
                self.update_sensors()
            except wmi.x_wmi as wmi_error:
                debug_logger.error(f"Ошибка подключения к WMI: {str(wmi_error)}")

        except subprocess.CalledProcessError as proc_error:
            debug_logger.error(f"Ошибка при проверке процессов: {str(proc_error)}")
        except Exception as e:
            debug_logger.error(f"Неожиданная ошибка в init_ohm: {str(e)}", exc_info=True)

    def close_ohm(self):
        """Завершает OHM"""
        try:
            result = subprocess.run(
                ['taskkill', '/IM', "OpenHardwareMonitor.exe", '/F'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )
            debug_logger.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
            debug_logger.info(f"Процесс успешно завершен.")
        except subprocess.CalledProcessError:
            debug_logger.error(f"Не удалось завершить процесс.")
        except Exception as e:
            debug_logger.error(f"Ошибка: {e}")

    def update_sensors(self):
        """Обновляет данные датчиков"""
        if not hasattr(self, 'wmi_conn'):
            self.set_default_sensor_values()
            return

        try:
            sensors = self.wmi_conn.Sensor()

            # CPU данные
            cpu_temp = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Temperature' and (
                         'CPU Core' in s.Name or 'CPU Package' in s.Name or 'Core #' in s.Name)),
                '--'
            )

            cpu_core = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Load' and 'CPU Total' in s.Name),
                '--'
            )

            cpu_watt = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Power' and 'CPU Package' in s.Name),
                '--'
            )

            cpu_clock = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Clock' and 'CPU Core #1' in s.Name),
                '--'
            )

            # GPU данные
            gpu_temp = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Temperature' and 'GPU Core' in s.Name),
                '--'
            )

            gpu_core = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Load' and 'GPU Core' in s.Name),
                '--'
            )

            gpu_watt = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Power' and 'GPU' in s.Name),
                '--'
            )

            gpu_clock = next(
                (round(float(s.Value)) for s in sensors
                 if s.SensorType == 'Clock' and 'GPU Core' in s.Name),
                '--'
            )

            # RAM данные
            ram_usage = next(
                (round(float(s.Value), 2) for s in sensors
                 if s.SensorType == 'Data' and 'Used Memory' in s.Name),
                '--'
            )

            ram_free = next(
                (round(float(s.Value), 2) for s in sensors
                 if s.SensorType == 'Data' and 'Available Memory' in s.Name),
                '--'
            )

            ram_total = round(float(ram_usage + ram_free))

            # Обновляем UI
            self.cpu_temp_label.setText(f"🌡{cpu_temp}°C")
            self.cpu_core_label.setText(f"📈{cpu_core}%")
            self.cpu_watt_label.setText(f"⚡{cpu_watt}W")
            self.cpu_clock_label.setText(f"⚙️{cpu_clock}МГц")

            self.gpu_temp_label.setText(f"🌡{gpu_temp}°C")
            self.gpu_core_label.setText(f"📈{gpu_core}%")
            self.gpu_watt_label.setText(f"⚡{gpu_watt}W")
            self.gpu_clock_label.setText(f"⚙️{gpu_clock}МГц")

            self.ram_usage_label.setText(f"💾{ram_usage}Гб")
            self.ram_over_label.setText(f"💾{ram_total}Гб")

        except Exception as e:
            debug_logger.error(f"Sensor update failed: {e}")

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
            debug_logger.error(f"Ошибка сохранения заметок: {e}")

    def load_notes(self):
        """Загружает заметки из файла"""
        try:
            if os.path.exists(self.notes_file):
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    notes_text = f.read()
                    self.notes_tab.setPlainText(notes_text)
        except Exception as e:
            debug_logger.error(f"Ошибка загрузки заметок: {e}")
            self.notes_tab.setPlainText("Тут можно писать заметки")
