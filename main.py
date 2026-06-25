"""
Здесь реализованы функции и классы, необходимые для
запуска и управления ассистентом, включая обработку
пользовательского ввода и управление интерфейсом.
"""
import csv
import jellyfish
import numpy as np
import requests
import sys
import time
import traceback
from packaging import version
import psutil
import threading
import sounddevice as sd
import subprocess
from vosk import Model, KaldiRecognizer
from PySide6.QtGui import QCursor, QIcon, QFont, QDesktopServices, QAction, QPixmap, QPainter, QMouseEvent,\
    QFontDatabase, QPainterPath
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QWidget,\
    QDialog, QSizePolicy, QSystemTrayIcon, QMenu, QMessageBox, QSpacerItem
from PySide6.QtCore import Signal, QTimer, Qt, QEasingCurve, QPropertyAnimation, QRect, QEvent, QUrl, QPoint, Slot,\
    QThreadPool

from bin.config_manager import get_config_value, set_config_value, update_version
from path_builder import get_app_data_dir, get_path, get_full_filepath
from log_config import logger, debuglog, get_log_path, get_debuglog_path
from config import dev_mode, domain, skip_splash_screen, is_login_widget

from bin.exract_resourses import ensure_resources
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

ohm_path = get_path("data", "OHM", "OpenHardwareMonitor.exe")
vosk_model_ru = get_path("data", "model_ru")

from mygui.config import mygui_config
mygui_config.configure(colors_path=style_path, 
                 presets_path=get_path("bin", "color_presets"), 
                 custom_presets_path=get_path("user_data", "presets"),
                 custom_selectors=get_path("bin", "custom_selectors.json"))
from mygui import main_apply_colors, color_signal, VersionLabel, CustomSvgWidget, \
    AnimatedSidebar, ColorSettingsWindow, SVGProgressBar
main_apply_colors.init()

from widgets.logs_page import LogsPage
from widgets.others_page import OthersPage
from widgets.settings_page import SettingsPage
from widgets.commands_page import CommandsPage
from bin.bluetooth_controller import bluetooth_controller
from bin.changelog_window import ChangelogWindow
from bin.check_update import load_changelog, VersionCheckThread
from bin.download_thread import DownloadThread
from bin.frosted_widget import GarlandDecorator, SnowOverlay
from bin.help_widget import HelpWidget
from bin.login_widget import LoginWindow
from bin.register_module import AuthManager
from bin.screenshot_tool import SystemScreenshot
from bin.signals import gui_signals, commands_signal, tool_widget_signal
from bin.notification_widget import ToastNotif, SimpleNotif
from bin.toggle_mute_discord import ToggleMuteDiscord
from bin.widget_window import SmartWidget
from bin.commands_manager import main_commands_manager
from bin.function_list_main import *
from bin.audio_control import controller
from bin.speak_functions import thread_play_sound, thread_react_detail, thread_react, react
from bin.lists import get_audio_paths, commands_list, default_keywords_data, setup_global_font
from bin.init_screen import InitScreen
from bin.session_manager import UserSessionManager
from bin.stacked_widget import SlidingStackedWidget
from bin.update_dialog import UpdateApp


build_ini = get_config_value("app", "build")
version_file = "3.0.5"
update_version(version_file)


def activate_existing_window():
    """Пытается отправить команду существующему приложению"""
    try:
        socket = QLocalSocket()
        socket.connectToServer("voxodium_app")

        if socket.waitForConnected(2000):
            from PySide6.QtCore import QThread
            QThread.msleep(50)

            socket.write(b'show_window')

            if socket.waitForBytesWritten(1000):
                debuglog.info("[MAIN] Команда отправлена существующему приложению")
            else:
                debuglog.error("[MAIN] Данные не были отправлены")
                
            socket.disconnectFromServer()
            return True
        else:
            debuglog.error("[MAIN] Не удалось подключиться к IPC серверу")
            return False
    except Exception as e:
        debuglog.error(f"[MAIN] IPC client error: {e}")
        return False


class Assistant(QMainWindow):
    """
Основной класс содержащий GUI и скрипт обработки команд
    """
    save_settings_signal = Signal()
    update_checked = Signal(bool, str)
    supply_notice_signal = Signal(str, bool)
    def __init__(self):
        super().__init__()
        ### signals for smartwidget
        tool_widget_signal.open_main_window.connect(self.open_window_from_tool)
        tool_widget_signal.open_settings.connect(self.open_settings_from_tool)
        tool_widget_signal.trigger_capture_area.connect(self.capture_area)
        tool_widget_signal.trigger_open_shortcuts.connect(self.open_folder_shortcuts)
        tool_widget_signal.run_command.connect(self.start_default_command)

        self.start_ipc_server()
        self.version = self.get_version()
        self.latest_version = None
        self.current_ver = None
        self.beta_version = False
        self.is_assistant_running = False
        self.microphone_available = True
        self.first_run = True
        self.assistant_thread = None
        self.widget_window = None
        self.snow_on_background = None
        self.garland_decorator = None
        self.is_manual_check = False
        self.stop_checking = False
        self.count = 0
        color_signal.color_changed.connect(self.apply_styles)
        gui_signals.open_widget_signal.connect(self.open_widget)
        gui_signals.close_widget_signal.connect(self.close_widget)
        self.supply_notice_signal.connect(self._handle_supply_notice)
        commands_signal.commands_reloaded.connect(self.reload_commands)
        self.update_checked.connect(self.handle_update_status)
        self.main_folder_path = get_app_data_dir()
        self.log_file_path = get_log_path()
        self.debuglog_file_path = get_debuglog_path()
        self.install_icons()
        self.changelog_file_path = changelog
        self.process_names = process_names
        self.ohm_path = ohm_path
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.settings_file_path = settings_file
        self.screenshot_tool = SystemScreenshot(save_dir=folder_screenshots)
        self.default_size = 920, 700
        self._is_maximized = False
        self._default_geometry = QRect(300, 200, 920, 700)
        self._normal_geometry = None
        self.update_settings(self.settings_file_path)
        self.install_settings()
        self.commands_manager = main_commands_manager
        self.audio_stream = None
        self.last_audio_time = None  # Время последнего НЕтихого пакета
        self.silence_timer = QTimer()  # Таймер для проверки тишины
        self.silence_timer.timeout.connect(self.check_silence_timeout)
        self.silence_timer.start(5000)
        self.bluetooth = bluetooth_controller
        self.save_settings_signal.connect(self.restart_bot) # сигнал эмитится при выборе другого устройства ввода
        self.type_version = "stable"
        self.commands = self.commands_manager.commands
        self.audio_paths = get_audio_paths(self.speaker)
        self.default_commands = commands_list
        
        self.session_manager = UserSessionManager()
        self.auth = AuthManager(domain)
        self.user_data = self.auth.user_data

        self.resize_animation = QPropertyAnimation(self, b"geometry")
        self.resize_animation.setDuration(100)
        self.resize_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.check_or_create_folders()
        
        if is_login_widget:
            self.check_auth(self.auth)
        else:
            self.check_up()

    def preload_utils(self):
        self.update_style_list() # Внутри вызывается apply_styles
        self.check_autostart()
        self.check_keywords_file()
        self.toggle_update_button()

    def check_up(self):
        self.init_ui()
        self.preload_utils()
        self.content_container.current_changed.connect(self.on_page_changed)
        self.on_page_changed(0)
        self.check_start_widget()
        self.load_window_settings()
        # Прятать ли программу в трей
        if self.is_min_tray:
            # Показ окна при первом запуске(для отладки)
            if self.first_run:
                self.preload_window()
        else:
            self.showNormal()
        if self.user_data:
            self.update_user_profile()
        if self.apply_keywords_for_values():
            self.run_assist()

        QTimer.singleShot(5000, lambda: self.check_update_app())

    def handle_init_result(self, success):
        """Обработчик результата инициализации"""
        if success:
            self.check_up()

    def start_splash_screen(self):
        try:
            self.splash = InitScreen()
            self.splash.init_complete.connect(self.handle_init_result)
            self.splash.show()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при инициализации программы: {e}")

    def update_style_list(self):
        change_color = ColorSettingsWindow(self)
        change_color.update_style_file()
        # change_color.update_all_styles()
        self.apply_styles()

    def open_login(self, message=""):
        try:
            self.login_window = LoginWindow(auth=self.auth, message=message)
            self.login_window.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.login_window.show()
            
            self.login_window.login_successful.connect(self.on_login_success)
            self.login_window.login_cancelled.connect(self.on_login_cancelled)
            
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске окна авторизации: {e}")

    def on_login_success(self):
        """Обработка успешного логина"""
        try:
            if self.auth.is_guest():
                self.session_manager.set_local_session()
            elif self.auth.user_data:
                username = self.auth.user_data['username']
                self.session_manager.set_user_session(username)
            else:
                raise RuntimeError("Неизвестное состояние авторизации")

            self.set_user_data(self.auth.user_data)
            
            if not skip_splash_screen:
                self.start_splash_screen()
            else:
                self.check_up()
        except ValueError as e:
            self.show_message(str(e), "Ошибка", "error")
            self.open_login()

    def on_login_cancelled(self):
        """Обработка отмены логина"""
        debuglog.info("[MAIN] Логин отменен")
        self.cleanup_before_exit()
        
    def check_auth(self, auth):
        self.auth = auth

        status, message = self.auth.is_authenticated()
        if status:
            if self.auth.is_guest():
                debuglog.info("[MAIN] Автоматический вход: Гость")
                self.session_manager.set_local_session()
            else:
                debuglog.info(f"[MAIN] Автоматический вход: {self.auth.user_data['username']}")
                self.session_manager.set_user_session(self.auth.user_data['username'])
            
            self.set_user_data(self.auth.user_data)

            if not skip_splash_screen:
                self.start_splash_screen()
            else:
                self.check_up()
        else:
           self.open_login(message)

    def get_version(self):
        vers_on_ini = get_config_value("app", "version")

        if not vers_on_ini or vers_on_ini != version_file:
            set_config_value("app", "version", f"{version_file}")
            return version_file
        return version_file

    def get_cursor_region(self, pos):
        """Определяем область курсора для изменения размера"""
        width = self.width()
        height = self.height()
        x, y = pos.x(), pos.y()

        if self._is_maximized:
            return "center"
        
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

            if self._is_maximized and region == "center":
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

                self.toggle_maximize(animate=False)
                
                if not self._is_maximized:
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

    def title_bar_double_click(self, event):
        """Двойной клик по заголовку — развернуть/восстановить"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()

    def install_settings(self):
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
        self.is_min_tray = self.settings.get("minimize_to_tray", False)
        self.is_start_win = self.settings.get("is_start_win", False)
        self.is_widget = self.settings.get("is_widget", True)
        self.is_keep_watch = self.settings.get("is_keep_watch", False)
        self.input_device_id = self.settings.get("input_device_id", None)
        self.input_device_name = self.settings.get("input_device_name", None)
        self.is_snow = self.settings.get("is_snow", False)
        self.is_garland = self.settings.get("is_garland", False)

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
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса."""
        try:
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
            self.resize(*self.default_size)

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

            self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
            self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
            self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release
            self.title_bar_widget.mouseDoubleClickEvent = self.title_bar_double_click

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
            self.user_profile_widget.mousePressEvent = self.on_profile_click
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
            self.update_btn.clicked.connect(self.open_update_app)
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

            self.maximize_button = QPushButton()
            self.maximize_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.maximize_button.clicked.connect(lambda: self.toggle_maximize(True))
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
            self.others_widget = OthersPage(main_window=self)

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
                "slot": lambda: self.start_assist_toggle()
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
            self.update_label.mousePressEvent = self.update_answer

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
            # self.animated_sidebar.finalize_setup()
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
            self.tray_icon.setToolTip("Ассистент")

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
            debuglog.debug(f"[MAIN] Минимальный размер контента: {self.minimum_size.width()}x{self.minimum_size.height()}")      
            self.setup_mouse_tracking_for_children(self.central_widget)
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при инициализации GUI: {e}")

    def open_color_settings(self):
        """Открывает диалоговое окно для настройки цветов."""
        try:
            color_dialog = ColorSettingsWindow(self)
            color_dialog.colorChanged.connect(self.apply_styles)
            color_dialog.show()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при открытии окна настроек цветов: {e}")
            self.show_message(f"Не удалось открыть настройки цветов: {e}", "Ошибка", "error")
            
    def _handle_sidebar_click(self, key: str):
        slot = self._sidebar_slot_map.get(key)
        if slot and callable(slot):
            slot()
        else:
            debuglog.error(f"[MAIN] Нет слота для ключа: {key}")

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
            logger.error(f"[MAIN] Ошибка при открытии папки: {e}")

    def setup_mouse_tracking_for_children(self, widget):
        """Устанавливает mouse tracking для всех дочерних виджетов"""
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)
            
    # def setup_mouse_tracking_for_children(self, widget):
    #     """Рекурсивно устанавливает mouse tracking для всех дочерних виджетов"""
    #     widget.setMouseTracking(True)
    #     for child in widget.findChildren(QWidget):
    #         child.setMouseTracking(True)
    #         self.setup_mouse_tracking_for_children(child)
            
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.drag_direction = self.get_cursor_region(pos)

            if self._is_maximized:
                self.drag_direction = "center"
            
            if self.drag_direction != "center":
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint()
                self.initial_geometry = self.geometry()
                self.reached_min_size = False
                
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_maximized:
            # Если окно развёрнуто — не показываем курсоры ресайза
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
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
        if self._is_maximized:
            return
        
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

        if hasattr(self, 'snow_on_background') and self.snow_on_background:
            self.snow_on_background.setGeometry(self.central_widget.rect())
            self.snow_on_background._init_snowflakes()
            self.snow_on_background.update()
            
        if hasattr(self, 'garland_decorator') and self.garland_decorator:
            self.garland_decorator.update_size(self.width())
                   
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
        # Загрузка шрифта
        font_path = get_path("bin", "fonts", "Audiowide", "Audiowide-Regular.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        
        if font_id == -1:
            return None
        
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if not font_families:
            return None
        
        font_family = font_families[0]
        
        # Создание лейбла с кастомным шрифтом
        label = QLabel(text)
        custom_font = QFont(font_family, 30, QFont.Weight.Light)
        label.setFont(custom_font)
        
        return label
        
    def start_ipc_server(self):
        """Настраивает IPC сервер используя Qt (без потоков)"""
        self.ipc_server = QLocalServer()
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)
        
        # Удаляем старый сервер если есть (на случай краша)
        QLocalServer.removeServer("voxodium_app")
        
        # Запускаем сервер
        if not self.ipc_server.listen("voxodium_app"):
            debuglog.error(f"[MAIN] IPC server error: {self.ipc_server.errorString()}")
        else:
            debuglog.info("[MAIN] IPC server started")

    def handle_ipc_connection(self):
        """Обрабатывает входящие соединения"""
        socket = self.ipc_server.nextPendingConnection()
        debuglog.info(f"[MAIN] New connection: {socket}")
        
        if socket:
            # Многократные попытки чтения
            for attempt in range(5):
                if socket.waitForReadyRead(100):  # Короткие интервалы
                    if socket.bytesAvailable() > 0:
                        data = socket.readAll().data()
                        debuglog.info(f"[MAIN] IPC data received (attempt {attempt+1}): {data}")
                        if data == b'show_window':
                            debuglog.info("[MAIN] Activating window...")
                            self.force_show_window()
                        break
                else:
                    debuglog.warning(f"[MAIN] Attempt {attempt+1}: No data yet")
            
            socket.disconnectFromServer()
            socket.deleteLater()
            debuglog.info("[MAIN] Connection closed")
            
    def read_ipc_data(self, socket):
        """Читает данные из IPC соединения"""
        try:
            if socket.bytesAvailable() > 0:
                data = socket.readAll().data()
                debuglog.debug(f"[MAIN] IPC data received: {data}")
                if data == b'show_window':
                    self.force_show_window()
            
            # Всегда закрываем соединение после чтения
            socket.disconnectFromServer()
            socket.deleteLater()
            
        except Exception as e:
            debuglog.error(f"[MAIN] Error reading IPC data: {e}")
        
    def force_show_window(self):
        """Принудительное открытие окна из любого состояния"""
        debuglog.debug(f"[MAIN] force_show_window called. isVisible: {self.isVisible()}, isMinimized: {self.isMinimized()}, isHidden: {self.isHidden()}")
        
        # Всегда показываем окно
        self.show()
        self.showNormal()
        
        # Активация и фокус
        self.activateWindow()
        self.raise_()
        self.setFocus()
        
        # Центрирование
        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

        self.update()
        self.repaint()
        self.logs_widget.log_area.start_active_mode()
        
        debuglog.debug(f"[MAIN] After force_show: isVisible: {self.isVisible()}, isMinimized: {self.isMinimized()}")
        
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
                debuglog.error("[MAIN] Не удалось создать гирлянду")
                
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при смене анимации гирлянды: {e}")    

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

    # def hide_layout(self, layout):
    #     """Скрывает все виджеты в layout"""
    #     for i in range(layout.count()):
    #         item = layout.itemAt(i)
    #         if item.widget():
    #             item.widget().hide()

    # def show_layout(self, layout):
    #     """Показывает все виджеты в layout"""
    #     for i in range(layout.count()):
    #         item = layout.itemAt(i)
    #         if item.widget():
    #             item.widget().show()
                
    def open_user_profile(self):
        username = self.user_data["username"]
        QDesktopServices.openUrl(QUrl(f"{domain}/user/{username}"))
    
    def logout_user(self):
        """Выход с возвратом к LoginWindow"""
        debuglog.info("[MAIN] Выход из системы...")
        
        # Очищаем данные
        self.user_data = None
        self.auth.logout()

        self.restart_application()

    def restart_application(self):
        """Перезапуск приложения"""
        self.restart_dialog = UpdateApp(self)
        self.restart_dialog.restart_app()
         
    def on_profile_click(self, event):
        """Обработчик клика по профилю"""
        menu = QMenu(self)

        menu.addAction("Профиль", self.open_user_profile)
        menu.addAction("Выйти", self.logout_user)
        
        # Показываем меню под виджетом профиля
        menu.exec(self.user_profile_widget.mapToGlobal(
            QPoint(0, self.user_profile_widget.height())
        ))
               
    def set_user_data(self, user_data):
            """Установить данные пользователя (вызывается из InitScreen)"""
            self.user_data = user_data
            debuglog.info(f"[MAIN] Данные пользователя установлены: {user_data['username']}")
    
    def clear_user_data(self):
        """Очистить данные пользователя"""
        self.user_data = None
        self.set_default_avatar_svg()
                
    def update_user_profile(self, user_data=None):
        """Обновить профиль пользователя (можно вызывать без параметров)"""
        debuglog.info(f"[MAIN] Обновление профиля...")
        data = user_data or self.user_data
            
        if data and data.get('avatar') is None:
            return self.set_default_avatar_svg()
        
        if data and 'avatar' in data:
            self.load_user_avatar(data['avatar'])
        else:
            self.set_default_avatar_svg()

    def set_default_avatar_svg(self):
        """Установить SVG аватарку по умолчанию"""
        if hasattr(self, 'avatar_svg'):
            self.avatar_svg.show()
            self.style_manager.apply_color_svg(self.avatar_svg)

    def load_user_avatar(self, avatar_path):
        """Загрузить пользовательскую аватарку"""
        try:
            avatar_url = f"{self.auth.base_url}/static/{avatar_path}"
            response = requests.get(avatar_url, timeout=10, verify=False)
            
            if response.status_code == 200:
                if hasattr(self, 'avatar_svg'):
                    self.avatar_svg.hide()

                if not hasattr(self, 'avatar_pixmap_label'):
                    self.avatar_pixmap_label = QLabel()
                    self.avatar_pixmap_label.setFixedSize(30, 30)
                    self.avatar_pixmap_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    self.avatar_pixmap_label.setStyleSheet("background: transparent;")
                    self.avatar_pixmap_label.setAlignment(Qt.AlignCenter)
                    avatar_index = self.user_profile_layout.indexOf(self.avatar_svg)
                    self.user_profile_layout.insertWidget(avatar_index, self.avatar_pixmap_label)
                else:
                    self.avatar_pixmap_label.show()

                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                rounded_pixmap = self.create_rounded_pixmap(pixmap, 30)
                self.avatar_pixmap_label.setPixmap(rounded_pixmap)
                
            else:
                debuglog.error(f"[MAIN] Ошибка загрузки аватара: {response.status_code}")
                self.set_default_avatar_svg()
                
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка загрузки аватара: {e}")
            self.set_default_avatar_svg()

    def create_rounded_pixmap(self, pixmap, size):
        if pixmap.isNull():
            return QPixmap()

        img_ratio = pixmap.width() / pixmap.height()
        circle_ratio = size / size
        
        if img_ratio > circle_ratio:
            scaled_height = size
            scaled_width = int(size * img_ratio)
        else:
            scaled_width = size
            scaled_height = int(size / img_ratio)
        
        scaled_pixmap = pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        x = (size - scaled_width) // 2
        y = (size - scaled_height) // 2
        
        rounded = QPixmap(size, size)
        rounded.fill(Qt.transparent)
        
        painter = QPainter(rounded)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
        
        return rounded

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

    def save_window_settings(self):
        """Сохранить размер и положение окна"""
        try:
            if not self._normal_geometry:
                if self._is_maximized:
                    self._normal_geometry = self._default_geometry
                else:
                    self._normal_geometry = self.geometry()

            if isinstance(self._normal_geometry, QRect):
                geom = [
                    self._normal_geometry.x(),
                    self._normal_geometry.y(),
                    self._normal_geometry.width(),
                    self._normal_geometry.height()
                ]
            else:
                geom = self._normal_geometry

            settings = {
                'geometry': geom,
                'state': {
                    '_is_maximized': self._is_maximized
                }
            }

            with open(winsize_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

        except Exception as e:
            logger.error(f"[WINDOW] Ошибка сохранения настроек: {e}")
    
    def load_window_settings(self):
        """Загрузить сохраненные размеры окна"""
        try:
            if not os.path.exists(winsize_file):
                with open(winsize_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                return {}

            with open(winsize_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            debuglog.info("[MAIN] Размеры окна загружены")

            if 'state' in settings:
                if settings['state'].get('is_maximized'):
                    self._is_maximized = True
                    self.showMaximized()
                else:
                    g = settings["geometry"]
                    if isinstance(g, (list, tuple)) and len(g) == 4:
                        rect = QRect(g[0], g[1], g[2], g[3])
                        self.setGeometry(rect)

        except Exception as e:
            logger.error(f"[WINDOW] Ошибка загрузки настроек: {e}")

    def showMaximized(self):
        """Кастомное максимизирование для безрамного окна"""
        super().showMaximized()

        screen = QApplication.primaryScreen()
        available_geometry = screen.availableGeometry()

        self.setGeometry(available_geometry)

        self.setContentsMargins(0, 0, 0, 0)

    def show_normal_window(self):
        self.setGeometry(self._default_geometry)

    def toggle_maximize(self, animate=True):
        """Переключение максимизации с опциональной анимацией"""
        self.resize_animation.stop()
        
        if self._is_maximized:
            if self._normal_geometry:
                target_geo = self._normal_geometry
            else:
                target_geo = self._default_geometry
            
            start_geo = self.geometry()
            
            self._is_maximized = False
            
            if animate:
                self.resize_animation.setStartValue(start_geo)
                self.resize_animation.setEndValue(target_geo)
                self.resize_animation.start()
                
                def on_animation_finished():
                    self.central_widget.setObjectName("MainWindowWidget")
                    self.close_button.setObjectName("TitleBarCloseBtn")
                    self.title_bar_widget.setObjectName("TitleBarV2")
                    self.apply_styles()
                
                self.resize_animation.finished.connect(on_animation_finished)
                self.resize_animation.finished.connect(lambda: self.resize_animation.finished.disconnect())
            else:
                self.setGeometry(target_geo)
                self.central_widget.setObjectName("MainWindowWidget")
                self.close_button.setObjectName("TitleBarCloseBtn")
                self.title_bar_widget.setObjectName("TitleBarV2")
                self.apply_styles()
            
        else:
            self._normal_geometry = self.geometry()
            screen = QApplication.primaryScreen()
            target_geo = screen.availableGeometry()
            
            start_geo = self.geometry()
            self._is_maximized = True
            
            if animate:
                self.resize_animation.setStartValue(start_geo)
                self.resize_animation.setEndValue(target_geo)
                self.resize_animation.start()
                
                def on_animation_finished():
                    self.central_widget.setObjectName("FullWindowMode")
                    self.close_button.setObjectName("FullWindowMode_CloseBtn")
                    self.title_bar_widget.setObjectName("FullWindowMode_TitleBar")
                    self.apply_styles()

                    if hasattr(self, 'snow_on_background') and self.snow_on_background:
                        self.snow_on_background.setGeometry(self.central_widget.rect())
                        self.snow_on_background._init_snowflakes()
                        self.snow_on_background.update()
                        
                    if hasattr(self, 'garland_decorator') and self.garland_decorator:
                        self.garland_decorator.update_size(self.width())
                
                self.resize_animation.finished.connect(on_animation_finished)
                self.resize_animation.finished.connect(lambda: self.resize_animation.finished.disconnect())
            else:
                self.setGeometry(target_geo)
                self.central_widget.setObjectName("FullWindowMode")
                self.close_button.setObjectName("FullWindowMode_CloseBtn")
                self.title_bar_widget.setObjectName("FullWindowMode_TitleBar")
                self.apply_styles()

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

            svg_attrs = ['style_svg', 'avatar_svg', 'svg_image', 'logo_svg', 'update_light_svg', 'clear_logs_svg', 'update_all_preset_svg', 'max_svg']

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
            if hasattr(self, "snow_on_background"):
                self.snow_on_background.setSnowColor(self.style_manager.get_raw_color(), white_balance=50)
                
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка в методе apply_styles: {e}")

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

    def show_toast(self, message):
        try:
            is_window_hidden = self.isMinimized() or not self.isVisible()

            toast = ToastNotif(
                parent=None if is_window_hidden else self,
                message=message,
                timeout=5000
            )
            toast.show_toast()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при показе всплывающего уведомления: {e}")

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
            debuglog.error(f"[MAIN] Ошибка при показе уведомления(оконного): {e}")
            return QDialog.DialogCode.Rejected

    def show_supply_notice(self, message, is_confirm=False):
        """Вызывается из фонового потока - emits signal"""
        try:
            self.supply_notice_signal.emit(message, is_confirm)
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при отправке сигнала уведомления: {e}")

    def _handle_supply_notice(self, message, is_confirm=False):
        """Выполняется в главном потоке Qt (обработчик сигнала)"""
        try:
            if is_confirm:
                default_text = ""
            else:
                default_text = "Распознано: "
            toast = ToastNotif(
                parent=None,
                message=f"{default_text}{message}",
                timeout=5000
            )
            toast.show_toast()

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при показе всплывающего уведомления: {e}")

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

    def open_update_app(self):
        """Запускает скрипт для установки обновления"""
        try:
            self.update_app(type_version=self.type_version)
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при запуске программы обновления: {e}")

    #  тут исправлена логика обработки ручной проверки
    @Slot()
    def update_answer(self, event):
        """Реакция бота на отсутствие обновления"""
        try:
            self.is_manual_check = True  # Устанавливаем флаг ручной проверки
            self.check_update_app()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при запуске программы обновления: {e}")

    def handle_update_status(self, is_success, status_text):
        """Обрабатывает результат проверки обновлений"""
        if not self.is_manual_check:  # Пропускаем реакцию для автоматических проверок
            return

        # Реагируем только если это ручная проверка
        if status_text == "Stable":
            self.get_reaction(detail=True, name="update_button")
        elif status_text == "New version":
            pass
        elif not is_success:
            self.get_reaction(detail=True, name="error_file")

        self.is_manual_check = False

    def toggle_update_button(self):
        """
        Метод для отображения или скрытия кнопки "Установить обновление"
        """
        if self.update_label.text() == "New version": # Stable New version 
            self.update_btn.show()
            self.style_manager.apply_color_svg(self.update_svg, strength=0.90, specified_color="#44D14F")
        else:
            self.update_btn.hide()
            
    def update_complete(self):
        from send2trash import send2trash
        
        download_dir = get_path("update")
        temp_dir = get_path("update_pack")
        backup_dir = get_path("old_files_backup")
        
        current_version = self.get_version()
        batch_dir = get_path("update", f"{current_version}_temp")

        # Удаление в корзину папки update_pack
        if os.path.exists(temp_dir):
            try:
                send2trash(temp_dir)
                debuglog.info(f"[MAIN] Папка update_pack отправлена в корзину: {temp_dir}")
            except Exception as e:
                debuglog.error(f"[MAIN] Не удалось удалить {temp_dir}: {e}")

        # Удаление в корзину папки бэкапа
        if os.path.exists(backup_dir):
            try:
                send2trash(backup_dir)
                debuglog.info(f"[MAIN] Папка бэкапа отправлена в корзину: {backup_dir}")
            except Exception as e:
                debuglog.error(f"[MAIN] Не удалось удалить {backup_dir}: {e}")
                
        # Удаление в корзину batch_dir
        if os.path.exists(batch_dir):
            try:
                send2trash(batch_dir)
                debuglog.info(f"[MAIN] Папка batch_dir отправлена в корзину: {batch_dir}")
            except Exception as e:
                debuglog.error(f"[MAIN] Не удалось удалить {batch_dir}: {e}")

        # Удаление .zip файлов в корзину
        if os.path.exists(download_dir):
            for old_file in os.listdir(download_dir):
                old_path = os.path.join(download_dir, old_file)
                if os.path.isfile(old_path) and old_file.endswith('.zip'):
                    try:
                        send2trash(old_path)
                        debuglog.info(f"[MAIN] Файл отправлен в корзину: {old_path}")
                    except Exception as e:
                        debuglog.error(f"[MAIN] Не удалось удалить {old_path}: {e}")

    def animation_start_load(self):
        self.progress_load.show()
        self.progress_load.startAnimation()

    def animation_stop_load(self):
        self.progress_load.hide()
        self.progress_load.stopAnimation()

    def check_update_app(self):
        """Проверяет обновления"""
        if self.stop_checking:
            return
        try:
            self.animation_start_load()
            self.toggle_update_button()
            self.update_label.setText("Searching...")

            task = VersionCheckThread()
            task.signals.version_checked.connect(self.handle_version_check)
            task.signals.check_failed.connect(self.handle_check_failed)

            QThreadPool.globalInstance().start(task)

        except Exception as e:
            self.animation_stop_load()
            debuglog.error(f"[MAIN] Неожиданная ошибка: {str(e)}", exc_info=True)
            self.update_label.setText("Failed update")
            QTimer.singleShot(2000, self.check_update_app)

    def handle_version_check(self, stable_version, exp_version):
        # Обработка полученных версий
        new_version = exp_version if self.beta_version else stable_version
        self.latest_version = version.parse(new_version)
        self.current_ver = version.parse(self.version)

        type_version = "exp" if self.beta_version else "stable"

        load_changelog(self.changelog_file_path)

        if self.latest_version > self.current_ver:
            self.start_full_download()
        else:
            self.animation_stop_load()
            self.update_label.setText("Stable")
            self.toggle_update_button()
            self.update_checked.emit(True, "Stable")
            self.stop_checking = False
            QTimer.singleShot(4000, lambda: self.update_complete())


    def start_full_download(self):
        """Запуск загрузки полной версии"""
        self.update_label.setText("Loading...")
        type_version = "exp" if self.beta_version else "stable"
        self.download_thread = DownloadThread(type_version)
        self.download_thread.download_complete.connect(self.handle_download_complete)
        self.download_thread.finished.connect(self.animation_stop_load)
        self.download_thread.start()
        self.toggle_update_button()

    def handle_check_failed(self):
        self.count += 1
        self.animation_stop_load()
        self.update_label.show()
        self.update_label.setText("Failed connection")
        if self.count == 3:
            self.update_label.setText("Server error")  
        if self.count <= 2: # 3 попытки на запрос версии в случае неудачи
            QTimer.singleShot(2000, self.check_update_app)
    
    def handle_download_complete(self, file_path, success=True, skipped=False, error=None, batch=False):
        self.animation_stop_load()
        self.update_label.setText("New version")
        if success:
            self.type_version = "exp" if "exp_" in os.path.basename(file_path).lower() else "stable"
            self.show_toast(f"Доступно обновление (v.{self.latest_version})")
            self.stop_checking = True
            if skipped:
                self.show_toast("Подготовка к процедуре обновления...\n Не выключайте приложение")
                debuglog.info(f"[MAIN][SKIP] Файл уже существует")
                self.open_window_and_update()
            else:
                debuglog.info(f"[MAIN][OK] Новый файл загружен")
        else:
            debuglog.error(f"[MAIN] Не удалось скачать: {error}")
        
        self.toggle_update_button()

    def open_window_and_update(self):
        """Обработка действия, если апдейт уже был скачан (активация окна)"""
        if not self.isVisible():
            self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        QApplication.processEvents()
        QTimer.singleShot(500, lambda: self.update_app(type_version=self.type_version))

    def check_or_create_folders(self):
        links_path = folder_links
        screenshot_path = folder_screenshots
        path_list = [links_path, screenshot_path]

        for folder_path in path_list:
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                debuglog.info(f"[MAIN] Папка {folder_path} найдена")
            else:
                try:
                    os.makedirs(folder_path)
                    debuglog.info(f'[MAIN] Папка {folder_path} была создана.')
                except Exception as e:
                    debuglog.error(f'[MAIN] Ошибка при создании папки {folder_path}: {e}')

    def reload_commands(self):
        """Централизованное сохранение команд"""
        self.commands = self.commands_manager.commands

    def load_settings(self):
        """Загружает настройки из settings.json."""
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_settings(self):
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
            "minimize_to_tray": self.is_min_tray,
            "is_start_win": self.is_start_win,
            "is_widget": self.is_widget,
            "is_keep_watch": self.is_keep_watch,
            "input_device_id": self.input_device_id,
            "input_device_name": self.input_device_name,
            "is_snow": self.is_snow,
            "is_garland": self.is_garland
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

            self.show_toast("Настройки сохранены!")
            debuglog.debug("[MAIN] Настройки сохранены.")
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при сохранении настроек: {e}")
            debuglog.error(f"[MAIN] Ошибка при сохранении настроек: {e}")
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
                "assist_name2": "джон",
                "assist_name3": "джон",
                "steam_path": "",
                "is_censored": True,
                "volume_assist": 0.15,
                "run_updater": True,
                "is_corrected_command": False,
                "minimize_to_tray": True,
                "is_start_win": True,
                "is_widget": True,
                "is_keep_watch": False,
                "input_device_id": None,
                "input_device_name": None,
                "is_snow": True,
                "is_garland": True
            }

        # Загружаем текущие настройки
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as file:
                try:
                    settings = json.load(file)
                except json.JSONDecodeError:
                    settings = {}
        else:
            settings = {}

        # Обновляем настройки, если ключи отсутствуют
        updated = False
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
                updated = True

        # Сохраняем обновленные настройки, если они изменились
        if updated:
            with open(settings_file, "w", encoding="utf-8") as file:
                json.dump(settings, file, ensure_ascii=False, indent=4)

        return settings

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
        self.save_window_settings()
        if hasattr(self, "logs_widget"):
            self.logs_widget.log_area.stop_monitoring()

        if self.is_assistant_running:
            self.stop_assist()
        event.accept()

    def on_shutdown(self):
        try:
            self.logs_widget.log_area.stop_monitoring()
            self.force_close()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при закрытии приложения: {e}")

    def close_app(self):
        """Закрытие приложения."""
        if self.is_assistant_running:
            self.stop_assist()
            self.logs_widget.log_area.stop_monitoring()
            QTimer.singleShot(2500, self.force_close) # Время для проигрывания аудио перед закрытием
        else:
            self.force_close()

    def force_close(self):
        """Принудительное закрытие, игнорируя все подтверждения"""
        self.logs_widget.log_area.stop_monitoring()
        self.close()

        # Гарантированное завершение через 100 мс
        QTimer.singleShot(100, lambda: [
            QApplication.closeAllWindows(),
            QApplication.quit()
        ])

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
            debuglog.error(f"[MAIN] Ошибка при завершении: {e}")
            self.close()

    def start_assist_toggle(self):
        """Обработка нажатия кнопки 'Старт ассистента' или 'Остановить работу'"""
        if self.is_assistant_running:
            self.stop_assist()
        else:
            self.run_assist()

    def run_assist(self):
        """Запуск ассистента"""
        self.is_assistant_running = True
        self.animated_sidebar.update_element_text("toggle_worker", "Остановить работу")
        logger.debug("Ассистент запущен...")

        # Запуск ассистента в отдельном потоке
        self.assistant_thread = threading.Thread(target=self.run_script)
        self.assistant_thread.start()

    def stop_assist(self, reaction=True):
        """Остановка ассистента"""
        self.is_assistant_running = False
        self.animated_sidebar.update_element_text("toggle_worker", "Старт ассистента")
        debuglog.info("[MAIN][Ассистент остановлен]")
        if reaction:
            debuglog.info("[MAIN] Реакция на выключение ассистента...")
            self.get_reaction(threading=True, name="close_assist_folder", trace="stop_assist in main")

        # Безопасная остановка потока
        if hasattr(self, 'assistant_thread') and self.assistant_thread is not None:
            try:
                if self.assistant_thread.is_alive() and self.assistant_thread != threading.current_thread():
                    self.assistant_thread.join(timeout=1.0)
                    if self.assistant_thread.is_alive():
                        debuglog.warning("[MAIN] Поток ассистента не завершился в течение таймаута")
            except Exception as e:
                debuglog.error(f"[MAIN] Ошибка при остановке потока: {e}")
            finally:
                self.assistant_thread = None

        # Очистка аудиоресурсов
        self.cleanup_audio_resources()

    def get_reaction(self, threading=True, detail=False, name="", trace=""):
        try:
            path = self.audio_paths.get(f'{name}')
            if not path:
                logger.error(f"[MAIN][assistant.get_reaction] Путь не найден")
                debuglog.error(f"[MAIN][assistant.get_reaction] Путь не найден")
                return

            if threading:
                if detail:
                    thread_react_detail(path, trace)
                else:
                    thread_react(path, trace)
            else:
                react(path, trace)

        except Exception as e:
            debuglog.error(f"[MAIN][assistant.get_reaction] Ошибка: {e}")

    def censor_counter(self):
        """Добавляет запись о матерном слове в счетчик"""
        CSV_FILE = censor_file
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        
        today = datetime.now().date()  # Используем date вместо str
        today_str = today.strftime('%Y-%m-%d')
        
        data = []
        headers = ['date', 'score', 'total_score']
        file_exists = os.path.exists(CSV_FILE)
        
        if file_exists:
            try:
                with open(CSV_FILE, mode='r', encoding='utf-8', newline='') as file:
                    reader = csv.DictReader(file)
                    
                    if reader.fieldnames != headers:
                        debuglog.warning(f"[MAIN] Некорректные заголовки в файле {CSV_FILE}")
                        file_exists = False
                    else:
                        for row in reader:
                            try:
                                row_date = row['date'].strip()
                                score = int(row['score'] or 0)
                                total_score = int(row['total_score'] or 0)
                                
                                data.append({
                                    'date': row_date,
                                    'score': score,
                                    'total_score': total_score
                                })
                            except (ValueError, KeyError) as e:
                                debuglog.warning(f"[MAIN] Пропущена некорректная строка: {row}, ошибка: {e}")
                                continue
            except Exception as e:
                logger.error(f"[MAIN] Ошибка чтения файла {CSV_FILE}: {e}")
                debuglog.error(f"[MAIN] Ошибка чтения файла {CSV_FILE}: {e}")
                file_exists = False
        
        if not file_exists:
            data = []
            with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
        
        total_all_time = 0
        today_found = False
        
        for record in data:
            try:
                score_val = record['score']
                total_all_time += score_val
                
                if record['date'] == today_str:
                    today_found = True
                    record['score'] += 1
                    record['total_score'] = total_all_time + 1
            except KeyError:
                continue
        
        # Если запись на сегодня не найдена, добавляем новую
        if not today_found:
            total_all_time += 1  # Добавляем новое слово
            data.append({
                'date': today_str,
                'score': 1,
                'total_score': total_all_time
            })
        
        # Записываем обновленные данные
        try:
            with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            debuglog.debug(f"[MAIN] Счетчик обновлен. Сегодняшняя запись: {'обновлена' if today_found else 'добавлена'}")
            
        except Exception as e:
            logger.error(f"[MAIN] Ошибка записи в файл {CSV_FILE}: {e}")
            debuglog.error(f"[MAIN] Ошибка записи в файл {CSV_FILE}: {e}")
            
    def check_keywords_file(self):
        """
        Проверяет наличие файла keywords.json и создает его со стандартными значениями из default_keywords.json если нет
        """
        keywords_path = user_keywords
        default_keywords_path = get_path("bin", "default_keywords.json")

        if not os.path.exists(keywords_path):
            debuglog.info(f"[MAIN] Файл keywords.json не найден, создаю...")
            if os.path.exists(default_keywords_path):
                with open(default_keywords_path, 'r', encoding='utf-8') as f:
                    default_keywords = json.load(f)
            else:
                default_keywords = default_keywords_data
            os.makedirs(os.path.dirname(keywords_path), exist_ok=True)
            with open(keywords_path, 'w', encoding='utf-8') as f:
                json.dump(default_keywords, f, ensure_ascii=False, indent=2)

            return True
        else:
            debuglog.info(f"[MAIN] Файл keywords.json уже существует")
        
    def apply_keywords_for_values(self):
        try:
            keywords_path = user_keywords
            if os.path.exists(keywords_path):
                with open(keywords_path, 'r', encoding='utf-8') as f:
                    keywords_data = json.load(f)
            
            self.keywords_shutdown = keywords_data["keywords_shutdown"]
            self.keywords_restart = keywords_data["keywords_restart"]
            self.keywords_search = keywords_data["keywords_search"]
            self.keywords_no = keywords_data['keywords_no']
            self.keywords_yes = keywords_data['keywords_yes']
            self.keywords_reject = keywords_data['keywords_reject']
            self.screen_list = keywords_data["screen_list"]
            self.fullscreen_list = keywords_data["fullscreen_list"]
            self.action_up = keywords_data['action_up']
            self.action_down = keywords_data['action_down']
            self.all_actions = self.action_up + self.action_down
            self.keywords_player = keywords_data["keywords_player"]
            self.keywords_playpause = keywords_data['keywords_playpause']
            self.keywords_next = keywords_data["keywords_next"]
            self.keywords_prev = keywords_data["keywords_prev"]
            self.censored_list = keywords_data["censored_list"]
            return True
        except Exception as e:
            debuglog.error(f"Ошибка во время применения списков: {e}")
            return False

    # "Основной цикл ассистента"
    # "--------------------------------------------------------------------------------------------------"
    # "Основной цикл ассистента"

    def run_script(self):
        """Основной цикл ассистента"""
        greeting()
        default_commands = {
            'микшер': (open_volume_mixer, close_volume_mixer),
            'калькулятор': (open_calc, close_calc),
            'пейнт': (open_paint, close_paint),
            'переменные': (open_path, None),
            'диспетчер': (open_taskmgr, close_taskmgr),
            'корзина': (open_recycle_bin, close_recycle_bin),
            'ап дата': (open_appdata, close_appdata),
            'панель': (self._open_widget_signal, self._close_widget_signal),
            'виджет': (self._open_widget_signal, self._close_widget_signal),
            "микрофон": (self.toggle_mute_discord, self.toggle_mute_discord),
            "микро": (self.toggle_mute_discord, self.toggle_mute_discord),
            "ютуб": (lambda: self.start_default_command("ютуб", "open", "url"), None),
            "блютуз": (self.bluetooth.enable, self.bluetooth.disable)
        }
        default_commands_keys = list(default_commands.keys())

        self.last_unrecognized_command = None  # Хранит контекст неудачной команды
        last_activity_time = time.time()  # Время последней активности
        name_mentioned_time = None  # Время последнего упоминания имени ассистента
        name_mentioned = False  # Флаг, что имя было упомянуто
        has_action_words = True
        if not self.initialize_audio():
            return

        try:
            for text in self.get_audio():
                if not self.is_assistant_running:
                    break
                self.command_handled = False
                debuglog.info(f"[last_unrecognized_command]---> {self.last_unrecognized_command}")
                current_time = time.time()
                
                words = text.split()

                all_commands = self.get_command_names()
                all_names = [self.assistant_name, self.assist_name2, self.assist_name3]

                # Список фраз действие-команда, ["action command", ...]
                action_command = self.handle_text_smart(text, self.all_actions, threshold=60)

                # Чистая команда без действия, "command"
                clean_target = self._extract_clean_target(text, self.all_actions)

                if self.find_action(text, self.action_up, self.action_down, self.all_actions)[0] is not None:
                    has_action_words = True
                else:
                    has_action_words = False
                
                # Проверка на наличие команд для управления    
                self.is_keyword_player = any(self.find_closest_command(word, self.keywords_player, threshold=80) for word in words)

                debuglog.info(f"[MAIN][FIRST_HANDLER][has_action_words] {has_action_words}")

                debuglog.info(f"[MAIN][FIRST_HANDLER][Raw Text] {text}")
                debuglog.info(f"[MAIN][FIRST_HANDLER][Action] {action_command}")
                debuglog.info(f"[MAIN][FIRST_HANDLER][Clean Command] {clean_target}")

                # Сбрасываем контекст, если прошло более 10 секунд без активности
                if self.last_unrecognized_command and (current_time - last_activity_time) > 10:
                    self.last_unrecognized_command = None
                    logger.info("Сброс контекста из-за неактивности")
                    debuglog.info("[MAIN] Сброс контекста из-за неактивности")

                # Обновляем время последней активности при получении текста
                last_activity_time = current_time

                # Сбрасываем флаг упоминания имени, если прошло более n секунд
                if name_mentioned and (current_time - name_mentioned_time) > 20:
                    name_mentioned = False
                    name_mentioned_time = None
                    logger.info("Сброс флага упоминания имени")
                    debuglog.info("[MAIN] Сброс флага упоминания имени")

                # Проверка цензуры
                if any(self.find_closest_command(word, self.censored_list, threshold=80) for word in words):
                    self.censor_counter()
                    if self.is_censored:
                        self.get_reaction(name="censored_folder")

                # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                # ОБРАБОТКА ПОДТВЕРЖДЕНИЯ КОМАНДЫ ("ДА"/"НЕТ")
                # Если мы ожидаем подтверждение — игнорируем всё, кроме "да" или "нет"
                if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'confirm':
                    if self.last_unrecognized_command.get('is_shutdown'):
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            logger.info("Таймаут подтверждения — сброс")
                            debuglog.info("[MAIN] Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            debuglog.info("[MAIN] Пользователь подтвердил команду(ы).")

                            turnoff_value = self.last_unrecognized_command.get('is_shutdown')
                            self.set_shutdown(is_shutdown=turnoff_value)

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            debuglog.info("[MAIN] Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            debuglog.info("[MAIN] Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue
                    else:
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            logger.info("Таймаут подтверждения — сброс")
                            debuglog.info("Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            debuglog.info("[MAIN] Пользователь подтвердил команду(ы).")

                            pending_commands = self.last_unrecognized_command.get('pending_commands')

                            any_executed = False

                            for cmd_info in pending_commands:
                                action_type = cmd_info['action_type']
                                suggested_cmd = cmd_info['suggested_command']

                                debuglog.info(f"[MAIN] Выполняем: {action_type} {suggested_cmd}")

                                # Пробуем стандартные команды
                                default_list = self.find_closest_command(suggested_cmd, default_commands_keys)
                                if default_list:
                                    if action_type == 'open' and default_commands[default_list][0]:
                                        default_commands[default_list][0]()
                                        any_executed = True
                                    elif action_type == 'close' and default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                                        any_executed = True
                                else:
                                    # Пробуем кастомные команды
                                    type_processed = self.commands_manager.get_type_command(suggested_cmd)
                                    if type_processed == "shortcut" or type_processed == "url":
                                        self.handle_app_command(suggested_cmd, action_type)
                                    elif type_processed == "folder":
                                        self.handle_folder_command(suggested_cmd, action_type)
                                    elif type_processed == "script":
                                        self.handle_script_command(suggested_cmd, action_type)

                                    if type_processed != "":
                                        any_executed = True

                            if any_executed:
                                pass
                            else:
                                self.get_reaction(detail=True, name="error_file")
                                message = "Не удалось выполнить команду(ы)."
                                self.show_supply_notice(message, is_confirm=True)
                                debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            debuglog.info("[MAIN] Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            debuglog.info("[MAIN] Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                            continue

                # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                # Условие. Проверка на упоминание имени ассистента

                words = text.split()
                has_name = any(
                    self.find_closest_command(word, all_names, threshold=70) is not None
                    for word in words
                )

                if len(words) <= 4 and has_name:
                    name_mentioned = True
                    name_mentioned_time = current_time

                # Проверка на наличие имени ассистента в тексте или флаг упоминания
                has_assistant_name = (self.assistant_name in text or
                                      self.assist_name2 in text or
                                      self.assist_name3 in text or
                                      name_mentioned)

                # Режим уточнения команды (если предыдущая попытка не удалась)
                if self.is_corrected_command:
                    debuglog.info(f"[MAIN][RETRY][Start Mode Correction]")
                    if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'correction':
                        if text:
                            # Обновляем время последней активности при обработке команды
                            last_activity_time = current_time

                            _, new_action_type = self.find_action(text, self.action_up, self.action_down, self.all_actions)

                            current_action_type = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                            # Если действие изменилось — обновляем контекст
                            if new_action_type and new_action_type != current_action_type:
                                self.last_unrecognized_command['pending_commands'][0]['action_type'] = new_action_type
                                debuglog.info(f"[MAIN][RETRY] Действие обновлено на: {new_action_type}")

                            # Блок А. Для поиска совпадений и запуска методов в соответствии с действием
                            default_list = self.find_closest_command(clean_target, default_commands_keys)

                            if default_list:
                                action_to_use = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                                if action_to_use == 'open':
                                    default_commands[default_list][0]()
                                elif action_to_use == 'close':
                                    if default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                                self.last_unrecognized_command = None
                                continue
                            # Конец блока А.

                            # Блок В. Для поиска совпадений из кастомного списка команд и их активация
                            file_commands = list(self.commands.keys()) if hasattr(self, 'commands') and isinstance(
                                self.commands, dict) else []
                            custom_list = self.find_closest_command(clean_target, file_commands)

                            if custom_list:
                                action_type = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                                # Восстанавливаем полную команду
                                restored_command = f"{action_type} {custom_list}"
                                debuglog.info(f"[MAIN][RETRY] Восстановленная команда: {restored_command}")

                                type_processed = self.commands_manager.get_type_command(custom_list)
                                debuglog.info(f"[MAIN][RETRY] Команда: {custom_list}, тип: {type_processed}")
                                if type_processed == "shortcut" or type_processed == "url":
                                    self.handle_app_command(custom_list, action_type)
                                elif type_processed == "folder":
                                    self.handle_folder_command(custom_list, action_type)
                                elif type_processed == "script":
                                    self.handle_script_command(custom_list, action_type)
                                else:
                                    logger.warning(f"Команда не обработана: {restored_command}")
                                    debuglog.warning(f"[MAIN][RETRY] Команда не обработана: {restored_command}")
                                    self.get_reaction(name="what_folder",
                                                    trace="Реакция в блоке, где режим корректировки команды")

                                    self.last_unrecognized_command['pending_commands'][0][
                                        'suggested_command'] = clean_target

                                    debuglog.info(f"[MAIN][RETRY] Обновлена цель для уточнения: {clean_target}")
                                    self.show_supply_notice(text)
                                    debuglog.info(f"[MAIN][RETRY] Отправлено уведомление ---> {text}")
                                    self.last_unrecognized_command = None
                                    continue
                            # Конец блока В.

                            if any(word in text for word in self.keywords_reject):
                                debuglog.info("[MAIN] Пользователь отменил команду(ы).")
                                self.get_reaction(name="confirm_folder")
                                self.last_unrecognized_command = None
                                message = "Хорошо, отменяю."
                                self.show_supply_notice(message, is_confirm=True)
                                debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")
                                continue

                            if not default_list and not custom_list:
                                self.get_reaction(name="what_folder",
                                                trace="Реакция в блоке, где режим корректировки команды")
                                self.show_supply_notice(text)
                                debuglog.info(f"[MAIN] Отправлено уведомление ---> {text}")

                if has_assistant_name:
                    debuglog.info("[MAIN] <<< Условие, где есть Имя ассистента >>>")
                    trigger_react = False
                    _, action_type = self.find_action(text, self.action_up, self.action_down, self.all_actions)
                    if self.find_any_command_in_text(clean_target, self.keywords_search, threshold=80):
                        search_yandex(text, self.assistant_name, self.assist_name2, self.assist_name3)
                        self.get_reaction(name="approve_folder")
                        continue
                    elif self.find_closest_command(clean_target, self.fullscreen_list, threshold=70):
                        self.capture_fullscreen()
                        continue
                    elif self.find_closest_command(clean_target, self.screen_list, threshold=70):
                        self.capture_area()
                        continue
                    elif self.find_closest_command(clean_target, self.keywords_shutdown):
                        self.get_confirm_shutdown(clean_target, text, action_type)
                        continue
                    elif self.find_closest_command(clean_target, self.keywords_restart, threshold=90):
                        self.get_confirm_shutdown(clean_target, text, action_type, is_shutdown=False)
                        continue

                    if len(words) <= 4 and has_name:
                        if not has_action_words:
                            if not self.is_keyword_player:
                                # Если нет слов-действий и в тексте нет команд для управления плеером — воспроизводим эхо
                                self.get_reaction(name="echo_folder")

                    final_commands = self.handle_text_smart(text, self.all_actions, threshold=60)
                    debuglog.info(f"[MAIN][HAS_NAME][handle_text_smart] {final_commands}")

                    for command in final_commands:
                        command = command.strip()
                        debuglog.info(f"[MAIN][Команда в цикле из списка выше] {command}")

                        _, action_type = self.find_action(command, self.action_up, self.action_down, self.all_actions)

                        if action_type:
                            clean_target = self._extract_clean_target(command, self.all_actions)
                            # Ищем совпадение со специальными командами

                            default_list = self.find_closest_command(clean_target, default_commands_keys)
                            debuglog.info(f"[MAIN][HAS_NAME][list] {default_list}")
                            debuglog.info(f"[MAIN][HAS_NAME][action_type] {action_type}")
                            debuglog.info(f"[MAIN][HAS_NAME][clean_target] {clean_target}")

                            if default_list:
                                self.command_handled = True
                                if action_type == 'open':
                                    default_commands[default_list][0]()
                                elif action_type == 'close':
                                    if default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                            else:
                                # Пытаемся обработать команду
                                type_processed = self.commands_manager.get_type_command(clean_target)
                                debuglog.info(f"[MAIN][HAS_NAME] Команда: {clean_target}, тип: {type_processed}")
                                self.command_handled = True
                                if type_processed == "shortcut" or type_processed == "url":
                                    self.handle_app_command(clean_target, action_type)
                                elif type_processed == "folder":
                                    self.handle_folder_command(clean_target, action_type)
                                elif type_processed == "script":
                                    self.handle_script_command(clean_target, action_type)
                                else:
                                    if clean_target:
                                        # Ищем похожие команды
                                        closest_cmd = self.find_closest_command(clean_target, all_commands)
                                        debuglog.info(f"[MAIN][closest_cmd] {closest_cmd}")

                                        if closest_cmd:
                                            message = f"Вы имели в виду: '{closest_cmd}'?\nСкажите: Да/Нет"
                                            self.show_supply_notice(message, is_confirm=True)
                                            thread_play_sound(type_sound="what")
                                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")

                                            # Сохраняем контекст с предложенной командой + флаг ожидания подтверждения
                                            self.last_unrecognized_command = {
                                                'mode': 'confirm',
                                                'original_text': text,
                                                'pending_commands': [{
                                                    'action_type': action_type,
                                                    'suggested_command': closest_cmd
                                                }]
                                            }
                                        else:
                                            self.last_unrecognized_command = {
                                                'mode': 'correction',
                                                'original_text': text,
                                                'pending_commands': [{
                                                    'action_type': action_type,
                                                    'suggested_command': clean_target
                                                }]
                                            }
                                            trigger_react = True
                                            break
                                        
                                if type_processed != "":
                                    self.command_handled = True

                    if trigger_react:
                        self.command_handled = True
                        self.show_supply_notice(text)
                        self.get_reaction(name="what_folder", trace="Реакт из триггера")
                        debuglog.info(f"[MAIN] Сработал триггер реакции. Отправлено уведомление ---> {text}")
                        continue

                # Флаг для контроля над обработкой команд без имени ассистента (не относится к плееру)
                if self.is_keep_watch:
                    if has_action_words and not has_assistant_name:
                        debuglog.info("[MAIN] <<< Условие без имени ассистента, только действие и команда >>>")

                        if self.find_closest_command(clean_target, self.screen_list):
                            self.capture_area()

                        final_commands = self.handle_text_smart(text, self.all_actions, threshold=60)
                        debuglog.info(f"[MAIN] [final_commands] {final_commands}")

                        pending_commands = []

                        for command in final_commands:
                            command = command.strip()
                            clean_target = self._extract_clean_target(command, self.all_actions)
                            if not clean_target:
                                continue

                            _, action_type = self.find_action(command, self.action_up, self.action_down, self.all_actions)
                            if not action_type:
                                continue

                            closest_cmd = self.find_closest_command(clean_target, all_commands)
                            if not closest_cmd:
                                continue

                            debuglog.info(f"[MAIN][command] {command}")
                            debuglog.info(f"[MAIN][clean_target] {clean_target}")
                            debuglog.info(f"[MAIN][closest_cmd] {closest_cmd}")

                            pending_commands.append({
                                'action_type': action_type,
                                'suggested_command': closest_cmd,
                                'original_command': command
                            })

                        if pending_commands:
                            # Формируем сообщение
                            action_groups = {'open': [], 'close': []}
                            for cmd in pending_commands:
                                action_groups[cmd['action_type']].append(cmd['suggested_command'])

                            parts = []
                            if action_groups['open']:
                                parts.append(f"Включить: {', '.join(action_groups['open'])}")
                            if action_groups['close']:
                                parts.append(f"Выключить: {', '.join(action_groups['close'])}")

                            message = ";\n".join(parts) + "\n\nСкажите: Да/Нет"
                            self.show_supply_notice(message, is_confirm=True)
                            thread_play_sound(type_sound="what")
                            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = {
                                'mode': 'confirm',
                                'original_text': text,
                                'pending_commands': pending_commands
                            }
                            continue

                # Обработка плеера
                if not self.command_handled and (self.is_keyword_player or has_assistant_name):
                    debuglog.info("[MAIN] Успешное условие для управления плеером")
                    # Ищем первое подходящее действие (в порядке приоритета: пауза, след, пред)
                    for word in words:
                        if self.find_closest_command(word, self.keywords_playpause, threshold=80):
                            controller.play_pause()
                            self.get_reaction(name="player_folder")
                            continue
                        elif self.find_closest_command(word, self.keywords_next, threshold=80):
                            controller.next_track()
                            self.get_reaction(name="player_folder")
                            continue
                        elif self.find_closest_command(word, self.keywords_prev, threshold=80):
                            controller.previous_track()
                            self.get_reaction(name="player_folder")
                            continue

        except Exception as e:
            logger.error(f"Ошибка в основном цикле ассистента: {e}")
            debuglog.error(f"[MAIN] Ошибка в основном цикле ассистента: {e}")
            debuglog.error(traceback.format_exc())
            self.show_toast(f"[MAIN] Ошибка в основном цикле ассистента: {e}")

    # "Основной цикл ассистента(конец)"
    # "--------------------------------------------------------------------------------------------------"
    # "Основной цикл ассистента(конец)"

    def get_confirm_shutdown(self, closest_cmd, text, action_type, is_shutdown=True):
        try:
            if is_shutdown:
                action_pc = "Выключить"
            else:
                action_pc = "Перезагрузить"
            message = f"{action_pc} ПК?\n\nСкажите: Да/Нет"
            self.show_supply_notice(message, is_confirm=True)
            thread_play_sound(type_sound="what")
            debuglog.info(f"[MAIN] Отправлено уведомление ---> {message}")

            # Сохраняем контекст
            self.last_unrecognized_command = {
                'mode': 'confirm',
                'original_text': text,
                'is_shutdown': action_pc,
            }
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка в методе get_confirm_shutdown: {e}")

    def set_shutdown(self, is_shutdown):
        try:
            if is_shutdown == "Выключить":
                shutdown_windows()
                debuglog.info("[MAIN] Выполняется обработка запроса: shutdown windows")
            elif is_shutdown == "Перезагрузить":
                restart_windows()
                debuglog.info("[MAIN] Выполняется обработка запроса: restart windows")

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка в методе set_shutdown: {e}")

    def _extract_clean_target(self, text, all_actions):
        """
        Извлекает чистую цель из текста: удаляет имя ассистента, слова-действия (нечётко!), артикли, союзы.
        Возвращает строку с предполагаемой целью.
        """
        if not text:
            return ""

        # Приводим к нижнему регистру
        clean_text = text.lower()

        # Разбиваем на слова
        words = clean_text.split()

        # Удаляем слова, содержащие имя ассистента (даже частично)
        names = [name.lower() for name in [self.assistant_name, self.assist_name2, self.assist_name3] if name]
        filtered_words = [
            word for word in words
            if not any(name in word for name in names)
        ]

        # Собираем обратно
        clean_text = " ".join(filtered_words)

        # Разбиваем снова для обработки действий
        words = clean_text.split()
        filtered_words = []

        # НЕЧЁТКОЕ УДАЛЕНИЕ слов-действий
        for word in words:
            # Ищем ближайшее действие для этого слова
            closest_action = self.find_closest_command(word, all_actions)
            # Если слово похоже на действие — пропускаем (удаляем)
            if not closest_action:
                filtered_words.append(word)

        clean_text = " ".join(filtered_words).strip()

        # Удаляем мусорные слова (союзы, предлоги)
        garbage_words = {"и", "а", "но", "или", "с", "на", "в", "по", "для", "это", "то", "там", "здесь", "же", "бы",
                         "что", "как"}
        words = clean_text.split()
        final_words = [word for word in words if word not in garbage_words]

        return " ".join(final_words).strip()

    def find_action(self, text, action_up, action_down, all_actions, threshold=50):
        """
        Ищет в тексте слово, наиболее похожее на любое из all_actions.
        Возвращает кортеж: (найденное_действие, тип_действия) или (None, None)
        """
        if not text:
            return None, None

        words = text.lower().split()
        best_action = None
        best_score = 0
        best_word = None

        for word in words:
            # Для каждого слова ищем ближайшее действие
            closest_action = self.find_closest_command(word, all_actions)
            if closest_action:
                # Получаем score (можно модифицировать find_closest_command, чтобы возвращал score)
                score = self._get_similarity_score(word, closest_action)
                if score > best_score:
                    best_score = score
                    best_action = closest_action
                    best_word = word

        if best_score >= threshold:
            if best_action in action_up:
                return best_action, 'open'
            elif best_action in action_down:
                return best_action, 'close'

        return None, None

    def _get_similarity_score(self, input_text, command):
        """
        Возвращает процент схожести между input_text и command (0-100)
        """
        if not input_text or not command:
            return 0
        distance = jellyfish.levenshtein_distance(input_text, command)
        max_len = max(len(input_text), len(command))
        if max_len == 0:
            return 100
        score = (1 - distance / max_len) * 100
        return score
    
    def find_any_command_in_text(self, input_text, command_list, threshold=50):
        """
        Ищет любую команду из списка в тексте (проверяет каждое слово текста)
        """
        if not input_text or not command_list:
            return None
        
        # Разбиваем текст на слова
        words = input_text.split()
        
        for word in words:
            # Для каждого слова ищем похожую команду
            best_match = self.find_closest_command(word, command_list, threshold)
            if best_match:
                return best_match
        
        return None

    def find_closest_command(self, input_text, command_list, threshold=50):
        """
        Возвращает наиболее похожую команду из списка, если схожесть >= threshold.
        """
        best_match = None
        best_score = 0

        for command in command_list:
            score = self._get_similarity_score(input_text, command)
            if score > best_score:
                best_score = score
                best_match = command

        # print("[best_match, best_score]", best_match, best_score)

        return best_match if best_score >= threshold else None

    def handle_text_smart(self, text, all_actions, threshold=50):
        """
        Умная обработка текста: берёт слова ПОСЛЕ каждого действия как цели.
        ФИКС: сначала ищет цель ЦЕЛИКОМ, только потом по частям.
        """
        if not text:
            return []

        text_lower = text.lower()
        words = text_lower.split()

        # 1. Находим все действия с позициями
        actions_in_text = []  # [(index, raw_word, normalized_action), ...]
        for i, word in enumerate(words):
            closest_action = self.find_closest_command(word, all_actions, threshold=50)
            if closest_action:
                actions_in_text.append((i, word, closest_action))

        if not actions_in_text:
            return []

        # 2. Для каждого действия — определяем "область целей"
        command_blocks = []  # [(action, start_idx, end_idx), ...]

        for i, (action_index, raw_action, norm_action) in enumerate(actions_in_text):
            start_idx = action_index + 1  # первое слово ПОСЛЕ действия
            if i + 1 < len(actions_in_text):
                end_idx = actions_in_text[i + 1][0]  # до следующего действия
            else:
                end_idx = len(words)  # до конца строки

            if start_idx < end_idx:  # есть хотя бы одно слово после действия
                command_blocks.append((norm_action, start_idx, end_idx))

        # 3. Извлекаем цели из каждой области
        final_commands = []
        all_targets = self.get_command_names()
        
        # Слова, которые всегда разделяют команды (не являются частью названия)
        SEPARATORS = {"и", "или", "а", "но", "затем", "потом", "а также"}
        # Мусорные слова для удаления
        GARBAGE_WORDS = {"с", "на", "в", "по", "для", "это", "то", "там", "здесь", "же", "бы", "что", "как"}

        for action, start, end in command_blocks:
            # Берем подмассив слов в области
            target_words = words[start:end]
            
            if not target_words:
                continue
            
            # 3.1. УДАЛЯЕМ МУСОРНЫЕ СЛОВА из target_words
            clean_target_words = [w for w in target_words if w not in GARBAGE_WORDS]
            if not clean_target_words:
                continue
                
            # 3.2. РАЗБИВАЕМ НА ПОДКОМАНДЫ по разделителям
            sub_commands = []  # список подкоманд (каждая = список слов)
            current_sub = []
            
            for word in clean_target_words:
                if word in SEPARATORS:
                    # Встретили разделитель → завершаем текущую подкоманду
                    if current_sub:
                        sub_commands.append(current_sub)
                        current_sub = []
                else:
                    # Обычное слово → добавляем в текущую подкоманду
                    current_sub.append(word)
            
            # Добавляем последнюю подкоманду, если есть
            if current_sub:
                sub_commands.append(current_sub)
            
            # Если разделителей не было → одна подкоманда со всеми словами
            if not sub_commands:
                sub_commands = [clean_target_words]
            
            # 3.3. ОБРАБАТЫВАЕМ КАЖДУЮ ПОДКОМАНДУ
            for sub_words in sub_commands:
                if not sub_words:
                    continue
                    
                # Вариант А: Пробуем найти цель ЦЕЛИКОМ
                full_target = " ".join(sub_words)
                closest_target = self.find_closest_command(full_target, all_targets, threshold=threshold)
                
                if closest_target:
                    # Нашли целиком → добавляем одну команду
                    cmd = f"{action} {closest_target}"
                    if cmd not in final_commands:  # избегаем дубликатов
                        final_commands.append(cmd)
                    continue
                
                # Вариант Б: Не нашли целиком → ищем по частям
                # Но только если подкоманда из 2+ слов
                if len(sub_words) >= 2:
                    # Пробуем все возможные n-граммы (от самых длинных к коротким)
                    found_any = False
                    for n in range(len(sub_words), 0, -1):
                        # Проверяем все n-граммы такой длины
                        for i in range(len(sub_words) - n + 1):
                            ngram = " ".join(sub_words[i:i+n])
                            closest = self.find_closest_command(ngram, all_targets, threshold=threshold)
                            if closest:
                                cmd = f"{action} {closest}"
                                if cmd not in final_commands:
                                    final_commands.append(cmd)
                                found_any = True
                                # Пропускаем слова, которые вошли в найденную n-грамму
                                    # (можно реализовать, но сложнее)
                    
                    if found_any:
                        continue
                
                # Вариант В: Не нашли даже частей → добавляем как есть (только не мусор)
                # Но проверяем, что это не разделитель
                if full_target not in SEPARATORS and full_target not in GARBAGE_WORDS:
                    cmd = f"{action} {full_target}"
                    if cmd not in final_commands:
                        final_commands.append(cmd)

        # 4. Убираем дубликаты команд
        seen_commands = set()
        unique_commands = []
        for cmd in final_commands:
            if cmd not in seen_commands:
                seen_commands.add(cmd)
                unique_commands.append(cmd)

        return unique_commands

    def get_command_names(self):
        """Возвращает объединённый список всех имён команд"""

        standard_commands = getattr(self, 'standard_commands', [
            "калькулятор",
            "диспетчер",
            "пейнт",
            "пэйнт",
            "панель",
            "корзина",
            "микшер",
            "переменные",
            "ап дата",
            "микрофон",
            "микро",
            "ютуб"
        ])

        file_commands = list(self.commands.keys()) if hasattr(self, 'commands') and isinstance(self.commands,
                                                                                               dict) else []

        standard_commands = [cmd.lower() for cmd in standard_commands]
        file_commands = [cmd.lower() for cmd in file_commands]

        # Убираем дубликаты с сохранением порядка
        seen = set()
        combined = []
        for cmd in standard_commands + file_commands:
            if cmd not in seen:
                seen.add(cmd)
                combined.append(cmd)

        return combined

    def restart_bot(self):
        self.stop_assist(reaction=False)
        QTimer.singleShot(3000, lambda: self.run_assist())

    def initialize_audio(self):
        """Инициализация моделей и аудиопотока через sounddevice."""
        self.cleanup_audio_resources()
        logger.info("Загрузка моделей для распознавания...")
        debuglog.debug("[MAIN] Загрузка моделей для распознавания...")

        model_path_ru = vosk_model_ru
        debuglog.debug(f"[MAIN] Загружена модель RU - {model_path_ru}")

        try:
            self.model_ru = Model(model_path_ru)
            logger.info("Модели успешно загружены.")
            debuglog.info("[MAIN] Модели успешно загружены.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели: {e}. Возможно путь содержит кириллицу.")
            debuglog.error(f"[MAIN] Ошибка при загрузке модели: {e}", exc_info=True)
            return False

        try:
            self.rec_ru = KaldiRecognizer(self.model_ru, 16000)

            target_id = self.get_microphone_id(self.input_device_name)
            if target_id is None:
                logger.warning("Не удалось определить микрофон. Используем устройство по умолчанию.")
                target_id = sd.default.device[0] if sd.default.device[0] < len(sd.query_devices()) else None

            if target_id is None:
                raise RuntimeError("Нет доступных входных устройств")

            try:
                self.audio_stream = sd.InputStream(
                    samplerate=16000,
                    channels=1,
                    dtype='int16',
                    blocksize=512,
                    device=target_id,
                    callback=self.audio_callback
                )
                self.audio_stream.start()
                self.input_device_id = target_id
                device_name = sd.query_devices(target_id)['name']
                self.input_device_name = device_name
                debuglog.info(f"[MAIN] Аудиопоток запущен: '{device_name}' (ID={target_id})")
            except Exception as e:
                debuglog.error(f"[MAIN] Не удалось открыть выбранное устройство (ID={target_id}): {e}")
                try:
                    self.audio_stream = sd.InputStream(
                        samplerate=16000,
                        channels=1,
                        dtype='int16',
                        blocksize=512,
                        callback=self.audio_callback
                    )
                    self.audio_stream.start()
                    fallback_id = sd.default.device[0]
                    fallback_name = sd.query_devices(fallback_id)['name']
                    self.input_device_id = fallback_id
                    self.input_device_name = fallback_name
                    debuglog.warning(f"[MAIN] Используется устройство по умолчанию: '{fallback_name}'")
                except Exception as e2:
                    debuglog.error("[MAIN] Не удалось запустить ни одно устройство.", exc_info=True)
                    raise e2

            self.microphone_available = True
            self.last_audio_time = time.time()
            return True

        except Exception as e:
            debuglog.error(f"[MAIN] Критическая ошибка при инициализации аудио: {e}", exc_info=True)
            return False

    def get_microphone_id(self, preferred_name=None):
        """Возвращает ID микрофона по имени"""
        try:
            devices = sd.query_devices()
            default_in = sd.default.device[0]
            candidates = []
            seen = set()

            for dev in devices:
                idx, name, ch = dev['index'], dev.get('name', ''), dev.get('max_input_channels', 0)
                if ch <= 0 or not name:
                    continue

                # Фильтр: системные, дубли, нежелательные
                clean = name.split('(')[0].strip()
                lower_name = name.lower()
                if (clean in seen or
                        any(kw in lower_name for kw in ['mapper', 'primary', 'wave', 'default', 'communications'])):
                    continue
                seen.add(clean)

                # Приоритет API: WASAPI > ASIO > остальные
                api_name = sd.query_hostapis(dev['hostapi'])['name'].lower()
                priority = {'wasapi': 3, 'asio': 2}.get(api_name, 1)

                try:
                    with sd.InputStream(device=idx, channels=1, samplerate=16000, blocksize=512):
                        candidates.append((idx, priority, preferred_name and preferred_name.lower() in lower_name))
                except Exception:
                    continue

            if candidates:
                best = max(candidates, key=lambda x: (x[2], x[1], -x[0]))
                return best[0]

            return default_in

        except Exception as e:
            debuglog.warning(f"[MAIN] Ошибка выбора микрофона: {e}")
            return sd.default.device[0]

    def audio_callback(self, indata, frames, time_info, status):
        """
        :param time_info: Временные метки от PortAudio
        """
        if status:
            debuglog.warning(f"Статус аудио: {status}")
            if any(keyword in str(status).lower() for keyword in ['overrun', 'underrun']):
                pass
            else:
                return

        if len(indata) == 0:
            return

        # === АНАЛИЗ ГРОМКОСТИ ===
        try:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            is_silent = rms < 20

            if not is_silent:
                self.last_audio_time = time.time()

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при анализе громкости: {e}")

        data = indata.tobytes()
        ru_text = ""
        en_text = ""

        try:
            if self.rec_ru.AcceptWaveform(data):
                result = json.loads(self.rec_ru.Result())
                ru_text = result.get("text", "").strip().lower()

            final_text = ru_text or en_text
            if final_text:
                self.on_final_result(final_text)

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка в обработке распознавания: {e}")

    def on_final_result(self, text):
        """Вызывается при распознавании фразы. Логирует и отправляет дальше."""
        logger.info(f"[Распознано] {text}")
        debuglog.info(f"[MAIN] [Распознано] {text}")

        if hasattr(self, '_current_queue') and self._current_queue is not None:
            try:
                self._current_queue.put(text)
            except Exception as e:
                logger.error(f"Не удалось положить текст в очередь: {e}")

    def get_audio(self):
        """
        Совместимый интерфейс: возвращает генератор текста.
        Но теперь работает через callback + очередь.
        """
        from queue import Queue
        q = Queue()

        self.text_queue = q
        self._current_queue = q

        try:
            while self.is_assistant_running:
                try:
                    text = q.get(timeout=1)
                    yield text
                except:
                    continue
        except Exception as e:
            logger.error(f"Ошибка в get_audio: {e}")
        finally:
            if hasattr(self, '_current_queue'):
                del self._current_queue

    # === ПРОВЕРКА МИКРОФОНА ===
    def check_microphone(self):
        """Проверка доступности микрофона через sounddevice"""
        debuglog.info("[MAIN] Проверка микрофона через sounddevice...")
        try:
            devices = sd.query_devices()
            active_mics = []

            for device in devices:
                if device['max_input_channels'] <= 0:
                    continue

                device_id = device['index']
                name = device['name']

                # Фильтруем системные
                if any(kw in name.lower() for kw in ['mapper', 'primary', 'wave', 'default']):
                    continue

                try:
                    with sd.InputStream(
                            device=device_id,
                            channels=1,
                            samplerate=44100,
                            blocksize=1024
                    ):
                        active_mics.append(device)
                except Exception:
                    continue

            if active_mics:
                debuglog.info(f"[MAIN] Найдено рабочих микрофонов: {len(active_mics)}")
                self.microphone_available = True
                return True
            else:
                logger.info("[MAIN] Нет доступных микрофонов.")
                self.microphone_available = False
                return False

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка проверки микрофона: {e}")
            self.microphone_available = False
            return False

    def _check_microphone_wrapper(self):
        try:
            self.check_microphone()
            if self.microphone_available:
                if not self.is_assistant_running:
                    self.show_toast(message="Микрофон обнаружен!")
                    self.run_assist()
                else:
                    self.show_toast(message="Микрофон подключен!")
            else:
                self.show_toast(message="Микрофон не найден!")
        except Exception as e:
            logger.error(f"Ошибка в _check_microphone_wrapper: {e}")

    def cleanup_audio_resources(self):
        """Безопасное освобождение аудиоресурсов"""
        try:
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    if self.audio_stream.active:
                        self.audio_stream.stop()
                    self.audio_stream.close()
                    debuglog.info("[MAIN] Аудиопоток закрыт.")
                except Exception as e:
                    debuglog.error(f"[MAIN] Ошибка при закрытии аудиопотока: {e}")
                finally:
                    self.audio_stream = None
        except Exception as e:
            debuglog.error(f"[MAIN] Критическая ошибка аудиопотока: {e}", exc_info=True)
        
        try:
            if hasattr(self, 'rec_ru') and self.rec_ru is not None:
                self.rec_ru = None
            if hasattr(self, 'model_ru') and self.model_ru is not None:
                self.model_ru = None
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при очистке моделей: {e}")

        import gc
        gc.collect()

    def check_silence_timeout(self):
        """Проверяет, сколько времени прошло с последнего звука"""
        if not self.is_assistant_running or not self.microphone_available:
            return

        if self.last_audio_time is None:
            return  # Ещё не было данных

        silent_duration = time.time() - self.last_audio_time

        if silent_duration > 10.0:  # 10 секунд тишины
            debuglog.warning(f"[MAIN] Нет звука более 10 сек ({silent_duration:.1f}s) — перезапуск аудиопотока")
            self.restart_audio_stream()

    def restart_audio_stream(self):
        """Перезапускает только InputStream, не трогая модели и ассистента"""
        debuglog.info("[MAIN] Перезапуск аудиопотока...")

        try:
            # Останавливаем старый поток
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                if self.audio_stream.active:
                    self.audio_stream.abort()
                self.audio_stream = None
                debuglog.info("[MAIN] Старый аудиопоток остановлен")

            # Создаём новый — без указания устройства → по умолчанию
            self.audio_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                blocksize=512,
                callback=self.audio_callback
            )
            self.audio_stream.start()

            # Обновляем время активности
            self.last_audio_time = time.time()

            debuglog.info("[MAIN] Аудиопоток успешно перезапущен (по умолчанию)")

        except Exception as e:
            debuglog.error(f"[MAIN] Не удалось перезапустить поток: {e}")
            # Можно попробовать повторно через 10 сек
            QTimer.singleShot(10000, self.restart_audio_stream)

    def handle_app_command(self, text, action):
        """Обработка команд для приложений, ярлыков и ссылок"""
        debuglog.info(f"[MAIN] Вызван обработчик команд для ярлыков и ссылок: {text}, {action}")
        all_commands = {**self.default_commands, **self.commands}
        for keyword, command_data in all_commands.items():
            if keyword in text:

                value = command_data.get('name', '') if isinstance(command_data, dict) else command_data

                self.commands_manager.handler_links(value, action)
                return True
        return False

    def handle_folder_command(self, text, action):
        """Обработка команд для папок"""
        debuglog.error(f"[MAIN] Вызван обработчик команд для папок: {text}, {action}")
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
            debuglog.error(f"[MAIN] Ошибка при запуске сценария: {e}")
            return False
        
    def handle_system_command(self, command, action):
        debuglog.info(f"[MAIN] Вызван обработчик команд для запуска системных: {command}, {action}")
        data_commands = self.default_commands

        for keyword, command_data in data_commands.items():
            if keyword in command:
                value = command_data.get('name', '') if isinstance(command_data, dict) else command_data

                if self.commands_manager.handler_system_commands(value, action):
                    return True
        return False

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

    def toggle_mute_discord(self):
        toggle = ToggleMuteDiscord()
        toggle.main()

    def start_default_command(self, command, action, type_command):
        debuglog.info(f"[MAIN][start_default_command] Получены аргументы: {command}, {action}, {type_command}")
        self.global_handler_command(command, action, type_command)
        debuglog.info(f"[MAIN][start_default_command] Команда {command} выполнена с действием {action}")

    def _open_widget_signal(self):
        try:
            gui_signals.open_widget_signal.emit()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при запуске сигнала виджета: {e}")

    def _close_widget_signal(self):
        try:
            gui_signals.close_widget_signal.emit()
        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при запуске сигнала виджета (на закрытие): {e}")

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
                self.get_reaction(name="approve_folder")

        except Exception as e:
            debuglog.error(f"[MAIN] Ошибка при открытии виджета: {str(e)}")
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
        debuglog.info("[MAIN] Виджет полностью уничтожен")

    def close_widget(self):
        try:
            if hasattr(self, "widget_window"):
                self.widget_window.close()
                self.get_reaction(name="approve_folder")
        except Exception as e:
            self.get_reaction(detail=True, name="error_file")
            self.show_toast(f"Ошибка при закрытии виджета (close_widget): {e}")
            debuglog.error(f"[MAIN] Ошибка при закрытии виджета (close_widget): {e}")

    def restore_and_hide(self):
        """Показываем окно и сразу скрываем — чтобы оно стало 'живым'"""
        self.move(-2000, -2000)
        self.showNormal()  # Восстанавливаем из минимизации/скрытия
        self.raise_()  # Поднимаем поверх всех
        self.activateWindow()  # Делаем активным
        QTimer.singleShot(50, self.hide)

    def open_folder_shortcuts(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = folder_links
        debuglog.info(f"[MAIN] Открытие папки ярлыков , {folder_path}")
        os.startfile(folder_path)

    def open_folder_screenshots(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = folder_screenshots
        debuglog.info(f"[MAIN] Открытие папки скриншотов, {folder_path}")
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
            debuglog.error(f"Ошибка при открытии mutable_panel: {e}")
            self.show_message(f"Ошибка при открытии mutable_panel: {str(e)}", "Ошибка", "error")

    def changelog_window(self, event):
        """Открываем окно с логами изменений"""
        dialog = ChangelogWindow(self)
        dialog.show()

    def update_app(self, type_version=None):
        """Обработка нажатия кнопки 'Установить обновление'"""
        debuglog.info(f"Вызвано создание update_app c флагами type_version {type_version}")
        dialog = UpdateApp(self, type_version)
        dialog.main()

    def update_voice(self, new_voice):
        """Обновление голоса и путей к аудиофайлам"""
        self.speaker = new_voice
        self.audio_paths = get_audio_paths(self.speaker)  # Обновляем пути к аудиофайлам
        logger.info(f"Голос изменен на: {new_voice}")
        debuglog.info(f"Голос изменен на: {new_voice}")

    def check_start_widget(self):
        if self.is_widget:
            self.open_widget(is_auto_start=True)

    def is_start_win_win(self):
        """Переключает состояние и меняет цвет иконки"""
        self.is_start_win = not self.is_start_win

        if self.is_start_win:
            self.add_to_autostart()
        else:
            self.remove_from_autostart()

    def add_to_autostart(self):
        """Добавление программы в автозапуск через планировщик задач"""
        task_name = "Voxodium"
        target_path = get_full_filepath()

        debuglog.debug(f"Путь для планировщика: {target_path}")

        # Проверка наличия файла
        if not os.path.isfile(target_path):
            error_msg = f"Ошибка: Файл '{target_path}' не найден."
            logger.error(error_msg)
            debuglog.error(error_msg)
            return

        # Команда для создания задачи в планировщике
        command = [
            'schtasks',
            '/create',
            '/tn', task_name,
            '/tr', f'"{target_path}"',
            '/sc', 'onlogon',
            '/rl', 'highest',
            '/f'
        ]

        try:
            result = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )

            success_msg = f"Программа добавлена в автозапуск"
            logger.info(success_msg)
            debuglog.info(success_msg)
            self.show_toast("Автозапуск включен")

        except subprocess.CalledProcessError as e:
            error_msg = f"Ошибка при добавлении в автозапуск: {e.stderr}"
            logger.error(error_msg)
            debuglog.error(error_msg)

    def remove_from_autostart(self):
        """Удаление программы из автозапуска через планировщик задач"""
        task_name = "Voxodium"

        command = [
            'schtasks',
            '/delete',
            '/tn', task_name,
            '/f'
        ]

        try:
            result = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )
            success_msg = f"Задача '{task_name}' удалена из автозапуска"
            debuglog.info(success_msg)
            self.show_toast(message=f"Автозапуск выключен")
        except subprocess.CalledProcessError as e:
            if "не существует" not in e.stderr:
                error_msg = f"Ошибка при удалении задачи '{task_name}': {e.stderr}"
                self.show_toast(message=f"{error_msg}")
                debuglog.error(error_msg)
            else:
                debuglog.info(f"Задача '{task_name}' не найдена в планировщике")

    def check_autostart(self):
        """Проверка, добавлена ли программа в автозапуск"""
        task_name = "Voxodium"

        command = ['schtasks', '/query', '/tn', task_name]

        try:
            result = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )
            debuglog.info(f"Найдена задача автозапуска: '{task_name}'")
            self.is_start_win = True
        except subprocess.CalledProcessError as e:
            if "не существует" not in e.stderr:
                error_msg = f"Автозапуск '{task_name}': {e.stderr}"
                logger.error(error_msg)
                debuglog.error(error_msg)
            self.is_start_win = False
            debuglog.info(f"Задачи '{task_name}' не существует")

    def capture_area(self):
        try:
            self.screenshot_tool.capture_area()
        except Exception as e:
            logger.error(f'Ошибка {e}')
            debuglog.error(f'[MAIN] Ошибка capture_area {e}')

    def capture_fullscreen(self):
        try:
            self.screenshot_tool.capture_fullscreen()
            thread_play_sound(type_sound="ok")
        except Exception as e:
            thread_play_sound(type_sound="error")
            logger.error(f'Ошибка {e}')
            debuglog.error(f'Ошибка {e}')

    def open_settings_from_tool(self):
        try:
            if self.isVisible():
                self.open_main_settings()
            else:
                self.show()
                self.open_main_settings()
        except Exception as e:
            debuglog.error(f"[MAIN][open_window_from_tool] Ошибка при переключении окна настроек: {e}")

    def open_window_from_tool(self):
        try:
            if self.isVisible():
                self.custom_hide()
            else:
                self.proper_show()
        except Exception as e:
            debuglog.error(f"[PANEL][open_window_from_tool] Ошибка при открытии основного окна через виджет {e}")


def should_launch_updater():
    """Определяет нужно ли запускать updater"""
    # Не запускаем updater если:
    # 1. Это запуск после обновления (--updated)
    # 2. Updater уже запущен
    # 3. Это специальный режим (например, --no-update)
    if build_ini == "dev":
        return False

    if len(sys.argv) > 1 and sys.argv[1] == "--updated":
        return False

    # Проверяем, не запущен ли уже updater
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == 'Update.exe':
            return False

    return True


if __name__ == '__main__':
    try:
        # Запускаем updater если нужно
        if should_launch_updater():
            updater_path = get_path("Update.exe")
            if os.path.exists(updater_path):
                subprocess.Popen([updater_path])
                sys.exit(0)  # Закрываем основную программу

        # Продолжаем обычный запуск
        if len(sys.argv) > 1 and sys.argv[1] == "--updated":
            logger.info("Запуск после обновления")
        else:
            if activate_existing_window():
                sys.exit(0)


        app = QApplication([])
        app.setWindowIcon(QIcon(get_path('icon.ico')))
        setup_global_font(app, "Open Sans", 10, "Medium")
        window = Assistant()
        app.exec()

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Произошла ошибка при запуске программы: {e}")
        debuglog.error(f"Произошла ошибка при запуске программы: {e}")
