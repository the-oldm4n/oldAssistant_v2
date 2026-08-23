"""
Основной модуль инициализации приложения, GUI
"""

import json
import os
from bin.base_modules.autostart_crossplatform import AutostartManager
from bin.base_modules.check_auth_manager import CheckAuthManager
from bin.base_modules.ipс_manager import IPCManager, activate_existing_window
from bin.base_modules.resize_manager import ResizeManager
from bin.base_modules.update_manager import UpdateManager
import sys
import traceback
from bin.core_assist import AssistManager
from bin.reminder_manager import ReminderManager, RemindersListDialog
from PySide6.QtGui import QCursor, QIcon, QFont, QAction, QFontDatabase
from PySide6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QWidget,\
    QDialog, QSizePolicy, QSystemTrayIcon, QMenu, QMessageBox, QSpacerItem
from PySide6.QtCore import Signal, QTimer, Qt, QEvent
from bin.base_modules.config_manager import get_config_value, set_config_value, update_version
from path_builder import get_app_data_dir, get_path
from log_config import assist_log, logger, get_log_path, get_debuglog_path
from config import dev_mode, domain, is_login_widget, skip_splash_screen, current_version

from bin.base_modules.exract_resourses import ensure_resources
if not dev_mode:
    ensure_resources()

if dev_mode:
    style_path = get_path("user_data", "color.json")
    winsize_file = get_path("win_size.json")
    download_dir = get_path("update")
    changelog_path = get_path("user_data", "changelog.md")
    process_names = get_path('user_data', 'process_names.json')
    settings_file = get_path('user_data', 'settings.json')
    folder_links = get_path('user_data', 'links')
    folder_screenshots = get_path('user_data', 'screenshots')
    censor_file = get_path('user_data', 'censor_counter.csv')
    user_keywords = get_path("user_data", "keywords.json")
    changelog = get_path("user_data", "changelog.md")
    reminders_file = get_path("user_data", "reminders.json")
else:
    style_path = os.path.join(get_app_data_dir(), "user_data", "color.json")
    winsize_file = os.path.join(get_app_data_dir(), "win_size.json")
    download_dir = os.path.join(get_app_data_dir(), "update")
    changelog_path = os.path.join(get_app_data_dir(), "user_data", "changelog.md")
    process_names =  os.path.join(get_app_data_dir(), 'user_data', 'process_names.json')
    settings_file =  os.path.join(get_app_data_dir(), 'user_data', 'settings.json')
    folder_links = os.path.join(get_app_data_dir(), 'user_data', 'links')
    folder_screenshots = os.path.join(get_app_data_dir(), 'user_data', 'screenshots')
    censor_file = os.path.join(get_app_data_dir(), 'user_data', 'censor_counter.csv')
    user_keywords = os.path.join(get_app_data_dir(), "user_data", "keywords.json")
    changelog = os.path.join(get_app_data_dir(), "user_data", "changelog.md")
    reminders_file = os.path.join(get_app_data_dir(), "user_data", "reminders.json")

ohm_path = get_path("data", "OHM", "OpenHardwareMonitor.exe")
vosk_model_ru = get_path("data", "model_ru")

from mygui.config import mygui_config
mygui_config.configure(colors_path=style_path, 
                 presets_path=get_path("bin", "color_presets"), 
                 custom_presets_path=get_path("user_data", "presets"),
                 custom_selectors=get_path("bin", "custom_selectors.json"))
from mygui import main_apply_colors, color_signal, sidebar_animated_signal, VersionLabel, CustomSvgWidget, \
    AnimatedSidebar, ColorSettingsWindow, SVGProgressBar
main_apply_colors.init()

from widgets.logs_page import LogsPage
from widgets.others_page import OthersPage
from widgets.settings_page import SettingsPage
from widgets.commands_page import CommandsPage
from bin.base_modules.changelog_window import ChangelogWindow

from bin.frosted_widget import GarlandDecorator, SnowOverlay
from bin.help_widget import HelpWidget
from bin.base_modules.register_module import AuthManager
from bin.screenshot_tool import SystemScreenshot
from bin.signals import gui_signals, commands_signal, tool_widget_signal
from bin.base_modules.toast_notification import ToastNotif, SimpleNotif
from bin.widget_window import SmartWidget
from bin.commands_manager import main_commands_manager
from bin.speak_functions import thread_play_sound
from bin.lists import commands_list
from bin.utils import setup_global_font
from bin.init_screen import InitScreen
from bin.base_modules.stacked_widget import SlidingStackedWidget


# build_ini = get_config_value("app", "build")
update_version(current_version)


class Assistant(QMainWindow):
    """
Основной класс содержащий GUI и скрипт обработки команд
    """
    save_settings_signal = Signal()
    def __init__(self):
        super().__init__()
        self.ipc_manager = IPCManager(self)

        ### signals for smartwidget
        tool_widget_signal.open_main_window.connect(self.open_window_from_tool)
        tool_widget_signal.open_settings.connect(self.open_settings_from_tool)
        tool_widget_signal.trigger_capture_area.connect(self.capture_area)
        tool_widget_signal.trigger_open_shortcuts.connect(self.open_folder_shortcuts)
        tool_widget_signal.run_command.connect(self.start_default_command)
        tool_widget_signal.add_reminder.connect(self.add_reminder)
        tool_widget_signal.show_reminders.connect(self.show_reminders_list)
        color_signal.color_changed.connect(self.apply_styles)
        sidebar_animated_signal.update_delay.connect(self.update_sidebar_delay)
        gui_signals.open_widget_signal.connect(self.open_widget)
        gui_signals.close_widget_signal.connect(self.close_widget)
        commands_signal.commands_reloaded.connect(self.reload_commands)


        self.latest_version = None
        self.current_ver = None
        self.beta_version = False
        self.first_run = True
        self.widget_window = None
        self.snow_on_background = None
        self.garland_decorator = None
        self.process_names = process_names
        self.ohm_path = ohm_path
        self.type_version = "stable"

        self.main_folder_path = get_app_data_dir()
        self.log_file_path = get_log_path()
        self.debuglog_file_path = get_debuglog_path()
        self.changelog_file_path = changelog

        self.resize_manager = ResizeManager(winsize_file=winsize_file, main_window=self)
        # Обязательное переопределение ивентов
        self.mousePressEvent = self.resize_manager.mousePressEvent
        self.mouseMoveEvent = self.resize_manager.mouseMoveEvent
        self.mouseReleaseEvent = self.resize_manager.mouseReleaseEvent
        self.enterEvent = self.resize_manager.enterEvent
        self.leaveEvent = self.resize_manager.leaveEvent

        self.update_manager = UpdateManager(download_dir=download_dir, main_window=self)

        self.reminder_manager = ReminderManager(reminders_file=reminders_file)
        self.reminder_manager.reminder_triggered.connect(self.show_reminder)
        
        self.install_icons()

        self.style_manager = main_apply_colors
        self.settings_file_path = settings_file
        self.screenshot_tool = SystemScreenshot(save_dir=folder_screenshots)
        self.update_settings(self.settings_file_path)
        self.install_settings()
        self.commands_manager = main_commands_manager

        self.assist_manager = AssistManager(main_window=self, user_keywords=user_keywords, vosk_model_ru_path=vosk_model_ru)
        self.save_settings_signal.connect(self.assist_manager.restart_bot) # сигнал эмитится при выборе другого устройства ввода
        
        self.commands = self.commands_manager.commands
        self.default_commands = commands_list

        self.auth = AuthManager(domain)
        self.user_data = self.auth.user_data

        self.check_auth_manager = CheckAuthManager(auth_manager=self.auth, main_window=self)
        self.autostart_manager = AutostartManager(main_window=self)

        self.check_or_create_folders()
        
        if is_login_widget:
            self.check_auth_manager.check_auth(self.auth)
        else:
            self.check_up()

    def check_up(self):
        if not skip_splash_screen:
            self.start_splash_screen()
        else:
            self.post_check_up()

    def post_check_up(self):
        self.init_ui()
        self.preload_utils()
        self.content_container.current_changed.connect(self.on_page_changed)
        self.on_page_changed(0)
        self.check_start_widget()
        self.resize_manager.load_window_settings()
        

        if self.is_min_tray:
            if self.first_run:
                self.preload_window()
        else:
            self.showNormal()

        if self.user_data:
            self.check_auth_manager.update_user_profile()

        self.assist_manager.run_assist()

        QTimer.singleShot(5000, self.update_manager.check_update_app)

    def preload_utils(self):
        self.update_style_list() # Внутри вызывается apply_styles
        self.autostart_manager.check_autostart()
        self.assist_manager.check_keywords_file()
        self.toggle_update_button()

    def handle_init_result(self, success):
        """Обработчик результата инициализации"""
        if success:
            self.post_check_up()

    def start_splash_screen(self):
        try:
            self.splash = InitScreen()
            self.splash.init_complete.connect(self.handle_init_result)
            self.splash.show()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при инициализации программы: {e}")

    def update_style_list(self):
        change_color = ColorSettingsWindow(self)
        change_color.update_style_file()
        # change_color.update_all_styles()
        self.apply_styles()

    def load_settings(self):
        """Загружает настройки из settings.json."""
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_settings(self, notif=True):
        """Сохраняет настройки в файл settings.json."""
        settings_data = {
            "voice": self.speaker,
            "assistant_name": self.assistant_name,
            "assist_name2": self.assist_name2,
            "assist_name3": self.assist_name3,
            "steam_path": self.steam_path,
            "is_censored": self.is_censored,
            "volume_assist": self.volume_assist,
            "run_updater": self.run_updater,
            "is_corrected_command": self.is_corrected_command,
            "autostart_app": self.autostart_app,
            "is_min_tray": self.is_min_tray,
            "is_widget": self.is_widget,
            "is_keep_watch": self.is_keep_watch,
            "input_device_id": self.input_device_id,
            "input_device_name": self.input_device_name,
            "is_snow": self.is_snow,
            "is_garland": self.is_garland,
            "sidebar_delay": self.sidebar_delay
        }
        try:
            os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)

            # Сохраняем настройки в файл
            with open(self.settings_file_path, 'w', encoding='utf-8') as file:
                json.dump(settings_data, file, ensure_ascii=False, indent=4)

            if self.run_updater:
                value = "prod"
            else:
                value = "dev"
            set_config_value("app", "build", f"{value}")

            self.commands_manager.update_vaults()  # Синхронизация настроек в менеджере команд
            if notif:
                self.show_toast("Настройки сохранены!")
            logger.debug("[MAIN] Настройки сохранены.")
        except Exception as e:
            assist_log.error(f"[MAIN] Ошибка при сохранении настроек: {e}")
            logger.error(f"[MAIN] Ошибка при сохранении настроек: {e}")
            raise

    def update_settings(self, settings_file, default_settings=None):
        """
        Проверяет файл настроек на наличие ключей из default_settings.
        Если ключ отсутствует, добавляет его со значением по умолчанию.
        """
        if default_settings is None:
            default_settings = {
                "voice": "johnny",
                "assistant_name": "джон",
                "assist_name2": "джонни",
                "assist_name3": "джон",
                "steam_path": "",
                "is_censored": True,
                "volume_assist": 0.15,
                "run_updater": False,
                "is_corrected_command": True,
                "autostart_app": False,
                "is_min_tray": False,
                "is_widget": True,
                "is_keep_watch": False,
                "input_device_id": None,
                "input_device_name": None,
                "is_snow": False,
                "is_garland": False,
                "sidebar_delay": 300
            }

        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as file:
                try:
                    settings = json.load(file)
                except json.JSONDecodeError:
                    settings = {}
        else:
            settings = {}

        updated = False
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
                updated = True

        if updated:
            with open(settings_file, "w", encoding="utf-8") as file:
                json.dump(settings, file, ensure_ascii=False, indent=4)

        return settings

    def install_settings(self):
        self.version = self.update_manager.get_version(version=current_version)
        self.settings = self.load_settings()
        self.assistant_name = self.settings.get('assistant_name', "джон")
        self.assist_name2 = self.settings.get('assist_name2', "джон")
        self.assist_name3 = self.settings.get('assist_name3', "джон")
        self.speaker = self.settings.get("voice", "johnny")
        self.volume_assist = self.settings.get('volume_assist', 0.2)
        self.steam_path = self.settings.get('steam_path', '')
        self.is_censored = self.settings.get('is_censored', False)
        self.run_updater = self.settings.get("run_updater", True)
        self.is_corrected_command = self.settings.get("is_corrected_command", False)
        self.autostart_app = self.settings.get("autostart_app", False)
        self.is_min_tray = self.settings.get("is_min_tray", False)
        self.is_widget = self.settings.get("is_widget", True)
        self.is_keep_watch = self.settings.get("is_keep_watch", False)
        self.input_device_id = self.settings.get("input_device_id", None)
        self.input_device_name = self.settings.get("input_device_name", None)
        self.is_snow = self.settings.get("is_snow", False)
        self.is_garland = self.settings.get("is_garland", False)
        self.sidebar_delay = self.settings.get("sidebar_delay", 300)

        if mygui_config:
            mygui_config.update('sidebar_delay', self.sidebar_delay)

    def install_icons(self):
        self.icon_main_path = get_path("bin", "icons", "nine_dots.svg")
        self.icon_start_win = get_path("bin", "icons", "start-win.svg")
        self.icon_update = get_path("bin", "icons", "updates.svg")
        self.icon_settings_path = get_path("bin", "icons", "settings.svg")
        self.icon_shortcut_path = get_path("bin", "icons", "shortcut.svg")
        self.icon_power_path = get_path("bin", "icons", "power.svg")
        self.icon_guide_path = get_path("bin", "icons", "guide.svg")
        self.icon_other_path = get_path("bin", "icons", "other.svg")
        self.icon_commands_path = get_path("bin", "icons", "commands.svg")
        self.icon_widget_path = get_path("bin", "icons", "open_widget.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.icon_screenshot_path = get_path("bin", "icons", "camera.svg")
        self.icon_tray_path = get_path("bin", "icons", "tray_icon.png")
        self.icon_updates_path = get_path("bin", "icons", "updates.svg")
        self.icon_advance_settings_path = get_path("bin", "icons", "settings+.svg")
        self.icon_speech_hook_path = get_path("bin", "icons", "speech_hook.svg")
        self.icon_styles_path = get_path("bin", "icons", "styles.svg")
        self.icon_panel_path = get_path("bin", "icons", "panel.svg")
        self.icon_logs_path = get_path("bin", "icons", "logs.svg")
        self.icon_censor_path = get_path("bin", "icons", "censor.svg")
        self.icon_relax_path = get_path("bin", "icons", "relax.svg")
        self.icon_create_command_path = get_path("bin", "icons", "commands.svg")
        self.icon_added_commands_path = get_path("bin", "icons", "commands_list.svg")
        self.icon_process_link_path = get_path("bin", "icons", "process_link.svg")
        self.default_avatar_path = get_path("bin", "icons", "default_avatar.svg")
        self.update_light_path = get_path("bin", "icons", "update_light.svg")
        self.icon_main_settings_path = get_path("bin", "icons", "main_settings.svg")
        self.icon_clear_logs_path = get_path("bin", "icons", "clear_log.svg")
        self.icon_scripts_path = get_path("bin", "icons", "scripts.svg")
        self.resize_path = get_path("bin", "icons", "resize_window.svg")
        self.logo_path = get_path("bin", "icons", "logo-app.svg")
        self.owlapp_logo_path = get_path("bin", "icons", "logo-owlapp.svg")
        self.icon_min_path = get_path("bin", "icons", "minimize.svg")
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса."""
        try:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowSystemMenuHint |
                Qt.WindowType.WindowMinimizeButtonHint |
                Qt.WindowType.WindowMaximizeButtonHint |
                Qt.WindowType.WindowCloseButtonHint
            )
            self.setWindowIcon(QIcon(get_path('icon.ico')))
            self.setWindowTitle("VOXODIUM")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setMouseTracking(True)
            self.resize(*self.resize_manager.default_size)

            screen_geometry = self.screen().availableGeometry()
            self.move(
                (screen_geometry.width() - self.width()) // 2,
                (screen_geometry.height() - self.height()) // 2
            )

            # Главный контейнер
            self.central_widget = QWidget(self)
            self.central_widget.setObjectName("MainWindowWidget") 
            self.setCentralWidget(self.central_widget)
            self.central_widget.setMouseTracking(True)
            
            self.update_snow_state()

            # Главный layout
            root_layout = QVBoxLayout(self.central_widget)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # --- Title Bar ---
            self.title_bar_widget = QWidget()
            self.title_bar_widget.setMaximumHeight(40)
            self.title_bar_widget.setObjectName("TitleBarV2")
            self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
            self.title_bar_layout.setContentsMargins(10, 0, 0, 0)

            self.title_bar_widget.mousePressEvent = self.resize_manager.title_bar_mouse_press
            self.title_bar_widget.mouseMoveEvent = self.resize_manager.title_bar_mouse_move
            self.title_bar_widget.mouseReleaseEvent = self.resize_manager.title_bar_mouse_release
            self.title_bar_widget.mouseDoubleClickEvent = self.resize_manager.title_bar_double_click

            self.logo_svg = CustomSvgWidget(self.logo_path)
            self.logo_svg.setFixedSize(30, 30)
            self.logo_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.logo_svg)

            self.title_label = self.setup_custom_font_label(text="VOXODIUM")
            self.title_label.setStyleSheet("background: transparent; font-size: 24px;")
            self.title_bar_layout.addWidget(self.title_label)
            
            self.progress_load = SVGProgressBar(style="circle", show_text=False, circle_size=30, padding=5)
            self.title_bar_layout.addWidget(self.progress_load)
            
            self.title_bar_layout.addStretch()
            
            # Виджет профиля
            self.user_profile_widget = QWidget()
            self.user_profile_widget.setObjectName("UserProfileWidget")
            self.user_profile_widget.setFixedSize(34, 34)
            self.user_profile_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            self.user_profile_widget.mousePressEvent = self.check_auth_manager.on_profile_click
            self.user_profile_layout = QHBoxLayout(self.user_profile_widget)
            self.user_profile_layout.setContentsMargins(0, 0, 0, 0)

            # Аватарка
            self.avatar_svg = CustomSvgWidget(self.default_avatar_path)
            self.avatar_svg.setFixedSize(30, 30)
            self.avatar_svg.setStyleSheet("background: transparent; border: none;")

            self.user_profile_layout.addWidget(self.avatar_svg)
            self.title_bar_layout.addWidget(self.user_profile_widget)

            spacer_0 = QSpacerItem(5, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.title_bar_layout.addItem(spacer_0)
            
            self.update_btn = QPushButton()
            self.update_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.update_btn.setFixedSize(30, 30)
            self.update_btn.clicked.connect(self.update_manager.open_update_app)
            self.update_btn.hide()
            self.update_svg = CustomSvgWidget(self.icon_update, self.update_btn)
            self.update_svg.setFixedSize(24, 24)
            self.update_svg.move(3, 3)
            self.update_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.update_btn)

            spacer_1 = QSpacerItem(5, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.title_bar_layout.addItem(spacer_1)
            
            self.update_light_btn = QPushButton()
            self.update_light_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.update_light_btn.setToolTip("Сменить анимацию гирлянды")
            self.update_light_btn.setFixedSize(30, 30)
            self.update_light_btn.clicked.connect(self.update_light_garland)
            self.update_light_svg = CustomSvgWidget(self.update_light_path, self.update_light_btn)
            self.update_light_svg.setFixedSize(24, 24)
            self.update_light_svg.move(3, 3)
            self.update_light_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.update_light_btn)
            if self.is_garland:
                self.update_light_btn.show()
            else:
                self.update_light_btn.hide()

            spacer_2 = QSpacerItem(5, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.title_bar_layout.addItem(spacer_2)

            self.styles_button = QPushButton()
            self.styles_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.styles_button.clicked.connect(self.open_color_settings)
            self.styles_button.setFixedSize(50, 38)
            self.styles_button.setObjectName("TitleBarBtn")
            self.style_svg = CustomSvgWidget(self.icon_styles_path, self.styles_button)
            self.style_svg.setFixedSize(25, 25)
            self.style_svg.move(12, 7)
            self.style_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.styles_button)

            self.min_button = QPushButton()
            self.min_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.min_button.clicked.connect(self.showMinimized)
            self.min_button.setFixedSize(50, 38)
            self.min_button.setObjectName("TitleBarBtn")
            self.min_svg = CustomSvgWidget(self.icon_min_path, self.min_button)
            self.min_svg.setFixedSize(25, 25)
            self.min_svg.move(12, 7)
            self.min_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.min_button)

            self.maximize_button = QPushButton()
            self.maximize_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.maximize_button.clicked.connect(lambda: self.resize_manager.toggle_maximize(True))
            self.maximize_button.setFixedSize(50, 38)
            self.maximize_button.setObjectName("TitleBarBtn")
            self.max_svg = CustomSvgWidget(self.resize_path, self.maximize_button)
            self.max_svg.setFixedSize(25, 25)
            self.max_svg.move(12, 7)
            self.max_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.maximize_button)

            self.close_button = QPushButton()
            self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.close_button.clicked.connect(self.custom_hide)
            self.close_button.setFixedSize(50, 38)
            self.close_button.setObjectName("TitleBarCloseBtn")
            self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_button)
            self.close_svg.setFixedSize(25, 25)
            self.close_svg.move(12, 7)
            self.close_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.close_button)

            # --- Основное содержимое ---
            self.content_widget = QWidget()
            self.content_widget.setObjectName("ContentWidget")
            main_layout = QHBoxLayout(self.content_widget)
            main_layout.setContentsMargins(55, 5, 5, 5)

            self.update_garland_state()

            self.content_container = SlidingStackedWidget(self)

            self.logs_widget = LogsPage(main_window=self, log_path=self.log_file_path)
            self.settings_widget = SettingsPage(main_window=self)
            self.commands_widget = CommandsPage(main_window=self)
            self.others_widget = OthersPage(main_window=self, censor_file=censor_file)

            self.content_container.add_page(self.logs_widget)
            self.content_container.add_page(self.settings_widget)
            self.content_container.add_page(self.commands_widget)
            self.content_container.add_page(self.others_widget)


            self.buttons_data = [
            {
                "key": "logs_page",
                "text": "Главная",
                "icon_path": self.icon_main_path,
                "svg_attr": "home_svg",
                "slot": lambda: self.content_container.switch_to(0)
            },
            {
                "key": "links_page",
                "text": "Ярлыки",
                "icon_path": self.icon_shortcut_path,
                "svg_attr": "links_svg",
                "slot": lambda: self.open_folder_shortcuts()
            },
            {
                "key": "settings_page",
                "text": "Настройки",
                "icon_path": self.icon_settings_path,
                "svg_attr": "settings_svg",
                "slot": lambda: self.content_container.switch_to(1)
            },
            {
                "key": "commands_page",
                "text": "Команды",
                "icon_path": self.icon_commands_path,
                "svg_attr": "commands_svg",
                "slot": lambda: self.content_container.switch_to(2)
            },
            {
                "key": "others_page",
                "text": "Прочее",
                "icon_path": self.icon_other_path,
                "svg_attr": "others_svg",
                "slot": lambda: self.content_container.switch_to(3)
            },
            {
                "key": "toggle_worker",
                "text": "Остановить работу",
                "icon_path": self.icon_power_path,
                "svg_attr": "toggle_worker_svg",
                "slot": lambda: self.assist_manager.start_assist_toggle()
            },
            {
                "key": "open_widget",
                "text": "Открыть виджет",
                "icon_path": self.icon_widget_path,
                "svg_attr": "open_widget_svg",
                "slot": lambda: self.open_widget()
            }
            ]

            sidebar_elements = [
                {
                    "key": item["key"],
                    "text": item["text"],
                    "icon_path": item["icon_path"]
                }
                for item in self.buttons_data
            ]

            self.open_folder_btn = QLabel("Корневая папка")
            self.open_folder_btn.setToolTip("Открыть папку с данными")
            self.open_folder_btn.setObjectName("UpdateLabel")
            self.open_folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.open_folder_btn.mousePressEvent = self.open_folder_files

            self.update_label = QLabel("Stable") # Stable
            self.update_label.setToolTip("Проверить обновления")
            self.update_label.setObjectName("UpdateLabel")
            self.update_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.update_label.mousePressEvent = self.update_manager.update_answer

            self.label_version = VersionLabel(version=self.version)
            self.label_version.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.label_version.mousePressEvent = self.changelog_window
            
            self.animated_sidebar = AnimatedSidebar(
                parent=self.content_widget, 
                elements_data=sidebar_elements, 
                max_width=250, 
                main_window=self, 
                position="left"
                )
            
            self._sidebar_slot_map = {item["key"]: item["slot"] for item in self.buttons_data}
            self.animated_sidebar.element_clicked.connect(self._handle_sidebar_click)

            self.animated_sidebar.add_custom_widget(self.open_folder_btn)
            self.animated_sidebar.add_custom_widget(self.update_label)
            self.animated_sidebar.add_custom_widget(self.label_version)
            self.help_widget = HelpWidget()
            self.help_widget.hide()

            main_layout.addWidget(self.content_container)
            main_layout.addWidget(self.help_widget)
  

            root_layout.addWidget(self.title_bar_widget)
            root_layout.addWidget(self.content_widget)

            #===============================================

            # === Tray, логи, прочее ===
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(QIcon(self.icon_tray_path))
            self.tray_icon.setToolTip("Voxodium")

            start_widget = QAction("Запустить виджет", self)
            start_widget.triggered.connect(self.open_widget)

            settings = QAction("Настройки", self)
            settings.triggered.connect(self.open_settings_of_tray)
            
            open_folder_links = QAction("Папка с ярлыками", self)
            open_folder_links.triggered.connect(self.open_folder_shortcuts)
            
            open_folder_screens = QAction("Папка со скринами", self)
            open_folder_screens.triggered.connect(self.open_folder_screenshots)

            quit_action = QAction("Закрыть", self)
            quit_action.triggered.connect(self.close_app)

            self.menu_tray = QMenu()
            self.menu_tray.addAction(start_widget)
            self.menu_tray.addAction(settings)
            self.menu_tray.addAction(open_folder_links)
            self.menu_tray.addAction(open_folder_screens)
            self.menu_tray.addAction(quit_action)
            self.tray_icon.setContextMenu(self.menu_tray)
            self.tray_icon.activated.connect(self.on_tray_icon_activated)
            self.tray_icon.show()
            
            self.centralWidget().adjustSize()
            self.minimum_size = self.centralWidget().minimumSizeHint()
            logger.debug(f"[MAIN] Минимальный размер контента: {self.minimum_size.width()}x{self.minimum_size.height()}")      
            self.setup_mouse_tracking_for_children(self.central_widget)
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при инициализации GUI: {e}")

    def open_color_settings(self):
        """Открывает диалоговое окно для настройки цветов."""
        try:
            color_dialog = ColorSettingsWindow(self)
            color_dialog.colorChanged.connect(self.apply_styles)
            color_dialog.show()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при открытии окна настроек цветов: {e}")
            self.show_message(f"Не удалось открыть настройки цветов: {e}", "Ошибка", "error")
            
    def _handle_sidebar_click(self, key: str):
        slot = self._sidebar_slot_map.get(key)
        if slot and callable(slot):
            slot()
        else:
            logger.error(f"[MAIN] Нет слота для ключа: {key}")

    def on_page_changed(self, index):
        """При смене страницы обновляем активный элемент"""
        if index == 0:
            self.animated_sidebar.set_active_element("logs_page")
        elif index == 1:
            self.animated_sidebar.set_active_element("settings_page")
        elif index == 2:
            self.animated_sidebar.set_active_element("commands_page")
        elif index == 3:
            self.animated_sidebar.set_active_element("others_page")

        if index != 0:
            self.help_widget.show()
        else:
            self.help_widget.hide()

    def open_folder_files(self, event):
        try:
            path = self.main_folder_path
            os.startfile(path)
        except Exception as e:
            assist_log.error(f"[MAIN] Ошибка при открытии папки: {e}")

    def setup_mouse_tracking_for_children(self, widget):
        """Устанавливает mouse tracking для всех дочерних виджетов"""
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    def install_event_filter_recursive(self, widget):
        """Рекурсивно устанавливает event filter для виджета и всех его детей"""
        if not widget:
            return
            
        widget.installEventFilter(self)
        for child in widget.children():
            if isinstance(child, QWidget):
                self.install_event_filter_recursive(child)
    
    def eventFilter(self, obj, event):
        """Обрабатывает события мыши для показа справок"""
        if event.type() == QEvent.Enter:
            help_id = obj.property("helpId")
            if help_id and hasattr(self, 'help_widget'):
                self.help_widget.show_help(help_id)
                return True
                
        elif event.type() == QEvent.Leave:
            pass
            
        return super().eventFilter(obj, event)
        
    def setup_custom_font_label(self, text: str):
        font_path = get_path("bin", "fonts", "Audiowide", "Audiowide-Regular.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        
        if font_id == -1:
            return None
        
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if not font_families:
            return None
        
        font_family = font_families[0]

        label = QLabel(text)
        custom_font = QFont(font_family, 30, QFont.Weight.Light)
        label.setFont(custom_font)
        
        return label
        
    def update_garland_state(self):
        if self.is_garland:
            if self.garland_decorator is None:
                self.create_garland()
            else:
                self.garland_decorator.show()
                self.update_light_btn.show()
        else:
            if self.garland_decorator is not None:
                self.garland_decorator.hide()
                self.update_light_btn.hide()
                
    def create_garland(self):
        if self.garland_decorator is not None:
            return
        
        self.garland_decorator = GarlandDecorator(self.content_widget, light_count=104, light_size=12)
        self.garland_decorator.set_animation_mode("random")
        
        if self.is_garland:
            self.garland_decorator.show()
        else:
            self.garland_decorator.hide()
            
    def update_light_garland(self):
        try:
            # Создаем гирлянду если ее нет
            if not hasattr(self, "garland_decorator") or self.garland_decorator is None:
                self.create_garland()
                
            if self.garland_decorator is not None:
                self.garland_decorator.next_animation()
            else:
                logger.error("[MAIN] Не удалось создать гирлянду")
                
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при смене анимации гирлянды: {e}")    

    def update_snow_state(self):
        """Обновляет состояние снега через show/hide"""
        if self.is_snow:
            if self.snow_on_background is None:
                self.create_snow()
            else:
                self.snow_on_background.show()
        else:
            if self.snow_on_background is not None:
                self.snow_on_background.hide()

    def create_snow(self):
        """Создает снежный эффект (только один раз)"""
        if self.snow_on_background is not None:
            return
        
        self.snow_on_background = SnowOverlay(parent=self.central_widget)
        self.snow_on_background.resize(1000, 1000)
        self.snow_on_background.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.snow_on_background.raise_()
        self.snow_on_background.setSnowColor(self.style_manager.get_raw_color(), white_balance=50)

        # Изначально показываем или скрываем в зависимости от состояния
        if self.is_snow:
            self.snow_on_background.show()
        else:
            self.snow_on_background.hide()

    def set_snow_enabled(self, enabled):
        """Включает/выключает снег"""
        self.is_snow = enabled
        
        if self.snow_on_background is not None:
            if enabled:
                self.snow_on_background.show()
            else:
                self.snow_on_background.hide()

    def update_sidebar_delay(self, delay):
        if isinstance(delay, int):
            self.sidebar_delay = delay
            self.save_settings(notif=False)

    def preload_window(self):
        """Предварительная загрузка окна"""
        # Показываем в невидимой области
        self.move(-10000, -10000)
        self.showMinimized()
        self.showNormal()

        # Принудительная отрисовка
        self.update()
        QApplication.processEvents()

        # Скрываем через короткое время
        QTimer.singleShot(100, lambda: [self.hide(), self.center_window()])
        self.first_run = False

    def center_window(self):
        """Центрирование окна"""
        frame_geo = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry()
        frame_geo.moveCenter(screen.center())
        self.move(frame_geo.topLeft())

    def apply_styles(self):
        """Применяет все стили к окну"""
        try:
            self.styles = self.style_manager.load_styles()

            svg_attrs = ['style_svg', 'avatar_svg', 'svg_image', 'logo_svg', 'update_light_svg', 
                         'clear_logs_svg', 'update_all_preset_svg', 'max_svg', 'min_svg']

            for attr in svg_attrs:
                if hasattr(self, attr):
                    self.style_manager.apply_color_svg(getattr(self, attr))

            if hasattr(self, 'progress_load'):
                self.style_manager.apply_progressbar(widget=self.progress_load)
            if hasattr(self, 'close_svg'):
                self.style_manager.apply_color_svg(self.close_svg, specified_color="#ff0000")

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
            self.apply_menu_styles(self.menu_tray)
            if getattr(self, "snow_on_background", None) is not None:
                self.snow_on_background.setSnowColor(self.style_manager.get_raw_color(), white_balance=50)
                
        except Exception as e:
            logger.error(f"[MAIN] Ошибка в методе apply_styles: {e}")

    def apply_menu_styles(self, menu: QMenu):
        """Применяет стили из self.styles к QMenu"""
        if not hasattr(self, 'styles') or not self.styles:
            return

        menu_style = ""
        for widget_name, styles in self.styles.items():
            if widget_name.startswith("QMenu"):
                menu_style += f"{widget_name} {{\n"
                for prop, value in styles.items():
                    menu_style += f"    {prop}: {value};\n"
                menu_style += "}\n"

        if menu_style.strip():
            menu.setStyleSheet(menu_style)

    def show_toast(self, message, on_outside=False):
        try:
            is_window_hidden = self.isMinimized() or not self.isVisible()
            if on_outside:
                is_window_hidden = True
            toast = ToastNotif(
                parent=None if is_window_hidden else self,
                message=message,
                timeout=5000
            )
            toast.show_toast()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при показе всплывающего уведомления: {e}")

    def show_message(self, text="...", title="Уведомление", message_type="info", buttons=QMessageBox.StandardButton.Ok):
        try:
            message = SimpleNotif(
                parent=self,
                message=text,
                title=title,
                message_type=message_type,
                buttons=buttons
            )
            return message.exec_()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при показе уведомления(оконного): {e}")
            return QDialog.DialogCode.Rejected

    def resizeEvent(self, event):
        if hasattr(self, 'animated_sidebar'):
            self.animated_sidebar.on_parent_resize()

        if hasattr(self, 'snow_on_background') and self.snow_on_background:
            self.snow_on_background.setGeometry(self.central_widget.rect())
            self.snow_on_background._init_snowflakes()
            self.snow_on_background.update()
            
        if hasattr(self, 'garland_decorator') and self.garland_decorator:
            self.garland_decorator.update_size(self.width())
        return super().resizeEvent(event)

    def keyPressEvent(self, event):
        """Сворачивает основное окно в трей по нажатию на Esc"""
        if event.key() == Qt.Key.Key_Escape:
            if self.isVisible():
                self.on_page_changed(0)
                event.accept()
            else:
                self.custom_hide()
                event.accept()
        else:
            super().keyPressEvent(event)

    def toggle_update_button(self):
        """
        Метод для отображения или скрытия кнопки "Установить обновление"
        """
        if self.update_label.text() == "New version": # Stable New version 
            self.update_btn.show()
            self.style_manager.apply_color_svg(self.update_svg, strength=0.90, specified_color="#44D14F")
        else:
            self.update_btn.hide()

    def check_or_create_folders(self):
        links_path = folder_links
        screenshot_path = folder_screenshots
        path_list = [links_path, screenshot_path]

        for folder_path in path_list:
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                logger.info(f"[MAIN] Папка {folder_path} найдена")
            else:
                try:
                    os.makedirs(folder_path)
                    logger.info(f'[MAIN] Папка {folder_path} была создана.')
                except Exception as e:
                    logger.error(f'[MAIN] Ошибка при создании папки {folder_path}: {e}')

    def reload_commands(self):
        """Централизованное сохранение команд"""
        self.commands = self.commands_manager.commands

    def on_tray_icon_activated(self, reason):
        """Обработка активации иконки в трее."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.proper_show()

    def proper_show(self):
        """Универсальный метод показа окна с активацией"""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

        self.activateWindow()
        self.raise_()
        self.setFocus()

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        self.logs_widget.log_area.start_active_mode()

    def custom_hide(self):
        self.logs_widget.log_area.start_background_mode()
        self.hide()
        self.show_toast("Приложение свернуто в трей")

    # def changeEvent(self, event):
    #     """Обработка изменения состояния окна."""
    #     if event.type() == QEvent.Type.WindowStateChange:
    #         if self.windowState() & Qt.WindowState.WindowMinimized:
    #             self.hide()
    #             self.logs_widget.log_area.start_background_mode()
    #     super().changeEvent(event)

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.resize_manager.save_window_settings()
        if hasattr(self, "logs_widget"):
            self.logs_widget.log_area.stop_monitoring()

        if self.assist_manager.is_running:
            self.assist_manager.stopped()
        event.accept()

    def force_close(self):
        """Принудительное закрытие, игнорируя все подтверждения"""
        self.logs_widget.log_area.stop_monitoring()
        self.close()

        # Гарантированное завершение через 100 мс
        QTimer.singleShot(100, lambda: [
            QApplication.closeAllWindows(),
            QApplication.quit()
        ])

    def close_app(self):
        if self.assist_manager.is_running:
            self.assist_manager.stopped()
            self.logs_widget.log_area.stop_monitoring()
            QTimer.singleShot(2500, self.force_close) # Время для проигрывания аудио перед закрытием
        else:
            self.force_close()    

    def cleanup_before_exit(self):
        """Подготовка к выходу"""
        try:
            if hasattr(self, 'splash') and self.splash:
                if hasattr(self.splash, 'check_thread') and self.splash.check_thread:
                    self.splash.check_thread.quit()
                    self.splash.check_thread.wait(1000)
                
                if self.splash.isVisible():
                    self.splash.close()

            self.close()
            
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при завершении: {e}")
            self.close()

    def start_default_command(self, command, action, type_command):
        logger.info(f"[MAIN][start_default_command] Получены аргументы: {command}, {action}, {type_command}")
        self.global_handler_command(command, action, type_command)
        logger.info(f"[MAIN][start_default_command] Команда {command} выполнена с действием {action}")

    def global_handler_command(self, command, action, type_command):
        if type_command == "shortcut" or type_command == "url":
            self.handle_app_command(command, action)
        elif type_command == "folder":
            self.handle_folder_command(command, action)
        elif type_command == "script":
            self.handle_script_command(command, action)
        elif type_command == "system":
            self.handle_system_command(command, action)
        else:
            self.show_toast("Тип команды передан некорректно!")

    def handle_app_command(self, text, action):
        """Обработка команд для приложений, ярлыков и ссылок"""
        logger.info(f"[MAIN] Вызван обработчик команд для ярлыков и ссылок: {text}, {action}")
        all_commands = {**self.default_commands, **self.commands}
        for keyword, command_data in all_commands.items():
            if keyword in text:

                value = command_data.get('name', '') if isinstance(command_data, dict) else command_data

                self.commands_manager.handler_links(value, action)
                return True
        return False

    def handle_folder_command(self, text, action):
        """Обработка команд для папок"""
        logger.error(f"[MAIN] Вызван обработчик команд для папок: {text}, {action}")
        all_commands = {**self.default_commands, **self.commands}
        for keyword, command_data in all_commands.items():
            if keyword in text:
                value = command_data.get('name', '') if isinstance(command_data, dict) else command_data

                if self.commands_manager.handler_folder(value, action):
                    return True
        return False
    
    def handle_script_command(self, script_key, action):
        """Обработка скрипт-команд"""
        try:
            # Просто запускаем скрипт
            self.commands_manager.execute_script(script_key, action)
            return True
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске сценария: {e}")
            return False
        
    def handle_system_command(self, command, action):
        logger.info(f"[MAIN] Вызван обработчик команд для запуска системных: {command}, {action}")
        data_commands = self.default_commands

        for keyword, command_data in data_commands.items():
            if keyword in command:
                value = command_data.get('name', '') if isinstance(command_data, dict) else command_data

                if self.commands_manager.handler_system_commands(value, action):
                    return True
        return False

    def open_widget(self, is_auto_start=False):
        QTimer.singleShot(100, lambda: self._show_smart_widget(is_auto_start))
    
    def _show_smart_widget(self, is_auto_start=False):
        try:
            widget_exists = (
                hasattr(self, 'widget_window') and
                self.widget_window is not None)

            if widget_exists and self.widget_window.isVisible():
                self._close_smart_widget()
                return

            if widget_exists:
                self.widget_window.show()
            else:
                self.widget_window = SmartWidget()
                self.widget_window.setAttribute(Qt.WA_DeleteOnClose, True)
                self.widget_window.destroyed.connect(self._on_widget_destroyed)
                self.widget_window.show()

            if not is_auto_start:
                self.assist_manager.get_reaction(name="approve_folder")

        except Exception as e:
            logger.error(f"[MAIN] Ошибка при открытии виджета: {str(e)}")
            self.show_toast(f"Ошибка при открытии виджета: {str(e)}")

    def _close_smart_widget(self):
        """Полное закрытие виджета с очисткой"""
        if hasattr(self, 'widget_window') and self.widget_window is not None:
            # Явно закрываем и удаляем
            self.widget_window.close()
            self.widget_window.deleteLater()
            self.widget_window = None
            
    def _on_widget_destroyed(self):
        """Слот вызывается когда виджет уничтожен"""
        if hasattr(self, 'widget_window'):
            self.widget_window = None
        logger.info("[MAIN] Виджет полностью уничтожен")

    def close_widget(self):
        try:
            if hasattr(self, "widget_window"):
                self.widget_window.close()
                self.assist_manager.get_reaction(name="approve_folder")
        except Exception as e:
            self.assist_manager.get_reaction(detail=True, name="error_file")
            self.show_toast(f"Ошибка при закрытии виджета (close_widget): {e}")
            logger.error(f"[MAIN] Ошибка при закрытии виджета (close_widget): {e}")

    def open_folder_shortcuts(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = folder_links
        logger.info(f"[MAIN] Открытие папки ярлыков, {folder_path}")
        os.startfile(folder_path)

    def open_folder_screenshots(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = folder_screenshots
        logger.info(f"[MAIN] Открытие папки скриншотов, {folder_path}")
        os.startfile(folder_path)

    def open_settings_of_tray(self):
        if self.isVisible():
            self.open_main_settings()
        else:
            self.showNormal()
            self.open_main_settings()

    def open_main_settings(self):
        """Открывает панель настроек"""
        try:
            self.content_container.switch_to(1)
        except Exception as e:
            logger.error(f"Error: {e}")
            self.show_message(f"[MAIN][open_main_settings]: {str(e)}", "Ошибка", "error")

    def changelog_window(self, event):
        """Открываем окно с логами изменений"""
        dialog = ChangelogWindow(self)
        dialog.show()

    def update_voice(self, new_voice):
        """Обновление голоса и путей к аудиофайлам"""
        self.speaker = new_voice
        self.assist_manager.update_audio_path(self.speaker)
        assist_log.info(f"Голос изменен на: {new_voice}")
        logger.info(f"[MAIN][update_voice] Голос изменен на: {new_voice}")

    def check_start_widget(self):
        if self.is_widget:
            self.open_widget(is_auto_start=True)

    def capture_area(self):
        try:
            self.screenshot_tool.capture_area()
        except Exception as e:
            assist_log.error(f'Ошибка {e}')
            logger.error(f'[MAIN][capture_area] Error: {e}')

    def capture_fullscreen(self):
        try:
            self.screenshot_tool.capture_fullscreen()
            thread_play_sound(type_sound="ok")
        except Exception as e:
            thread_play_sound(type_sound="error")
            assist_log.error(f'Ошибка {e}')
            logger.error(f'[MAIN][capture_fullscreen] Error: {e}')

    def open_settings_from_tool(self):
        try:
            if self.isVisible():
                self.open_main_settings()
            else:
                self.show()
                self.open_main_settings()
        except Exception as e:
            logger.error(f"[MAIN][open_window_from_tool] Ошибка при переключении окна настроек: {e}")

    def open_window_from_tool(self):
        try:
            if self.isVisible():
                self.custom_hide()
            else:
                self.proper_show()
        except Exception as e:
            logger.error(f"[MAIN][open_window_from_tool] Ошибка при открытии основного окна через виджет {e}")

    def show_reminder(self, text):
        thread_play_sound(type_sound="ok")
        self.show_toast(message=f"Напоминание: {text}", on_outside=True)
        assist_log.info(f"Напоминание: {text}")
        logger.info(f"[MAIN][show_reminder] Сработало напоминание — {text}")

    def add_reminder(self, text, dt):
        self.reminder_manager.add_reminder(text, dt)
        self.show_toast(f"Напоминание {text} создано!")

    def show_reminders_list(self):
        dialog = RemindersListDialog(self.reminder_manager, self)
        dialog.exec()


if __name__ == '__main__':
    try:
        if activate_existing_window():
            sys.exit(0)

        app = QApplication([])
        app.setWindowIcon(QIcon(get_path('icon.ico')))
        setup_global_font(app, "Open Sans", 10, "Medium")
        window = Assistant()
        app.exec()

    except Exception as e:
        traceback.print_exc()
        assist_log.error(f"[MAIN][start_app] Error: {e}")
        logger.error(f"[MAIN][start_app] Error: {e}")
