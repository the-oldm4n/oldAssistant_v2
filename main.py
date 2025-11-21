"""
Этот модуль представляет собой основной файл для работы ассистента.

Здесь реализованы функции и классы, необходимые для
запуска и управления ассистентом, включая обработку
пользовательского ввода и управление интерфейсом.
"""
import csv
import ctypes
import re
import shutil
import jellyfish
import numpy as np
import pyaudio
import requests
from bin.choose_color_window import ColorSettingsWindow
from bin.custom_svg_widget import CustomSvgWidget
import logging
from pathlib import Path
import sys
import time
import traceback
import zipfile
import markdown2
from packaging import version
import psutil
import threading
import sounddevice as sd
import subprocess
from vosk import Model, KaldiRecognizer
from PySide6.QtGui import (QIcon, QCursor, QFont, QColor, QDesktopServices, QAction, QPixmap, QFontDatabase,
QPen, QPainter, QBrush, QPainterPath)
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, \
                               QPushButton, QSystemTrayIcon, QMenu, QMessageBox, \
                               QTextEdit, QDialog, QLabel, QTextBrowser, QMainWindow, QSizePolicy,
                               QGraphicsColorizeEffect, QTabWidget, QSpacerItem, QTabBar)
from PySide6.QtCore import Qt, QFileSystemWatcher, QTimer, QEvent, Signal, QPropertyAnimation, QPoint, \
    QEasingCurve, Slot, QUrl, QThread
from bin.apply_color_methods import ApplyColor
from bin.check_update import GetManifestThread, get_update_strategy, load_changelog, VersionCheckThread
from bin.download_thread import DeltaDownloadThread, DownloadThread
from bin.frosted_widget import GarlandDecorator, SnowOverlay
from bin.progress_bar_widget import CustomProgressBar, SVGProgressBar
from bin.register_module import AuthManager
from bin.screenshot_tool import SystemScreenshot
from bin.signals import gui_signals, color_signal, progress_signal, commands_signal
from bin.toast_notification import ToastNotification, SimpleNotice, SupplyNotice
from bin.toggle_mute_discord import ToggleMuteDiscord
from bin.widget_window import SmartWidget
from bin.commands_widgets import CreateCommandsWidget, CommandsWidget, ProcessLinksWidget
from bin.other_options_widgets import CensorCounterWidget, CheckUpdateWidget, DebugLoggerWidget, \
    RelaxWidget
from bin.utils import get_config_value, set_config_value, update_version, CommandsManager
from bin.function_list_main import *
from path_builder import get_path
from bin.audio_control import controller
from bin.settings_widgets import SettingsWidget, InterfaceWidget, OtherSettingsWidget, SettingsWidgetPanel, SpeechHookManagerWidget
from bin.speak_functions import thread_play_sound, thread_react_detail, thread_react, react
from logging_config import logger, debug_logger
from bin.lists import get_audio_paths, commands_list, default_keywords_data

build_ini = get_config_value("app", "build")
version_file = "2.1.3"
update_version(version_file)
domain = "https://owl-app.ru"
# domain = "https://127.0.0.1:5000"

def activate_existing_window():
    """Пытается отправить команду существующему приложению"""
    try:
        socket = QLocalSocket()
        socket.connectToServer("assistant_app")

        if socket.waitForConnected(2000):
            from PySide6.QtCore import QThread
            QThread.msleep(50)

            socket.write(b'show_window')

            if socket.waitForBytesWritten(1000):
                debug_logger.info("Команда отправлена существующему приложению")
            else:
                debug_logger.error("Данные не были отправлены")
                
            socket.disconnectFromServer()
            return True
        else:
            debug_logger.error("Не удалось подключиться к IPC серверу")
            return False
    except Exception as e:
        debug_logger.error(f"IPC client error: {e}")
        return False


class Assistant(QMainWindow):
    """
Основной класс содержащий GUI и скрипт обработки команд
    """
    close_child_windows = Signal()
    save_settings_signal = Signal()
    update_checked = Signal(bool, str)
    supply_notice_signal = Signal(str, bool)

    def check_memory_usage(self, limit_mb):
        """
        Проверка потребления оперативной памяти
        :param limit_mb:
        :return:
        """
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # В МБ
        if memory_usage > limit_mb:
            debug_logger.error(f"Превышен лимит памяти: {memory_usage} МБ > {limit_mb} МБ")
            return False
        return True

    def setup_memory_monitor(self):
        """Настройка мониторинга памяти через QTimer"""
        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.check_memory_with_cleanup)
        self.memory_timer.start(10000)  # 10 секунд

    def check_memory_with_cleanup(self):
        """Проверка памяти с автоматической очисткой"""
        if not self.check_memory_usage(limit_mb=800):
            debug_logger.warning("Превышен лимит памяти")
            self.show_notification_message("Превышен лимит оперативной памяти (800Мб), требуется перезагрузка")

    def __init__(self):
        super().__init__()
        self.start_ipc_server()
        self.version = self.get_version()
        self.ps = "Powered by theoldman"
        self.label_version = QLabel(f"Версия: {self.version} {self.ps}", self)
        self.latest_version_url = None
        self.latest_version = None
        self.current_ver = None
        self.relax_button = None
        self.drag_pos = None
        self.beta_version = False
        self.is_batch_update = False
        self.tray_icon = None
        self.toggle_start = None
        self.start_button = None
        self._update_dialog = None
        self.is_assistant_running = False
        self.microphone_available = True
        self.first_run = True
        self.assistant_thread = None
        self.censored_thread = None
        self._current_panel = None
        self.widget_window = None
        self.snow_on_background = None
        self.garland_decorator = None
        self.is_manual_check = False
        self.stop_checking = False
        self.is_force_close = False
        self.count = 0
        gui_signals.open_widget_signal.connect(self.open_widget)
        gui_signals.close_widget_signal.connect(self.close_widget)
        color_signal.color_changed.connect(self.update_colors)
        self.supply_notice_signal.connect(self._handle_supply_notice)
        commands_signal.commands_updated.connect(self.save_commands)
        self.update_checked.connect(self.handle_update_status)
        self.close_child_windows.connect(self.hide_widget)
        self.last_position = 0
        self.MEMORY_LIMIT_MB = 1024
        self.log_file_path = get_path('assistant.log')
        self.init_logger()
        self.svg_file_path = get_path("owl.svg")
        self.install_icons()
        self.changelog_file_path = get_path('update', 'changelog.md')
        self.process_names = get_path('user_settings', 'process_names.json')
        self.ohm_path = get_path("bin", "OHM", "OpenHardwareMonitor.exe")
        self.style_manager = ApplyColor(self)
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.settings_file_path = get_path('user_settings', 'settings.json')
        self.screenshot_tool = SystemScreenshot()
        # self.game_mode = None
        # self.game_mode_bool = False
        self.update_settings(self.settings_file_path)
        self.assistant_name = None
        self.assist_name2 = None
        self.assist_name3 = None
        self.speaker = None
        self.volume_assist = None
        self.steam_path = None
        self.is_censored = None
        self.run_updater = None
        self.is_corrected_command = None
        self.is_min_tray = None
        self.is_widget = None
        self.is_keep_watch = None
        self.input_device_id = None
        self.input_device_name = None
        self.is_snow = None
        self.is_garland = None
        self.install_settings()
        self.commands_manager = CommandsManager()
        self.audio_stream = None
        self.last_audio_time = None  # Время последнего НЕтихого пакета
        self.silence_timer = QTimer()  # Таймер для проверки тишины
        self.silence_timer.timeout.connect(self.check_silence_timeout)
        self.silence_timer.start(5000)
        self.setup_memory_monitor()
        self.save_settings_signal.connect(self.restart_bot)
        self.type_version = "stable"
        self.commands = self.load_commands()
        self.audio_paths = get_audio_paths(self.speaker)
        self.default_commands = commands_list
        self.auth = AuthManager(domain)
        self.user_data = self.auth.user_data
        self.is_admin = True if self.auth.load_auth_data_id() == 1 else False
        self.init_ui()
        self.splash = InitScreen()
        self.splash.init_complete.connect(self.handle_init_result)
        self.splash.show()
        self.splash.check_auth(self, self.auth)

    def check_up(self):
        self.check_or_create_folder()
        self.apply_styles()
        # Обновление селекторов стилей в файле
        self.update_style_list()
        # Проверка автозапуска при старте программы
        self.check_autostart()
        self.check_start_win()
        self.check_start_widget()
        # Прятать ли программу в трей
        if self.is_min_tray:
            # Показ окна при первом запуске(для отладки)
            if self.first_run:
                self.preload_window()
        else:
            self.showNormal()
        if self.user_data:
            self.update_user_profile()
        if self.check_keywords_file():
            debug_logger.info("Файл keywords.json найден")
        else:
            debug_logger.info("Файл keywords.json не найден, создаю...")
        if self.apply_keywords_for_values():
            self.run_assist()
        self.toggle_update_button()
        QTimer.singleShot(5000, lambda: self.check_update_app())
        self.update_checker = QTimer()
        self.update_checker.timeout.connect(self.check_update_app)
        self.update_checker.start(3600000)  # Чек обновлений раз в 60 минут (3600000)

    def handle_init_result(self, success):
        """Обработчик результата инициализации"""
        if success:
            self.check_up()

    def get_version(self):
        vers_on_ini = get_config_value("app", "version")

        if not vers_on_ini or vers_on_ini != version_file:
            set_config_value("app", "version", f"{version_file}")
            return version_file
        return version_file

    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            # Получаем новую позицию основного окна
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

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
        self.is_widget = self.settings.get("is_widget", True)
        self.is_keep_watch = self.settings.get("is_keep_watch", False)
        self.input_device_id = self.settings.get("input_device_id", None)
        self.input_device_name = self.settings.get("input_device_name", None)
        self.is_snow = self.settings.get("is_snow", False)
        self.is_garland = self.settings.get("is_garland", False)

    def install_icons(self):
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

    def init_ui(self):
        """Инициализация пользовательского интерфейса."""
        try:
            # Убираем стандартную рамку окна
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setWindowIcon(QIcon(get_path('icon_assist.ico')))
            self.setWindowTitle("Ассистент")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(820, 700)

            # Центрирование окна
            screen_geometry = self.screen().availableGeometry()
            self.move(
                (screen_geometry.width() - self.width()) // 2,
                (screen_geometry.height() - self.height()) // 2
            )
            self.setMouseTracking(True)
            self.drag_pos = None

            # Главный контейнер
            self.central_widget = QWidget()
            self.central_widget.setObjectName("MainWindowWidget") 
            self.setCentralWidget(self.central_widget)
            
            self.update_snow_state()

            # Главный layout
            root_layout = QVBoxLayout(self.central_widget)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # --- Title Bar ---
            self.title_bar_widget = QWidget()
            self.title_bar_widget.setObjectName("TitleBar")
            self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
            self.title_bar_layout.setContentsMargins(10, 8, 10, 8)

            self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
            self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
            self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release

            self.icon_svg = CustomSvgWidget(self.svg_file_path)
            self.icon_svg.setFixedSize(25, 25)
            self.icon_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.icon_svg)

            # self.title_label = QLabel("OWLAPP")
            self.title_label = self.setup_custom_font_label(text="OWLAPP")
            self.title_label.setStyleSheet("background: transparent; font-size: 24px;")
            self.title_bar_layout.addWidget(self.title_label)
            self.title_bar_layout.addStretch()

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

            self.start_win_btn = QPushButton()
            self.start_win_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.start_win_btn.setFixedSize(30, 30)
            self.start_win_btn.clicked.connect(self.toggle_start_win)
            self.start_svg = CustomSvgWidget(self.icon_start_win, self.start_win_btn)
            self.start_svg.setFixedSize(15, 15)
            self.start_svg.move(7, 7)
            self.start_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.start_win_btn)

            self.close_button = QPushButton()
            self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.close_button.clicked.connect(self.custom_hide)
            self.close_button.setFixedSize(30, 30)
            self.close_button.setObjectName("CloseButton")
            self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_button)
            self.close_svg.setFixedSize(24, 24)
            self.close_svg.move(3, 3)
            self.close_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.close_button)

            root_layout.addWidget(self.title_bar_widget)

            # --- Основное содержимое ---
            self.content_widget = QWidget()
            self.content_widget.setObjectName("ContentWidget")
            main_layout = QHBoxLayout(self.content_widget)
            main_layout.setContentsMargins(5, 5, 5, 5)
            
            self.update_garland_state()

            # === ЛЕВАЯ ЧАСТЬ: Контейнер с динамической шириной ===
            self.left_container = QWidget()
            self.left_container.setMaximumWidth(230)
            self.left_container.setMinimumWidth(0)
            self.left_container_layout = QVBoxLayout(self.left_container)
            self.left_container_layout.setContentsMargins(5, 5, 5, 5)
            self.left_container_layout.setSpacing(5)
            self.left_container.setObjectName("WMLeftContainer")

            self.spacer = QSpacerItem(230, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.left_container_layout.addSpacerItem(self.spacer)

            # === 1. Основные кнопки ===
            self.left_buttons_panel = QWidget()
            self.left_buttons_panel.setObjectName("WMLeftButtonsPanel")
            self.buttons_layout = QVBoxLayout(self.left_buttons_panel)
            self.buttons_layout.setContentsMargins(0, 0, 0, 0)
            self.buttons_layout.setSpacing(5)
            
            # Словарь для хранения кнопок
            self.buttons = {}

            buttons_data = [
                {
                    "key": "settings",
                    "text": "Настройки",
                    "icon_path": self.icon_settings_path,
                    "slot": self.open_main_settings,
                    "svg_attr": "settings_svg"
                },
                {
                    "key": "shortcuts", 
                    "text": "Ярлыки", 
                    "icon_path": self.icon_shortcut_path,
                    "slot": self.open_folder_shortcuts,
                    "svg_attr": "shortcut_svg"
                },
                {
                    "key": "commands",
                    "text": "Команды",
                    "icon_path": self.icon_commands_path, 
                    "slot": self.open_commands_settings,
                    "svg_attr": "commands_svg"
                },
                {
                    "key": "other",
                    "text": "Прочее",
                    "icon_path": self.icon_other_path,
                    "slot": self.other_options, 
                    "svg_attr": "other_svg"
                },
                {
                    "key": "guide",
                    "text": "Обучение",
                    "icon_path": self.icon_guide_path,
                    "slot": self.guide_options,
                    "svg_attr": "guide_svg"
                },
                {
                    "key": "start", 
                    "text": "Старт ассистента", 
                    "icon_path": self.icon_power_path,
                    "slot": self.start_assist_toggle,
                    "svg_attr": "power_svg"
                },
                {
                    "key": "widget",
                    "text": "Открыть виджет",
                    "icon_path": self.icon_widget_path,
                    "slot": self.open_widget,
                    "svg_attr": "widget_svg"
                }
            ]

            # Создаем кнопки через цикл
            for button_data in buttons_data:
                button = QPushButton(button_data["text"])
                button.clicked.connect(button_data["slot"])
                button.setStyleSheet("height: 40px; text-align: left; padding-left:50px")
                
                # Создаем SVG иконку
                svg_widget = CustomSvgWidget(button_data["icon_path"], button)
                svg_widget.setFixedSize(30, 30)
                svg_widget.move(10, 5)
                svg_widget.setStyleSheet("background:transparent;")
                
                # Сохраняем кнопку в словарь
                self.buttons[button_data["key"]] = button
                # Сохраняем ссылку на SVG как атрибут экземпляра
                setattr(self, button_data["svg_attr"], svg_widget)
                
                self.buttons_layout.addWidget(button)

            self.buttons_layout.addStretch()
            
            # self.btn_test = QPushButton()
            # self.btn_test.clicked.connect(self.update_style_list)
            # self.buttons_layout.addWidget(self.btn_test, alignment=Qt.AlignmentFlag.AlignCenter)
            
            if self.is_admin:
                self.btn_update_all_presets = QPushButton("Обновить пресеты")
                self.btn_update_all_presets.clicked.connect(self.update_style_all)
                self.buttons_layout.addWidget(self.btn_update_all_presets)
            
            # self.svg_image = CustomSvgWidget(self.svg_file_path)
            # self.svg_image.setFixedSize(130, 130)
            # self.svg_image.setStyleSheet("background: transparent; border: none;")
            # self.color_svg = QGraphicsColorizeEffect()
            # self.svg_image.setGraphicsEffect(self.color_svg)
            # self.buttons_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.user_profile_widget = QWidget()
            self.user_profile_widget.setObjectName("UserProfileWidget")
            self.user_profile_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            self.user_profile_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            self.user_profile_widget.mousePressEvent = self.on_profile_click

            self.user_profile_layout = QHBoxLayout(self.user_profile_widget)
            self.user_profile_layout.setContentsMargins(10, 5, 10, 5)
            self.user_profile_layout.setSpacing(8)
            self.user_profile_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Аватарка
            self.avatar_svg = CustomSvgWidget(self.default_avatar_path)
            self.avatar_svg.setFixedSize(40, 40)
            self.avatar_svg.setStyleSheet("background: transparent; border: none;")
            self.avatar_color_svg = QGraphicsColorizeEffect()
            self.avatar_svg.setGraphicsEffect(self.avatar_color_svg)
            self.style_manager.apply_color_svg(self.avatar_svg, strength=0.90)

            # Юзернейм
            self.username_label = QLabel("Username")
            self.username_label.setStyleSheet("background: transparent;")

            self.user_profile_layout.addWidget(self.avatar_svg)
            self.user_profile_layout.addWidget(self.username_label)

            # Добавляем виджет в правый layout
            self.buttons_layout.addWidget(self.user_profile_widget, stretch=1)
            
            self.progress_load = CustomProgressBar(self, style="looper")
            self.progress_load.hide()
            self.buttons_layout.addWidget(self.progress_load)

            self.update_label = QLabel("Установлена последняя версия") # Установлена последняя версия
            self.update_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.update_label.mousePressEvent = self.update_answer
            self.buttons_layout.addWidget(self.update_label)

            self.label_version.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.label_version.mousePressEvent = self.changelog_window
            self.buttons_layout.addWidget(self.label_version)

            # Добавляем панель кнопок в контейнер
            self.left_container_layout.addWidget(self.left_buttons_panel)

            # === 2. Панель настроек (изначально скрыта) ===
            self.mutable_panel = QWidget()
            self.mutable_panel.setObjectName("WM_MutablePanel")
            self.mutable_layout = QVBoxLayout(self.mutable_panel)
            self.mutable_layout.setContentsMargins(5, 5, 5, 5)
            self.mutable_panel.hide()

            self.left_container_layout.addWidget(self.mutable_panel)

            # === ПРАВАЯ ЧАСТЬ: Логи + иконки ===
            self.right_layout = QVBoxLayout()
            self.right_layout.setContentsMargins(5, 5, 5, 5)

            # Компактная панель (иконки)
            self._setup_compact_toolbar()
            self.right_layout.addLayout(self.compact_layout)
            self.hide_layout(self.compact_layout)
            
            # self.user_profile_widget = QWidget()
            # self.user_profile_widget.setObjectName("UserProfileWidget")
            # self.user_profile_widget.setFixedSize(180, 60)
            # self.user_profile_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            # self.user_profile_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            # self.user_profile_widget.mousePressEvent = self.on_profile_click

            # self.user_profile_layout = QHBoxLayout(self.user_profile_widget)
            # self.user_profile_layout.setContentsMargins(10, 5, 10, 5)
            # self.user_profile_layout.setSpacing(8)
            # self.user_profile_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

            # # Аватарка
            # self.avatar_svg = CustomSvgWidget(self.default_avatar_path)
            # self.avatar_svg.setFixedSize(40, 40)
            # self.avatar_svg.setStyleSheet("background: transparent; border: none;")
            # self.avatar_color_svg = QGraphicsColorizeEffect()
            # self.avatar_svg.setGraphicsEffect(self.avatar_color_svg)
            # self.style_manager.apply_color_svg(self.avatar_svg, strength=0.90)

            # # Юзернейм
            # self.username_label = QLabel("Username")
            # self.username_label.setStyleSheet("background: transparent;")

            # self.user_profile_layout.addWidget(self.username_label)
            # self.user_profile_layout.addWidget(self.avatar_svg)

            # # Добавляем виджет в правый layout
            # self.right_layout.addWidget(self.user_profile_widget, alignment=Qt.AlignmentFlag.AlignRight)

            # Логи
            self.log_area = QTextEdit()
            self.log_area.setReadOnly(True)
            self.log_area.setFont(QFont("Consolas"))
            self.log_area.setStyleSheet("font-size: 16px")
            self.clear_logs_button = QPushButton("Очистить логи")
            self.clear_logs_button.clicked.connect(self.clear_logs)
            self.right_layout.addWidget(self.log_area)
            self.right_layout.addWidget(self.clear_logs_button)

            # === Добавляем в main_layout ===
            main_layout.addWidget(self.left_container)
            main_layout.addLayout(self.right_layout)

            root_layout.addWidget(self.content_widget)

            # === Анимация ширины ===
            self.animation = QPropertyAnimation(self.left_container, b"geometry")
            self.animation.setDuration(300)
            self.animation.setEasingCurve(QEasingCurve.Type.OutBack)

            # === Tray, логи, прочее ===
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(QIcon(self.icon_tray_path))
            self.tray_icon.setToolTip("Ассистент")

            start_widget = QAction("Запустить виджет", self)
            start_widget.triggered.connect(self.open_widget)

            settings = QAction("Настройки", self)
            settings.triggered.connect(self.open_settings_of_tray)

            show_action = QAction("Развернуть", self)
            show_action.triggered.connect(self.show)

            hide_action = QAction("Свернуть", self)
            hide_action.triggered.connect(self.custom_hide)

            quit_action = QAction("Закрыть", self)
            quit_action.triggered.connect(self.close_app)

            self.menu_tray = QMenu()
            self.menu_tray.addAction(start_widget)
            self.menu_tray.addAction(settings)
            self.menu_tray.addAction(show_action)
            self.menu_tray.addAction(hide_action)
            self.menu_tray.addAction(quit_action)
            self.tray_icon.setContextMenu(self.menu_tray)
            self.tray_icon.activated.connect(self.on_tray_icon_activated)
            self.tray_icon.show()

            self.init_file_watcher()
            self.load_existing_logs()

            self.timer = QTimer()
            self.timer.timeout.connect(self.check_log)
            self.timer.start(1000)

        except Exception as e:
            debug_logger.error(f"Ошибка при инициализации GUI: {e}")
            
    def setup_custom_font_label(self, text: str):
        # Загрузка шрифта
        font_path = get_path("bin", "fonts", "Flatiron", "Flatiron Regular.otf")
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
            
    def update_style_list(self):
        change_color = ColorSettingsWindow(self)
        # path = get_path("bin", "color_presets", "blue_neon.json")
        change_color.update_style_file()
        self.apply_styles()
        
    def update_style_all(self):
        change_color = ColorSettingsWindow(self)
        change_color.update_all_styles()
        self.apply_styles()
        
    def start_ipc_server(self):
        """Настраивает IPC сервер используя Qt (без потоков)"""
        self.ipc_server = QLocalServer()
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)
        
        # Удаляем старый сервер если есть (на случай краша)
        QLocalServer.removeServer("assistant_app")
        
        # Запускаем сервер
        if not self.ipc_server.listen("assistant_app"):
            debug_logger.error(f"IPC server error: {self.ipc_server.errorString()}")
        else:
            debug_logger.info("IPC server started")

    def handle_ipc_connection(self):
        """Обрабатывает входящие соединения"""
        socket = self.ipc_server.nextPendingConnection()
        debug_logger.info(f"New connection: {socket}")
        
        if socket:
            # Многократные попытки чтения
            for attempt in range(5):
                if socket.waitForReadyRead(100):  # Короткие интервалы
                    if socket.bytesAvailable() > 0:
                        data = socket.readAll().data()
                        debug_logger.info(f"IPC data received (attempt {attempt+1}): {data}")
                        if data == b'show_window':
                            debug_logger.info("Activating window...")
                            self.force_show_window()
                        break
                else:
                    debug_logger.warning(f"Attempt {attempt+1}: No data yet")
            
            socket.disconnectFromServer()
            socket.deleteLater()
            debug_logger.info("Connection closed")
            
    def read_ipc_data(self, socket):
        """Читает данные из IPC соединения"""
        try:
            if socket.bytesAvailable() > 0:
                data = socket.readAll().data()
                debug_logger.debug(f"IPC data received: {data}")
                if data == b'show_window':
                    self.force_show_window()
            
            # Всегда закрываем соединение после чтения
            socket.disconnectFromServer()
            socket.deleteLater()
            
        except Exception as e:
            debug_logger.error(f"Error reading IPC data: {e}")
        
    def force_show_window(self):
        """Принудительное открытие окна из любого состояния"""
        debug_logger.debug(f"force_show_window called. isVisible: {self.isVisible()}, isMinimized: {self.isMinimized()}, isHidden: {self.isHidden()}")
        
        # Всегда показываем окно
        self.show()
        self.showNormal()  # Сбрасываем minimized/maximized состояние
        
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
        
        # Принудительная перерисовка
        self.update()
        self.repaint()
        
        debug_logger.debug(f"After force_show: isVisible: {self.isVisible()}, isMinimized: {self.isMinimized()}")
        
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
                debug_logger.error("Не удалось создать гирлянду")
                
        except Exception as e:
            debug_logger.error(f"Ошибка при смене анимации гирлянды: {e}")    

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
            return  # Уже создан
        
        self.snow_on_background = SnowOverlay(
                parent=self.central_widget,
                snowflake_count=300,
                fall_speed=0.9,
                flake_size_min=1,
                flake_size_max=5
            )
        self.snow_on_background.resize(800, 700)
        self.snow_on_background.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.snow_on_background.raise_()
        self.snow_on_background.setSnowColor(self.style_manager.get_snow_color(), alpha=150, white_balance=50)
        
        # Изначально показываем или скрываем в зависимости от состояния
        if self.is_snow:
            self.snow_on_background.show()
        else:
            self.snow_on_background.hide()

    # def toggle_snow(self):
    #     """Переключает состояние снега"""
    #     self.is_snow = not self.is_snow
    #     self.update_snow_state()

    # Упрощенная версия без лишних проверок
    def set_snow_enabled(self, enabled):
        """Включает/выключает снег"""
        self.is_snow = enabled
        
        if self.snow_on_background is not None:
            if enabled:
                self.snow_on_background.show()
            else:
                self.snow_on_background.hide()

    def hide_layout(self, layout):
        """Скрывает все виджеты в layout"""
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().hide()

    def show_layout(self, layout):
        """Показывает все виджеты в layout"""
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().show()
                
    def open_user_profile(self):
        QDesktopServices.openUrl(QUrl("https://owl-app.ru/profile"))
    
    def refresh_user_data(self):
        pass
    
    def logout_user(self):
        """Выход с возвратом к InitScreen"""
        debug_logger.info("🚪 Выход из системы...")
        
        # Очищаем данные
        self.user_data = None
        self.auth.logout()
        
        # Скрываем главное окно
        self.hide()
        
        # Показываем InitScreen
        self.splash = InitScreen()
        self.splash.init_complete.connect(self.handle_init_result)
        self.splash.show()
        self.splash.check_auth(self, self.auth)

    def restart_application(self):
        """Перезапуск приложения"""
        import sys
        import os
        os.execl(sys.executable, sys.executable, *sys.argv)
         
    def on_profile_click(self, event):
        """Обработчик клика по профилю"""
        debug_logger.info("👤 Клик по профилю пользователя")
        menu = QMenu(self)

        menu.addAction("👤 Профиль", self.open_user_profile)
        menu.addAction("🔄 Обновить данные", self.refresh_user_data)
        menu.addAction("🚪 Выйти", self.logout_user)  # ⚠️ КНОПКА ВЫХОДА
        
        # Показываем меню под виджетом профиля
        menu.exec(self.user_profile_widget.mapToGlobal(
            QPoint(0, self.user_profile_widget.height())
        ))
               
    def set_user_data(self, user_data):
            """Установить данные пользователя (вызывается из InitScreen)"""
            self.user_data = user_data
            self.update_user_profile(user_data)
            debug_logger.info(f"👤 Данные пользователя установлены: {user_data['username']}")
    
    def clear_user_data(self):
        """Очистить данные пользователя"""
        self.user_data = None
        self.username_label.setText("Гость")
        self.set_default_avatar_svg()
                
    def update_user_profile(self, user_data=None):
        """Обновить профиль пользователя (можно вызывать без параметров)"""
        debug_logger.info(f"Обновление профиля...")
        # Используем переданные данные или локальные
        data = user_data or self.user_data

        if data and 'username' in data:
            if hasattr(self, "username_label"):
                self.username_label.setText(data['username'])
            else:
                self.username_label.setText("User")
            
        if data and data.get('avatar') is None:
            return self.set_default_avatar_svg()
        
        if data and 'avatar' in data:
            self.load_user_avatar(data['avatar'])
        else:
            self.set_default_avatar_svg()

    def set_default_avatar_svg(self):
        """Установить SVG аватарку по умолчанию"""
        if hasattr(self, 'avatar_svg'):
            # Если уже есть SVG, просто применяем стили
            self.style_manager.apply_color_svg(self.avatar_svg, strength=0.90)

    def load_user_avatar(self, avatar_path):
        """Загрузить пользовательскую аватарку"""
        try:
            avatar_url = f"{self.auth.base_url}{avatar_path}"
            response = requests.get(avatar_url, timeout=10, verify=False)
            
            if response.status_code == 200:
                # Создаем QLabel для растрового изображения
                if hasattr(self, 'avatar_svg'):
                    self.avatar_svg.hide()  # Скрываем SVG
                
                # Создаем QLabel для растровой аватарки если еще нет
                if not hasattr(self, 'avatar_pixmap_label'):
                    self.avatar_pixmap_label = QLabel()
                    self.avatar_pixmap_label.setFixedSize(50, 50)
                    self.avatar_pixmap_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    self.avatar_pixmap_label.setStyleSheet("background: transparent; border: none;")

                    avatar_index = self.user_profile_layout.indexOf(self.avatar_svg)
                    self.user_profile_layout.insertWidget(avatar_index, self.avatar_pixmap_label)
                else:
                    self.avatar_pixmap_label.show()
                
                # Загружаем и устанавливаем растровую аватарку
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                rounded_pixmap = self.create_rounded_pixmap(pixmap, 50)
                self.avatar_pixmap_label.setPixmap(rounded_pixmap)
                
            else:
                debug_logger.error(f"❌ Ошибка загрузки аватара: {response.status_code}")
                self.set_default_avatar_svg()
                
        except Exception as e:
            debug_logger.error(f"[EXCEPT] Ошибка загрузки аватара: {e}")
            self.set_default_avatar_svg()

    def create_rounded_pixmap(self, pixmap, size):
        if pixmap.isNull():
            return QPixmap()

        # Создаём прозрачный pixmap-контейнер
        rounded = QPixmap(size, size)
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )

        # Убедимся, что pixmap имеет альфа-канал
        if not pixmap.hasAlphaChannel():
            # QPixmap → QImage → convert → QPixmap
            image = pixmap.toImage()
            image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            pixmap = QPixmap.fromImage(image)

        # Масштабируем с сохранением пропорций
        scaled_pixmap = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Центрируем
        x = (size - scaled_pixmap.width()) // 2
        y = (size - scaled_pixmap.height()) // 2

        # Обрезаем по кругу
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()

        return rounded

    def _setup_compact_toolbar(self):
        """Инициализация компактной панели с иконками"""
        self.compact_layout = QHBoxLayout()
        self.compact_layout.setContentsMargins(0, 0, 0, 10)
        self.compact_layout.setSpacing(10)

        while self.compact_layout.count():
            item = self.compact_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.compact_layout.addStretch()

        self.left_spacer = QSpacerItem(1, 40, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.compact_layout.addSpacerItem(self.left_spacer)

        buttons_data = [
            (self.icon_close_path, "Закрыть", self.hide_widget),
            (self.icon_settings_path, "Настройки", self.open_main_settings),
            (self.icon_shortcut_path, "Ваши ярлыки", self.open_folder_shortcuts),
            (self.icon_commands_path, "Ваши команды", self.open_commands_settings),
            (self.icon_other_path, "Прочее", self.other_options),
            (self.icon_guide_path, "Обучение", self.guide_options),
            (self.icon_power_path, "Старт ассистента", self.start_assist_toggle),
            (self.icon_widget_path, "Открыть виджет", self.open_widget),
        ]

        self.btn_svg_list = []

        for svg_path, tooltip, callback in buttons_data:
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setToolTip(tooltip)
            btn.clicked.connect(callback)
            btn.setVisible(False)

            svg_widget = CustomSvgWidget(svg_path, btn)
            svg_widget.setFixedSize(30, 30)
            svg_widget.move(5, 5)
            svg_widget.setStyleSheet("background: transparent;")
            self.style_manager.apply_color_svg(svg_widget, strength=0.90)

            self.btn_svg_list.append({'button': btn, 'svg': svg_widget})

            self.compact_layout.addWidget(btn)

        self.right_spacer = QSpacerItem(1, 40, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.compact_layout.addSpacerItem(self.right_spacer)
        self.compact_layout.addStretch()

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
            # Применение к конкретным виджетам
            self.style_manager.apply_to_widget(self.label_version, 'label_version')
            self.style_manager.apply_to_widget(self.update_label, 'update_label')
            
            if hasattr(self, 'avatar_svg'):
                # Если уже есть SVG, просто применяем стили
                self.style_manager.apply_color_svg(self.avatar_svg, strength=0.90)
                
            # if hasattr(self, "update_svg"):
            #     self.style_manager.apply_color_svg(self.update_svg, strength=0.90, specified_color="#44D14F")

            self.style_manager.apply_progressbar(key="QPushButton", widget=self.progress_load, style="parts")
            # Применение к SVG
            if hasattr(self, 'svg_image'):
                self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            if hasattr(self, 'settings_svg'):
                self.style_manager.apply_color_svg(self.settings_svg, strength=0.90)
            if hasattr(self, 'shortcut_svg'):
                self.style_manager.apply_color_svg(self.shortcut_svg, strength=0.90)
            if hasattr(self, 'commands_svg'):
                self.style_manager.apply_color_svg(self.commands_svg, strength=0.90)
            if hasattr(self, 'guide_svg'):
                self.style_manager.apply_color_svg(self.guide_svg, strength=0.90)
            if hasattr(self, 'other_svg'):
                self.style_manager.apply_color_svg(self.other_svg, strength=0.90)
            if hasattr(self, 'power_svg'):
                self.style_manager.apply_color_svg(self.power_svg, strength=0.90)
            if hasattr(self, 'widget_svg'):
                self.style_manager.apply_color_svg(self.widget_svg, strength=0.90)
            if hasattr(self, 'icon_svg'):
                self.style_manager.apply_color_svg(self.icon_svg, strength=0.95)
            if hasattr(self, 'update_light_svg'):
                self.style_manager.apply_color_svg(self.update_light_svg, strength=0.95)
            if hasattr(self, 'close_svg'):
                self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#ff0000")
            

            # Применение общего стиля окна
            if hasattr(self, 'central_widget'):
                self.central_widget.setObjectName("MainWindowWidget")
            if hasattr(self, 'title_bar_widget'):
                self.title_bar_widget.setObjectName("TitleBar")
            if hasattr(self, 'container'):
                self.container.setObjectName("WindowContainer")
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
            self.apply_menu_styles(self.menu_tray)
            if hasattr(self, "snow_on_background"):
                self.snow_on_background.setSnowColor(self.style_manager.get_snow_color(), alpha=150, white_balance=60)
                
        except Exception as e:
            debug_logger.error(f"Ошибка в методе apply_styles: {e}")

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

    def update_colors(self):
        self.styles = self.style_manager.load_styles()
        for data in self.btn_svg_list:  # Итерируемся по списку
            self.style_manager.apply_color_svg(data['svg'], strength=0.90)
        for data in self.svg_settings_list:
            self.style_manager.apply_color_svg(data["svg"], strength=0.90)

    def show_notification_message(self, message):
        try:
            # Проверяем, действительно ли окно скрыто/свёрнуто
            is_window_hidden = self.isMinimized() or not self.isVisible()

            toast = ToastNotification(
                parent=None if is_window_hidden else self,
                message=message,
                timeout=4000
            )
            toast.show()
        except Exception as e:
            debug_logger.error(f"Ошибка при показе всплывающего уведомления: {e}")

    def show_message(self, text, title="Уведомление", message_type="info", buttons=QMessageBox.StandardButton.Ok):
        try:
            message = SimpleNotice(
                parent=self,
                message=text,
                title=title,
                message_type=message_type,
                buttons=buttons
            )
            return message.exec_()
        except Exception as e:
            debug_logger.error(f"Ошибка при показе уведомления(оконного): {e}")
            # В случае ошибки тоже нужно что-то вернуть, например, QDialog.Rejected или None
            return QDialog.DialogCode.Rejected  # или return None

    def show_supply_notice(self, message, is_confirm=False):
        """Вызывается из фонового потока - emits signal"""
        try:
            # Отправляем сигнал в главный поток Qt
            self.supply_notice_signal.emit(message, is_confirm)
        except Exception as e:
            debug_logger.error(f"Ошибка при отправке сигнала уведомления: {e}")

    def _handle_supply_notice(self, message, is_confirm=False):
        """Выполняется в главном потоке Qt (обработчик сигнала)"""
        try:
            if is_confirm:
                default_text = ""
            else:
                default_text = "Распознано: "
            toast = SupplyNotice(
                parent=None,
                message=f"{default_text}{message}",
                timeout=5000
            )
            toast.show()

        except Exception as e:
            debug_logger.error(f"Ошибка при показе всплывающего уведомления: {e}")

    def keyPressEvent(self, event):
        """Сворачивает основное окно в трей по нажатию на Esc"""
        if event.key() == Qt.Key.Key_Escape:
            if self.mutable_panel.isVisible():
                self.hide_widget()
                event.accept()
            else:
                self.custom_hide()
                event.accept()
        else:
            super().keyPressEvent(event)

    def open_update_app(self, event):
        """Запускает скрипт для установки обновления при клике на текст."""
        try:
            self.update_app(type_version=self.type_version, batch_update=self.is_batch_update)
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске программы обновления: {e}")

    #  тут исправлена логика обработки ручной проверки
    @Slot()
    def update_answer(self, event):
        """Реакция бота на отсутствие обновления"""
        try:
            self.is_manual_check = True  # Устанавливаем флаг ручной проверки
            self.check_update_app()
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске программы обновления: {e}")

    def handle_update_status(self, is_success, status_text):
        """Обрабатывает результат проверки обновлений"""
        if not self.is_manual_check:  # Пропускаем реакцию для автоматических проверок
            return

        # Реагируем только если это ручная проверка
        if status_text == "Установлена последняя версия":
            self.get_reaction(detail=True, name="update_button")
        elif status_text == "Доступно обновление":
            pass
        elif not is_success:
            self.get_reaction(detail=True, name="error_file")

        self.is_manual_check = False

    def toggle_update_button(self):
        """
        Метод для отображения или скрытия кнопки "Установить обновление"
        """
        if self.update_label.text() == "Доступно обновление": # Установлена последняя версия Доступно обновление 
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
                debug_logger.info(f"Папка update_pack отправлена в корзину: {temp_dir}")
            except Exception as e:
                debug_logger.error(f"Не удалось удалить {temp_dir}: {e}")

        # Удаление в корзину папки бэкапа
        if os.path.exists(backup_dir):
            try:
                send2trash(backup_dir)
                debug_logger.info(f"Папка бэкапа отправлена в корзину: {backup_dir}")
            except Exception as e:
                debug_logger.error(f"Не удалось удалить {backup_dir}: {e}")
                
        # Удаление в корзину batch_dir
        if os.path.exists(batch_dir):
            try:
                send2trash(batch_dir)
                debug_logger.info(f"Папка batch_dir отправлена в корзину: {batch_dir}")
            except Exception as e:
                debug_logger.error(f"Не удалось удалить {batch_dir}: {e}")

        # Удаление .zip файлов в корзину
        if os.path.exists(download_dir):
            for old_file in os.listdir(download_dir):
                old_path = os.path.join(download_dir, old_file)
                if os.path.isfile(old_path) and old_file.endswith('.zip'):
                    try:
                        send2trash(old_path)
                        debug_logger.info(f"Файл отправлен в корзину: {old_path}")
                    except Exception as e:
                        debug_logger.error(f"Не удалось удалить {old_path}: {e}")

    def animation_start_load(self):
        progress_signal.start_progress.emit()
        self.progress_load.show()
        self.progress_load.startAnimation()

    def animation_stop_load(self):
        progress_signal.stop_progress.emit()
        self.progress_load.hide()
        self.progress_load.stopAnimation()

    def swap_update_file(self, current_version):
        try:
            temp_folder_name = f"update/{current_version}_temp"
            temp_dir = get_path(temp_folder_name)
            debug_logger.info(f"Path update temp: {temp_dir}")
            if os.path.exists(temp_dir):
                subprocess.Popen([get_path("swap-updater.exe"), "--update-dir", str(temp_dir)], shell=True)
                debug_logger.info("swap-updater.exe успешно запущен")
            else:
                subprocess.Popen([get_path("swap-updater.exe")], shell=True)
                debug_logger.info(f"Папка обновления не найдена: {temp_dir}\n"
                                  "Запуск swap-updater.exe без параметров")
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске swap-updater.exe: {e}")

    def check_update_app(self):
        """Проверяет обновления"""
        if self.stop_checking:
            return
        try:
            self.animation_start_load()
            progress_signal.start_progress.emit()
            self.toggle_update_button()
            self.update_label.hide()

            self.thread = VersionCheckThread()
            self.thread.version_checked.connect(self.handle_version_check)
            self.thread.check_failed.connect(self.handle_check_failed)
            self.thread.start()

        except Exception as e:
            self.animation_stop_load()
            logger.error(f"Неожиданная ошибка")
            debug_logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
            self.update_label.show()
            self.update_label.setText("Ошибка обновления")
            QTimer.singleShot(2000, self.check_update_app)

    def handle_version_check(self, stable_version, exp_version):
        # Обработка полученных версий
        new_version = exp_version if self.beta_version else stable_version
        self.latest_version = version.parse(new_version)
        self.current_ver = version.parse(self.version)

        type_version = "exp" if self.beta_version else "stable"

        load_changelog()

        if self.latest_version > self.current_ver:
            # Запускаем проверку манифеста
            self.get_changes_manifest_thread = GetManifestThread(self.current_ver, self.auth)
            self.get_changes_manifest_thread.check_success.connect(self.on_manifest_ready)
            self.get_changes_manifest_thread.check_failed.connect(self.handle_failed_manifest)
            self.get_changes_manifest_thread.start()
        else:
            self.animation_stop_load()
            self.update_label.show()
            self.update_label.setText("Установлена последняя версия")
            self.toggle_update_button()
            self.update_checked.emit(True, "Установлена последняя версия")
            self.swap_update_file(self.current_ver)
            self.stop_checking = False
            QTimer.singleShot(4000, lambda: self.update_complete())
            
    def on_manifest_ready(self, manifest):
        """Обработка готового манифеста и запуск соответствующей загрузки"""
        strategy = get_update_strategy(self.current_ver, self.latest_version, manifest)
        
        if strategy == "full":
            print("Требуется полная установка (было критическое обновление)")
            self.start_full_download()
        else:
            print("Дельта-обновление доступно")
            # Собираем все файлы из всех версий между current и latest
            files_to_update = self.collect_all_changed_files(
                self.current_ver, self.latest_version, manifest
            )
            # Передаем manifest в start_delta_download
            self.start_delta_download(files_to_update, manifest)  # ← добавил manifest

    def start_full_download(self):
        """Запуск загрузки полной версии"""
        type_version = "exp" if self.beta_version else "stable"
        self.download_thread = DownloadThread(type_version)
        self.download_thread.download_complete.connect(self.handle_download_complete)
        self.download_thread.finished.connect(self.animation_stop_load)
        self.download_thread.start()
        self.toggle_update_button()

    def start_delta_download(self, files_to_update, manifest):  # ← добавил параметр manifest
        """Запуск загрузки дельта-обновления"""
        self.download_thread = DeltaDownloadThread(
            files_to_update, 
            manifest,  # ← передаем manifest в поток
            self.auth
        )
        self.download_thread.download_complete.connect(self.handle_download_complete)
        self.download_thread.finished.connect(self.animation_stop_load)
        self.download_thread.start()
        self.toggle_update_button()
        
    def collect_all_changed_files(self, current_ver, target_ver, manifest):
        """Собирает все измененные файлы между версиями"""
        # Преобразуем версии из манифеста в объекты Version для сравнения
        version_objects = []
        version_to_str_map = {}  # Сопоставление Version -> строковый ключ
        
        for ver_str in manifest.keys():
            try:
                ver_obj = version.parse(ver_str)
                version_objects.append(ver_obj)
                version_to_str_map[ver_obj] = ver_str
            except:
                continue
        
        # Сортируем объекты Version
        version_objects.sort()
        
        try:
            # Находим индексы в отсортированном списке объектов Version
            current_idx = version_objects.index(current_ver)
            target_idx = version_objects.index(target_ver)
            
            all_files = set()
            for i in range(current_idx + 1, target_idx + 1):
                version_obj = version_objects[i]
                version_str = version_to_str_map[version_obj]  # Получаем строковый ключ
                files = manifest[version_str].get('changed_files', [])  # Используем changed_files
                all_files.update(files)
            
            return list(all_files)
            
        except ValueError as e:
            debug_logger.error(f"❌ Версия не найдена в collect_all_changed_files: {e}")
            debug_logger.error(f"❌ Текущая: {current_ver}, Целевая: {target_ver}")
            debug_logger.error(f"❌ Доступные: {[str(v) for v in version_objects]}")
            return []
            
    def handle_failed_manifest(self):
        self.count += 1
        self.animation_stop_load()
        self.update_label.show()
        self.update_label.setText("Ошибка соединения")
        if self.count == 3:
            self.update_label.setText("Не удалось получить обновление")
        if self.count <= 2: # 3 попытки на запрос версии в случае неудачи
            QTimer.singleShot(2000, self.check_update_app)

    def handle_check_failed(self):
        self.count += 1
        self.animation_stop_load()
        self.update_label.show()
        self.update_label.setText("Ошибка соединения")
        if self.count == 3:
            self.update_label.setText("Сервер не доступен")  
        if self.count <= 2: # 3 попытки на запрос версии в случае неудачи
            QTimer.singleShot(2000, self.check_update_app)
    
    def handle_download_complete(self, file_path, success=True, skipped=False, error=None, batch=False):
        self.animation_stop_load()
        self.update_label.show()
        print(f"Values:", file_path, success, skipped, error, "batch:", batch)
        self.is_batch_update = batch
        if self.is_batch_update:
            # Обработка дельта-обновления
            if success:
                self.update_label.setText(f"Доступно обновление")
                self.show_notification_message(f"Обновление готово к установке")
                debug_logger.info(f"Файлы обновления по пути: {file_path}")
                self.stop_checking = True
                if skipped:
                    self.show_notification_message("Подготовка к процедуре обновления...\n Не выключайте приложение")
                    debug_logger.info(f"[SKIP] Файлы уже существуют")
                    # self.open_window_and_update()
                else:
                    debug_logger.info(f"[OK] Новый файл загружен")
            else:
                self.update_label.setText(f"Ошибка обновления: {error}")
        else:
            # Обработка полного обновления (старая логика)
            self.update_label.setText("Доступно обновление")
            if success:
                self.type_version = "exp" if "exp_" in os.path.basename(file_path).lower() else "stable"
                version = self.extract_version_simple(file_path)
                self.show_notification_message(f"Доступно обновление (v.{version})")
                self.stop_checking = True
                if skipped:
                    self.show_notification_message("Подготовка к процедуре обновления...\n Не выключайте приложение")
                    debug_logger.info(f"[SKIP] Файл уже существует")
                    self.open_window_and_update()
                else:
                    debug_logger.info(f"[OK] Новый файл загружен")
            else:
                debug_logger.error(f"[ERROR] Не удалось скачать: {error}")
        
        self.toggle_update_button()

    def extract_version_simple(self, file_path):
        """Извлекает версию из пути (работает с обоими форматами)"""
        filename = os.path.basename(file_path)
        
        # Формат 1: "2.1.0_temp" (дельта-обновление)
        if filename.endswith('_temp'):
            return filename.replace('_temp', '')
        
        # Формат 2: "stable_2.1.0.zip" или "exp_2.1.0.zip" (полное обновление)
        parts = filename.split('_')
        if len(parts) >= 2:
            # Ищем часть с версией (содержит точки)
            for part in parts:
                if '.' in part:
                    return part.replace('.zip', '')
        
        # Если не нашли - возвращаем как есть
        return filename.split('_')[0] if '_' in filename else filename

    def open_window_and_update(self):
        """Обработка действия, если апдейт уже был скачан (активация окна)"""
        if not self.isVisible():
            self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        QApplication.processEvents()
        QTimer.singleShot(500, lambda: self.update_app(type_version=self.type_version,
                                                       batch_update=self.is_batch_update))

    def init_logger(self):
        """Инициализация логгера."""
        # Используем ваш конфиг логов
        self.logger = logging.getLogger("assistant")

    def init_file_watcher(self):
        """Инициализация FileSystemWatcher для отслеживания изменений файла логов."""
        self.file_watcher = QFileSystemWatcher([self.log_file_path])
        self.file_watcher.fileChanged.connect(self.update_logs)

    def _check_log_file_size(self, max_lines=100):
        """Проверяет, превышает ли файл логов max_lines строк. Если да — очищает его."""
        try:
            if not os.path.exists(self.log_file_path):
                return

            with open(self.log_file_path, "r", encoding="utf-8-sig", errors="replace") as file:
                lines = file.readlines()

            if len(lines) > max_lines:
                # Очищаем файл и оставляем только последние 10 строк
                with open(self.log_file_path, "w", encoding="utf-8") as file:
                    file.writelines(lines[-10:])
                self.log_area.clear()  # Очищаем QTextEdit
                self.last_position = 0  # Сбрасываем позицию чтения
                self.logger.info("Файл логов превысил лимит, очищен.")
        except Exception as e:
            self.logger.error(f"Ошибка при проверке размера логов: {e}")

    def load_existing_logs(self):
        """Загрузка всех записей из файла логов при запуске."""
        try:
            if not os.path.exists(self.log_file_path):
                self.logger.info("Файл логов не найден. Создаем новый.")
                with open(self.log_file_path, "w", encoding="utf-8"):
                    pass  # Создаем пустой файл
            else:
                self._check_log_file_size()  # Проверяем и чистим, если нужно

            with open(self.log_file_path, "r", encoding="utf-8-sig", errors="replace") as file:
                existing_logs = file.read()
                self.log_area.setPlainText(existing_logs)
                self.last_position = file.tell()
        except Exception as e:
            self.logger.error(f"Ошибка при чтении файла логов: {e}")
            self.log_area.append(f"Ошибка при чтении файла логов: {e}")

    def check_log(self):
        """Проверка файла на наличие новых данных."""
        try:
            if not os.path.exists(self.log_file_path):
                self.logger.warning("Файл логов не найден. Пытаемся переподключиться...")
                self.file_watcher.removePath(self.log_file_path)
                self.file_watcher.addPath(self.log_file_path)
                return

            self._check_log_file_size()  # Проверяем, не превышен ли лимит

            with open(self.log_file_path, "r", encoding="utf-8-sig", errors="replace") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                if new_lines:
                    self.text_append("".join(new_lines))
                    self.last_position = file.tell()
        except FileNotFoundError:
            self.logger.warning("Файл логов не найден, переподключаем FileSystemWatcher.")
            self.file_watcher.removePath(self.log_file_path)
            self.file_watcher.addPath(self.log_file_path)
        except Exception as e:
            self.logger.error(f"Ошибка при чтении файла логов: {e}")
            self.log_area.append(f"Ошибка при чтении файла логов: {e}")

    def update_logs(self):
        """Обновление логов при изменении файла."""
        self.check_log()

    def text_append(self, text):
        """Добавление текста в QTextEdit с автоматической прокруткой."""
        self.log_area.append(text)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def check_or_create_folder(self):
        folder_path = get_path('user_settings', "links for assist")

        # Проверяем, существует ли папка
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            debug_logger.info("Папка links for assist найдена")
        else:
            # Если папка не существует, создаем её
            try:
                os.makedirs(folder_path)  # Создаем папку
                debug_logger.info('Папка "links for assist" была создана.')
                debug_logger.info(f"Путь хранения ярлыков: {folder_path}")
            except Exception as e:
                logger.error(f'Ошибка при создании папки для хранения ярлыков: {e}')
                debug_logger.error(f'Ошибка при создании папки для хранения ярлыков: {e}')

    def reload_commands(self):
        self.load_commands()

    def load_commands(self):
        """Загружает команды из JSON-файла."""
        file_path = get_path('user_settings', 'commands.json')
        try:
            if not os.path.exists(file_path):
                logger.info(f"Файл {file_path} не найден.")
                debug_logger.debug(f"Файл {file_path} не найден.")
                return {}

            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Ошибка: файл {file_path} содержит некорректный JSON.")
            debug_logger.error(f"Ошибка: файл {file_path} содержит некорректный JSON.")
            return {}
        except Exception as e:
            logger.error(f"Ошибка при загрузке команд из файла {file_path}: {e}")
            debug_logger.error(f"Ошибка при загрузке команд из файла {file_path}: {e}")
            return {}

    def save_commands(self):
        """Централизованное сохранение команд"""
        try:
            path = get_path('user_settings', 'commands.json')
            with open(path, 'w', encoding='utf-8') as file:
                json.dump(self.commands, file, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"Ошибка сохранения команд: {e}")

    def load_settings(self):
        """Загружает настройки из settings.json."""
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}  # Если файл не найден или повреждён, возвращаем пустой словарь

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
            "start_win": self.toggle_start,
            "is_widget": self.is_widget,
            "is_keep_watch": self.is_keep_watch,
            "input_device_id": self.input_device_id,
            "input_device_name": self.input_device_name,
            "is_snow": self.is_snow,
            "is_garland": self.is_garland
        }
        try:
            # Проверяем, существует ли папка user_settings
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

            self.show_notification_message("Настройки сохранены!")
            debug_logger.debug("Настройки сохранены.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {e}")
            debug_logger.error(f"Ошибка при сохранении настроек: {e}")
            raise  # Повторно выбрасываем исключение, если нужно

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
                "start_win": True,
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
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Одинарный щелчок
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

        # Центрирование (как в трее)
        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

    def custom_hide(self):
        self.close_child_windows.emit()
        self.hide()

    def changeEvent(self, event):
        """Обработка изменения состояния окна."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self.hide()
        super().changeEvent(event)

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.is_force_close:
            self.close_child_windows.emit()

            if self.is_assistant_running:
                self.stop_assist()
            event.accept()
        else:
            self.custom_hide()
            event.ignore()

    def on_shutdown(self):
        try:
            self.force_close()
        except Exception as e:
            debug_logger.error(f"Ошибка при закрытии приложения: {e}")

    def close_app(self):
        """Закрытие приложения."""
        if self.is_assistant_running:
            self.stop_assist()
            QTimer.singleShot(2500, self.force_close) # Время для проигрывания аудио перед закрытием
        else:
            self.force_close()

    def force_close(self):
        """Принудительное закрытие, игнорируя все подтверждения"""
        self.is_force_close = True
        self.close()

        # Гарантированное завершение через 100 мс
        QTimer.singleShot(100, lambda: [
            QApplication.closeAllWindows(),
            QApplication.quit()
        ])

    def cleanup_before_exit(self):
        """Подготовка к выходу"""
        try:
            # Проверяем существование splash и check_thread
            if hasattr(self, 'splash') and self.splash:
                # Безопасно проверяем наличие check_thread
                if hasattr(self.splash, 'check_thread') and self.splash.check_thread:
                    self.splash.check_thread.quit()
                    self.splash.check_thread.wait(1000)
                
                # Закрываем splash если он открыт
                if self.splash.isVisible():
                    self.splash.close()
                    
            # Закрываем главное окно
            self.close()
            
        except Exception as e:
            debug_logger.error(f"Ошибка при завершении: {e}")
            # Принудительно закрываем
            self.close()

    def handle_close_confirmation(self, confirmed, event, dialog):
        """Метод устарел и не используется"""
        dialog.close()
        if confirmed:
            self.stop_assist()
            event.accept()
        else:
            event.ignore()

    def start_assist_toggle(self):
        """Обработка нажатия кнопки 'Старт ассистента' или 'Остановить работу'"""
        if self.is_assistant_running:
            self.stop_assist()
        else:
            self.run_assist()

    def run_assist(self):
        """Запуск ассистента"""
        self.is_assistant_running = True
        self.buttons["start"].setText("Остановить работу")
        # self.start_button.setText("Остановить работу")  # Меняем текст кнопки
        self.log_area.append("Ассистент запущен...")  # Добавляем запись в лог

        # Запуск ассистента в отдельном потоке
        self.assistant_thread = threading.Thread(target=self.run_script)
        self.assistant_thread.start()

    def stop_assist(self, reaction=True):
        """Остановка ассистента"""
        self.is_assistant_running = False
        self.buttons["start"].setText("Старт ассистента")
        # self.start_button.setText("Старт ассистента")
        debug_logger.info("[Ассистент остановлен]")
        if reaction:
            debug_logger.info("Реакция на выключение ассистента...")
            self.get_reaction(threading=True, name="close_assist_folder", trace="stop_assist in main")

        # Безопасная остановка потока
        if hasattr(self, 'assistant_thread') and self.assistant_thread is not None:
            try:
                if self.assistant_thread.is_alive() and self.assistant_thread != threading.current_thread():
                    self.assistant_thread.join(timeout=1.0)  # Уменьшаем таймаут
                    if self.assistant_thread.is_alive():
                        debug_logger.warning("Поток ассистента не завершился в течение таймаута")
            except Exception as e:
                debug_logger.error(f"Ошибка при остановке потока: {e}")
            finally:
                self.assistant_thread = None

        # Очистка аудиоресурсов
        self.cleanup_audio_resources()

    def get_reaction(self, threading=True, detail=False, name="", trace=""):
        try:
            path = self.audio_paths.get(f'{name}')
            if not path:
                logger.error(f"[assistant.get_reaction] Путь не найден")
                debug_logger.error(f"[assistant.get_reaction] Путь не найден")
                return

            if threading:
                if detail:
                    thread_react_detail(path, trace)
                else:
                    thread_react(path, trace)
            else:
                react(path, trace)

        except Exception as e:
            debug_logger.error(f"[assistant.get_reaction] Ошибка: {e}")

    def censor_counter(self):
        # Путь к CSV-файлу
        CSV_FILE = get_path('user_settings', 'censor_counter.csv')

        # Создаем файл, если он не существует
        if not Path(CSV_FILE).exists():
            with open(CSV_FILE, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['date', 'score', 'total_score'])  # Заголовки столбцов

        # Получаем текущую дату
        today = datetime.now().strftime('%Y-%m-%d')

        # Читаем данные из CSV
        rows = []
        with open(CSV_FILE, mode='r') as file:
            reader = csv.reader(file)
            headers = next(reader)  # Пропускаем заголовки
            for row in reader:
                # Пропускаем пустые строки
                if not row:
                    continue
                # Проверяем, что строка содержит достаточно данных
                if len(row) >= 3:
                    rows.append(row)

        # Ищем запись для текущей даты
        found = False
        total_score = 0
        for row in rows:
            try:
                # Преобразуем score и total_score в int
                row[1] = int(row[1])
                row[2] = int(row[2])
                total_score += row[1]  # Считаем общее количество

                if row[0] == today:
                    # Если запись найдена, увеличиваем score на 1
                    row[1] += 1
                    row[2] += 1
                    found = True
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка при обработке строки {row}: {e}")
                debug_logger.error(f"Ошибка в методе censor_counter при обработке строки {row}: {e}")
                continue

        # Если запись не найдена, добавляем новую
        if not found:
            rows.append([today, 1, total_score + 1])

        # Записываем обновленные данные обратно в CSV
        with open(CSV_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)  # Записываем заголовки
            writer.writerows(rows)  # Записываем данные
            
    def check_keywords_file(self):
        """
        Проверяет наличие файла keywords.json и создает его со стандартными значениями из default_keywords.json если нет
        """
        keywords_path = get_path("user_settings", "keywords.json")
        default_keywords_path = get_path("bin", "default_keywords.json")

        if not os.path.exists(keywords_path):
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
            return False
        
    def apply_keywords_for_values(self):
        try:
            keywords_path = get_path("user_settings", "keywords.json")
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
            debug_logger.error(f"Ошибка во время применения списков: {e}")
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
            'пэйнт': (open_paint, close_paint),
            'переменные': (open_path, None),
            'диспетчер': (open_taskmgr, close_taskmgr),
            'корзина': (open_recycle_bin, close_recycle_bin),
            'ап дата': (open_appdata, close_appdata),
            'панель': (self._open_widget_signal, self._close_widget_signal),
            'виджет': (self._open_widget_signal, self._close_widget_signal),
            "микрофон": (self.toggle_mute_discord, self.toggle_mute_discord),
            "микро": (self.toggle_mute_discord, self.toggle_mute_discord),
            "ютуб": (lambda: self.start_default_command("ютуб", "open"), None)
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
                debug_logger.info(f"[last_unrecognized_command]---> {self.last_unrecognized_command}")
                current_time = time.time()
                
                words = text.split()

                all_commands = self.get_command_names()
                all_names = [self.assistant_name, self.assist_name2, self.assist_name3]

                # Список фраз действие-команда, ["action command", ...]
                action_command = self.handle_text_smart(text, self.all_actions)

                # Чистая команда без действия, "command"
                clean_target = self._extract_clean_target(text, self.all_actions)

                # has_action_words = any(kw in text.lower() for kw in all_actions)
                if self.find_action(text, self.action_up, self.action_down, self.all_actions)[0] is not None:
                    has_action_words = True
                else:
                    has_action_words = False
                
                # Проверка на наличие команд для управления    
                self.is_keyword_player = any(self.find_closest_command(word, self.keywords_player, threshold=80) for word in words)

                debug_logger.info(f"[has_action_words] {has_action_words}")

                debug_logger.info(f"[text------>] {text}"
                                  f"\n[action_command------>] {action_command}"
                                  f"\n[clean_target------>] {clean_target}")

                # Сбрасываем контекст, если прошло более 10 секунд без активности
                if self.last_unrecognized_command and (current_time - last_activity_time) > 10:
                    self.last_unrecognized_command = None
                    logger.info("Сброс контекста из-за неактивности")
                    debug_logger.info("Сброс контекста из-за неактивности")

                # Обновляем время последней активности при получении текста
                last_activity_time = current_time

                # Сбрасываем флаг упоминания имени, если прошло более n секунд
                if name_mentioned and (current_time - name_mentioned_time) > 20:
                    name_mentioned = False
                    name_mentioned_time = None
                    logger.info("Сброс флага упоминания имени")
                    debug_logger.info("Сброс флага упоминания имени")

                # Проверка цензуры
                if any(self.find_closest_command(word, self.censored_list, threshold=80) for word in words):
                    self.censor_counter()
                    if self.is_censored:
                        self.get_reaction(name="censored_folder")

                # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                # 🎯 ОБРАБОТКА ПОДТВЕРЖДЕНИЯ КОМАНДЫ ("ДА"/"НЕТ")
                # Если мы ожидаем подтверждение — игнорируем всё, кроме "да" или "нет"
                if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'confirm':
                    if self.last_unrecognized_command.get('is_shutdown'):
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            logger.info("Таймаут подтверждения — сброс")
                            debug_logger.info("Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            debug_logger.info("Пользователь подтвердил команду(ы).")

                            turnoff_value = self.last_unrecognized_command.get('is_shutdown')
                            self.set_shutdown(is_shutdown=turnoff_value)

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            debug_logger.info("Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            debug_logger.info("Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
                            continue
                    else:
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            logger.info("Таймаут подтверждения — сброс")
                            debug_logger.info("Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            debug_logger.info("Пользователь подтвердил команду(ы).")

                            pending_commands = self.last_unrecognized_command.get('pending_commands')

                            any_executed = False

                            for cmd_info in pending_commands:
                                action_type = cmd_info['action_type']
                                suggested_cmd = cmd_info['suggested_command']

                                debug_logger.info(f"Выполняем: {action_type} {suggested_cmd}")

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
                                    restored_command = f"{action_type} {suggested_cmd}"
                                    app_processed = self.handle_app_command(restored_command, action_type)
                                    folder_processed = self.handle_folder_command(restored_command, action_type)
                                    if app_processed or folder_processed:
                                        any_executed = True

                            if any_executed:
                                pass
                            else:
                                self.get_reaction(detail=True, name="error_file")
                                message = "Не удалось выполнить команду(ы)."
                                self.show_supply_notice(message, is_confirm=True)
                                debug_logger.info(f"Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            debug_logger.info("Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            debug_logger.info("Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            debug_logger.info(f"Отправлено уведомление ---> {message}")
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
                    if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'correction':
                        if text:
                            # Обновляем время последней активности при обработке команды
                            last_activity_time = current_time

                            _, new_action_type = self.find_action(text, self.action_up, self.action_down, self.all_actions)

                            current_action_type = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                            # Если действие изменилось — обновляем контекст
                            if new_action_type and new_action_type != current_action_type:
                                self.last_unrecognized_command['pending_commands'][0]['action_type'] = new_action_type
                                debug_logger.info(f"Действие обновлено на: {new_action_type}")

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
                                debug_logger.info(f"Восстановленная команда: {restored_command}")

                                # Пытаемся обработать как приложение и как папку
                                app_processed = self.handle_app_command(restored_command, action_type)
                                folder_processed = self.handle_folder_command(restored_command, action_type)

                                if not folder_processed and not app_processed:
                                    logger.warning(f"Команда не обработана: {restored_command}")
                                    debug_logger.warning(f"Команда не обработана: {restored_command}")
                                    self.get_reaction(name="what_folder",
                                                    trace="Реакция в блоке, где режим корректировки команды")

                                    self.last_unrecognized_command['pending_commands'][0][
                                        'suggested_command'] = clean_target

                                    debug_logger.info(f"Обновлена цель для уточнения: {clean_target}")
                                    self.show_supply_notice(text)
                                    debug_logger.info(f"Отправлено уведомление ---> {text}")
                                    self.last_unrecognized_command = None
                                    continue
                            # Конец блока В.

                            if any(word in text for word in self.keywords_reject):
                                debug_logger.info("Пользователь отменил команду(ы).")
                                self.get_reaction(name="confirm_folder")
                                self.last_unrecognized_command = None
                                message = "Хорошо, отменяю."
                                self.show_supply_notice(message, is_confirm=True)
                                debug_logger.info(f"Отправлено уведомление ---> {message}")
                                continue

                            if not default_list and not custom_list:
                                self.get_reaction(name="what_folder",
                                                trace="Реакция в блоке, где режим корректировки команды")
                                self.show_supply_notice(text)
                                debug_logger.info(f"Отправлено уведомление ---> {text}")

                if has_assistant_name:
                    debug_logger.info("<<< Условие, где есть Имя ассистента >>>")
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
                    elif self.find_closest_command(clean_target, self.keywords_restart):
                        self.get_confirm_shutdown(clean_target, text, action_type, is_shutdown=False)
                        continue

                    if len(words) <= 4 and has_name:
                        if not has_action_words:
                            if not self.is_keyword_player:
                                # Если нет слов-действий и в тексте нет команд для управления плеером — воспроизводим эхо
                                self.get_reaction(name="echo_folder")

                    final_commands = self.handle_text_smart(text, self.all_actions)
                    debug_logger.info(f"[handle_text_smart]---> {final_commands}")

                    for command in final_commands:
                        command = command.strip()
                        debug_logger.info(f"[Команда в цикле из списка выше] {command}")

                        _, action_type = self.find_action(command, self.action_up, self.action_down, self.all_actions)

                        if action_type:
                            clean_target = self._extract_clean_target(command, self.all_actions)
                            # Ищем совпадение со специальными командами

                            default_list = self.find_closest_command(clean_target, default_commands_keys)
                            debug_logger.info(f"[list] {default_list}")
                            debug_logger.info(f"[action_type] {action_type}")
                            debug_logger.info(f"[clean_target] {clean_target}")

                            if default_list:
                                if action_type == 'open':
                                    default_commands[default_list][0]()
                                elif action_type == 'close':
                                    if default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                            else:
                                # Пытаемся обработать команду
                                app_processed = self.handle_app_command(command, action_type)
                                folder_processed = self.handle_folder_command(command, action_type)

                                if not app_processed and not folder_processed:
                                    if clean_target:
                                        debug_logger.info(f"[clean_target] {clean_target}")

                                        # Ищем похожие команды
                                        closest_cmd = self.find_closest_command(clean_target, all_commands)
                                        debug_logger.info(f"[closest_cmd] {closest_cmd}")

                                        if closest_cmd:
                                            message = f"Вы имели в виду: '{closest_cmd}'?\nСкажите: Да/Нет"
                                            self.show_supply_notice(message, is_confirm=True)
                                            thread_play_sound(type_sound="what")
                                            debug_logger.info(f"Отправлено уведомление ---> {message}")

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

                    if trigger_react:
                        self.show_supply_notice(text)
                        self.get_reaction(name="what_folder", trace="Реакт из триггера")
                        debug_logger.info(f"Сработал триггер реакции. Отправлено уведомление ---> {text}")
                        continue

                # Флаг для контроля над обработкой команд без имени ассистента (не относится к плееру)
                if self.is_keep_watch:
                    if has_action_words and not has_assistant_name:
                        debug_logger.info("<<< Условие без имени ассистента, только действие и команда >>>")

                        if self.find_closest_command(clean_target, self.screen_list):
                            self.capture_area()

                        final_commands = self.handle_text_smart(text, self.all_actions)
                        debug_logger.info(f"[final_commands] {final_commands}")

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

                            debug_logger.info(f"[command] {command}")
                            debug_logger.info(f"[clean_target] {clean_target}")
                            debug_logger.info(f"[closest_cmd] {closest_cmd}")

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
                            debug_logger.info(f"Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = {
                                'mode': 'confirm',
                                'original_text': text,
                                'pending_commands': pending_commands
                            }
                            continue

                # Обработка плеера
                if self.is_keyword_player or has_assistant_name:

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
            debug_logger.error(f"Ошибка в основном цикле ассистента: {e}")
            debug_logger.error(traceback.format_exc())
            self.show_message(f"Ошибка в основном цикле ассистента: {e}", "Ошибка",
                              "warning")

    # "Основной цикл ассистента(конец)"
    # "--------------------------------------------------------------------------------------------------"
    # "Основной цикл ассистента(конец)"

    # def install_game_mode(self):
    #     try:
    #         self.game_mode = GamepadManager()
    #         if self.game_mode.init_success:
    #             logger.info("Игровой режим успешно инициализирован")
    #         else:
    #             logger.warning("Не удалось инициализировать игровой режим")
    #             self.game_mode = None
    #     except Exception as e:
    #         logger.error(f"Ошибка при инициализации GamepadManager: {e}")
    #         self.game_mode = None
    #
    # def start_game_mode(self):
    #     self.install_game_mode()
    #     self.game_mode.set_game("God of War")
    #     logger.info(self.game_mode)
    #     logger.info(self.game_mode.running)
    #     if self.game_mode and not self.game_mode.running:
    #         self.game_mode.start_proxy()
    #         self.game_mode_bool = True
    #         logger.info("Игровой режим активирован")
    #     else:
    #         logger.warning("Невозможно активировать игровой режим")
    #
    # def stop_game_mode(self):
    #     if self.game_mode and self.game_mode.running:
    #         self.game_mode.stop_proxy()
    #         self.game_mode.cleanup()
    #         self.game_mode_bool = False
    #         logger.info("Игровой режим деактивирован")

    def get_confirm_shutdown(self, closest_cmd, text, action_type, is_shutdown=True):
        try:
            if is_shutdown:
                action_pc = "Выключить"
            else:
                action_pc = "Перезагрузить"
            message = f"{action_pc} ПК?\n\nСкажите: Да/Нет"
            self.show_supply_notice(message, is_confirm=True)
            thread_play_sound(type_sound="what")
            debug_logger.info(f"Отправлено уведомление ---> {message}")

            # Сохраняем контекст
            self.last_unrecognized_command = {
                'mode': 'confirm',
                'original_text': text,
                'is_shutdown': action_pc,
            }
        except Exception as e:
            debug_logger.error(f"Ошибка в методе get_confirm_shutdown: {e}")

    def set_shutdown(self, is_shutdown):
        try:
            if is_shutdown == "Выключить":
                shutdown_windows()
                debug_logger.info("Выполняется обработка запроса: shutdown windows")
            elif is_shutdown == "Перезагрузить":
                restart_windows()
                debug_logger.info("Выполняется обработка запроса: restart windows")

        except Exception as e:
            debug_logger.error(f"Ошибка в методе set_shutdown: {e}")

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

        # ✅ НЕЧЁТКОЕ УДАЛЕНИЕ слов-действий
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
        Пример: "джонни запусти калькулятор и пейнт" → ["запустить калькулятор", "запустить пейнт"]
        """
        if not text:
            return []

        text_lower = text.lower()
        words = text_lower.split()

        # 1. Находим все действия с позициями
        actions_in_text = []  # [(index, raw_word, normalized_action), ...]
        for i, word in enumerate(words):
            closest_action = self.find_closest_command(word, all_actions, threshold=threshold)
            if closest_action:
                actions_in_text.append((i, word, closest_action))

        if not actions_in_text:
            return []

        # 2. Для каждого действия — определяем "область целей": от следующего слова до следующего действия
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

        for action, start, end in command_blocks:
            # Берём подмассив слов в области
            target_words = words[start:end]

            # Разбиваем на цели — учитываем разделители "и", "или", ","
            # Сначала соберём все n-граммы и отдельные слова
            candidates = []

            # Добавляем отдельные слова
            for i, word in enumerate(target_words):
                candidates.append((i, word, word))  # (local_index, raw, candidate)

            # Добавляем биграммы и триграммы
            for n in [2, 3]:
                for i in range(len(target_words) - n + 1):
                    ngram = " ".join(target_words[i:i + n])
                    candidates.append((i, ngram, ngram))

            # Убираем дубликаты по raw-значению
            seen = set()
            unique_candidates = []
            for local_idx, raw, candidate in candidates:
                if raw not in seen:
                    seen.add(raw)
                    unique_candidates.append((local_idx, raw, candidate))

            # Теперь для каждого кандидата ищем ближайшую команду
            for local_idx, raw, candidate in unique_candidates:
                # Пробуем найти похожую команду
                closest_target = self.find_closest_command(candidate, all_targets, threshold=threshold)
                if closest_target:
                    final_commands.append(f"{action} {closest_target}")
                else:
                    # Если не нашли — всё равно добавляем как есть (можно закомментировать, если не нужно)
                    final_commands.append(f"{action} {candidate}")

        # 4. Убираем дубликаты команд (если вдруг получилось "запустить калькулятор" дважды)
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
        debug_logger.debug("Загрузка моделей для распознавания...")

        model_path_ru = get_path("bin", "model_ru")
        # model_path_en = get_path("bin", "model_en")
        debug_logger.debug(f"Загружена модель RU - {model_path_ru}")
        # debug_logger.debug(f"Загружена модель EN - {model_path_en}")

        try:
            self.model_ru = Model(model_path_ru)
            # self.model_en = Model(model_path_en)
            logger.info("Модели успешно загружены.")
            debug_logger.info("Модели успешно загружены.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели: {e}. Возможно путь содержит кириллицу.")
            debug_logger.error(f"Ошибка при загрузке модели: {e}", exc_info=True)
            return False

        try:
            # Инициализация распознавателей
            self.rec_ru = KaldiRecognizer(self.model_ru, 16000)
            # self.rec_en = KaldiRecognizer(self.model_en, 16000)

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
                self.input_device_id = target_id  # обновляем ID
                device_name = sd.query_devices(target_id)['name']
                self.input_device_name = device_name  # фиксируем имя
                debug_logger.info(f"Аудиопоток запущен: '{device_name}' (ID={target_id})")
            except Exception as e:
                debug_logger.error(f"Не удалось открыть выбранное устройство (ID={target_id}): {e}")
                # Fallback: попробовать без указания устройства (по умолчанию)
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
                    debug_logger.warning(f"Используется устройство по умолчанию: '{fallback_name}'")
                except Exception as e2:
                    debug_logger.error("Не удалось запустить ни одно устройство.", exc_info=True)
                    raise e2

            # ✅ Успешно запущено
            self.microphone_available = True
            self.last_audio_time = time.time()  # начальное значение для watchdog
            return True

        except Exception as e:
            debug_logger.error(f"Критическая ошибка при инициализации аудио: {e}", exc_info=True)
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

            # Сортировка: совпадение по имени → приоритет API → индекс
            if candidates:
                best = max(candidates, key=lambda x: (x[2], x[1], -x[0]))
                return best[0]

            return default_in  # fallback

        except Exception as e:
            debug_logger.warning(f"Ошибка выбора микрофона: {e}")
            return sd.default.device[0]  # двойной fallback

    def audio_callback(self, indata, frames, time_info, status):
        """
        :param time_info: Временные метки от PortAudio
        """
        if status:
            debug_logger.warning(f"⚠️ Статус аудио: {status}")
            if any(keyword in str(status).lower() for keyword in ['overrun', 'underrun']):
                pass  # Будет обработано по тишине
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
            debug_logger.error(f"Ошибка при анализе громкости: {e}")

        data = indata.tobytes()
        ru_text = ""
        en_text = ""

        try:
            if self.rec_ru.AcceptWaveform(data):
                result = json.loads(self.rec_ru.Result())
                ru_text = result.get("text", "").strip().lower()

            # if self.rec_en.AcceptWaveform(data):
            #     result = json.loads(self.rec_en.Result())
            #     temp_en = result.get("text", "").strip().lower()
            #     if temp_en and temp_en != "huh":
            #         en_text = temp_en

            final_text = ru_text or en_text
            if final_text:
                self.on_final_result(final_text)

        except Exception as e:
            debug_logger.error(f"Ошибка в обработке распознавания: {e}")

    def on_final_result(self, text):
        """Вызывается при распознавании фразы. Логирует и отправляет дальше."""
        logger.info(f"[Распознано] {text}")
        debug_logger.info(f"[Распознано] {text}")

        # Если есть активная очередь (например, get_audio() ждёт), — кладём туда
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
        # Вариант 1: если хочешь оставить yield — используй очередь
        from queue import Queue
        q = Queue()

        # Сохраним ссылку, чтобы можно было выйти
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
        debug_logger.info("Проверка микрофона через sounddevice...")
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
                debug_logger.info(f"Найдено рабочих микрофонов: {len(active_mics)}")
                self.microphone_available = True
                return True
            else:
                logger.info("Нет доступных микрофонов.")
                self.microphone_available = False
                return False

        except Exception as e:
            debug_logger.error(f"Ошибка проверки микрофона: {e}")
            self.microphone_available = False
            return False

    def _check_microphone_wrapper(self):
        try:
            self.check_microphone()
            if self.microphone_available:
                if not self.is_assistant_running:
                    self.show_notification_message(message="Микрофон обнаружен!")
                    self.run_assist()
                    # self.check_micro_btn.hide()
                else:
                    self.show_notification_message(message="Микрофон подключен!")
            else:
                self.show_notification_message(message="Микрофон не найден!")
        except Exception as e:
            logger.error(f"Ошибка в _check_microphone_wrapper: {e}")

    def cleanup_audio_resources(self):
        """Безопасное освобождение аудиоресурсов"""
        try:
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    if self.audio_stream.active:
                        self.audio_stream.abort()  # быстро остановить
                except Exception as e:
                    debug_logger.error(f"Ошибка при остановке аудиопотока: {e}")
                finally:
                    self.audio_stream = None
                    debug_logger.info("Аудиопоток остановлен и очищен.")
        except Exception as e:
            debug_logger.error(f"Критическая ошибка аудиопотока: {e}", exc_info=True)

    def check_silence_timeout(self):
        """Проверяет, сколько времени прошло с последнего звука"""
        if not self.is_assistant_running or not self.microphone_available:
            return

        if self.last_audio_time is None:
            return  # Ещё не было данных

        silent_duration = time.time() - self.last_audio_time

        if silent_duration > 10.0:  # 10 секунд тишины
            debug_logger.warning(f"🔊 Нет звука более 10 сек ({silent_duration:.1f}s) — перезапуск аудиопотока")
            self.restart_audio_stream()

    def restart_audio_stream(self):
        """Перезапускает только InputStream, не трогая модели и ассистента"""
        debug_logger.info("🔄 Перезапуск аудиопотока...")

        try:
            # Останавливаем старый поток
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                if self.audio_stream.active:
                    self.audio_stream.abort()
                self.audio_stream = None
                debug_logger.info("Старый аудиопоток остановлен")

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

            debug_logger.info("✅ Аудиопоток успешно перезапущен (по умолчанию)")

        except Exception as e:
            debug_logger.error(f"❌ Не удалось перезапустить поток: {e}")
            # Можно попробовать повторно через 10 сек
            QTimer.singleShot(10000, self.restart_audio_stream)

    def handle_app_command(self, text, action):
        """Обработка команд для приложений"""
        for keyword, filename in self.commands.items():
            if keyword in text:
                if (not filename.endswith('.lnk') and not filename.endswith('.url')
                        and not self.commands_manager.is_url_string(filename)):
                    return False  # Прекращаем обработку, если это папка
                self.commands_manager.handler_links(filename, action)  # Вызываем обработчик ярлыков
                return True  # Возвращаем True, если команда была успешно обработана
        return False  # Возвращаем False, если команда не была найдена

    def handle_folder_command(self, text, action):
        """Обработка команд для папок"""
        for keyword, folder_path in self.commands.items():
            if keyword in text:
                if (folder_path.endswith('.lnk') or folder_path.endswith('.url')
                        or self.commands_manager.is_url_string(folder_path)):
                    return False  # Прекращаем обработку, если это файл приложения
                if self.commands_manager.handler_folder(folder_path, action):  # Вызываем обработчик папок
                    return True  # Возвращаем True, если команда была успешно обработана
        return False  # Возвращаем False, если команда не была найдена

    def handler_default_command(self, command, action):
        for keyword, filename in self.default_commands.items():
            if keyword in command:
                if (not filename.endswith('.lnk') and not filename.endswith('.url')
                        and not self.commands_manager.is_url_string(filename)):
                    return False  # Прекращаем обработку, если это папка
                self.commands_manager.handler_links(filename, action)  # Вызываем обработчик ярлыков
                return True  # Возвращаем True, если команда была успешно обработана
        return False  # Возвращаем False, если команда не была найдена

    def toggle_mute_discord(self):
        toggle = ToggleMuteDiscord()
        toggle.main()

    def start_default_command(self, command, action):
        self.handler_default_command(command, action)
        debug_logger.info(f"[start_default_command] Команда {command} выполнена с действием {action}")

    def _open_widget_signal(self):
        try:
            gui_signals.open_widget_signal.emit()
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске сигнала виджета: {e}")

    def _close_widget_signal(self):
        try:
            gui_signals.close_widget_signal.emit()
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске сигнала виджета (на закрытие): {e}")

    def open_widget(self, is_auto_start=False):
        QTimer.singleShot(100, lambda: self._show_smart_widget(is_auto_start))
    
    def _show_smart_widget(self, is_auto_start=False):
        try:
            # Проверяем существует ли виджет и не удален ли он
            widget_exists = (
                hasattr(self, 'widget_window') and
                self.widget_window is not None)

            if widget_exists and self.widget_window.isVisible():
                # Полное закрытие с очисткой
                self._close_smart_widget()
                return

            if widget_exists:
                # Виджет существует, но скрыт - показываем
                self.widget_window.show()
            else:
                # Создаем новый виджет
                self.widget_window = SmartWidget(self)
                # Устанавливаем атрибут для автоматического удаления
                self.widget_window.setAttribute(Qt.WA_DeleteOnClose, True)
                # Подключаем сигнал уничтожения
                self.widget_window.destroyed.connect(self._on_widget_destroyed)
                self.widget_window.show()

            if not is_auto_start:
                self.get_reaction(name="approve_folder")

        except Exception as e:
            debug_logger.error(f"Ошибка при открытии виджета: {str(e)}")
            self.show_notification_message(f"Ошибка при открытии виджета: {str(e)}")

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
        debug_logger.info("Виджет полностью уничтожен")

    def close_widget(self):
        try:
            if hasattr(self, "widget_window"):
                self.widget_window.close()
                self.get_reaction(name="approve_folder")
        except Exception as e:
            self.get_reaction(detail=True, name="error_file")
            self.show_notification_message(f"Ошибка при закрытии виджета (close_widget): {e}")
            debug_logger.error(f"Ошибка при закрытии виджета (close_widget): {e}")

    def restore_and_hide(self):
        """Показываем окно и сразу скрываем — чтобы оно стало 'живым'"""
        self.move(-2000, -2000)
        self.showNormal()  # Восстанавливаем из минимизации/скрытия
        self.raise_()  # Поднимаем поверх всех
        self.activateWindow()  # Делаем активным
        QTimer.singleShot(50, self.hide)

    def open_folder_shortcuts(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = get_path('user_settings', "links for assist")
        debug_logger.info(f"Открытие папки ярлыков , {folder_path}")

        # Проверяем, существует ли папка
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            os.startfile(folder_path)  # Открываем папку
        else:
            # Если папка не существует, создаем её
            try:
                os.makedirs(folder_path)  # Создаем папку
                logger.info(f'Папка "{folder_path}" была создана.')
                debug_logger.info(f'Папка "{folder_path}" была создана.')
                os.startfile(folder_path)  # Открываем папку после создания
            except Exception as e:
                logger.error(f'Ошибка при создании папки: {e}')
                debug_logger.error(f'Ошибка при создании папки: {e}')

    def open_folder_screenshots(self):
        """Обработка нажатия кнопки 'Открыть папку с ярлыками'"""
        folder_path = get_path('user_settings', "screenshots")
        debug_logger.info(f"Открытие папки скриншотов, {folder_path}")

        # Проверяем, существует ли папка
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            os.startfile(folder_path)  # Открываем папку
        else:
            # Если папка не существует, создаем её
            try:
                os.makedirs(folder_path)  # Создаем папку
                logger.info(f'Папка "{folder_path}" была создана.')
                debug_logger.info(f'Папка "{folder_path}" была создана.')
                os.startfile(folder_path)  # Открываем папку после создания
            except Exception as e:
                logger.error(f'Ошибка при создании папки: {e}')
                debug_logger.error(f'Ошибка при создании папки: {e}')

    def open_settings_of_tray(self):
        if self.isVisible():
            self.open_main_settings()
        else:
            self.showNormal()
            self.open_main_settings()

    def open_main_settings(self):
        """Открывает панель настроек"""
        try:
            if self.mutable_panel.isVisible() and self._current_panel == 'settings':
                self.hide_widget()
                return

            self._current_panel = 'settings'

            if self.mutable_panel.isVisible():
                # Уже открыто — запускаем анимацию переключения
                self._load_current_panel()
            else:
                self.show_widget()  # Запускаем анимацию открытия

        except Exception as e:
            debug_logger.error(f"Ошибка при открытии настроек: {e}")
            self.show_message(f"Ошибка при открытии настроек команд: {str(e)}", "Ошибка", "error")

    def get_size_widget(self, widget):
        width = widget.width()
        height = widget.height()
        size = widget.size()

    def show_widget(self):
        """Открывает панель настроек: сначала сжимаем, потом расширяем с изменяемой панелью"""
        # Анимация сжатия левой панели
        self._load_current_panel()
        self.show_layout(self.compact_layout)
        self.show_compact_buttons()
        self.get_size_widget(self.left_container)

        self.animation.stop()
        self.animation.setPropertyName(b"maximumWidth")
        self.animation.setStartValue(200)
        self.animation.setEndValue(1)
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InBack)
        # После сжатия — начинаем расширение с панелью настроек
        self.animation.finished.connect(self._expand_mutable_panel)
        self.animation.start()

    def _expand_mutable_panel(self):
        """Вызывается после сжатия: показываем панель и загружаем нужный контент"""
        self.left_buttons_panel.hide()
        self.animation.finished.disconnect(self._expand_mutable_panel)
        self.mutable_panel.show()

        self.animation.setStartValue(1)
        self.animation.setEndValue(self._get_panel_width())
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self.animation.start()

    def _clear_mutable_panel(self):
        """Очищает содержимое mutable_panel"""
        while self.mutable_layout.count():
            item = self.mutable_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_current_panel(self):
        """Загружает текущую панель (настройки или прочее)"""
        if self._current_panel == 'settings':
            if self.mutable_panel.isVisible():
                # Если панель уже видна - анимируем переключение
                self._animate_content_switch(self._load_settings_panel)
            else:
                self._load_settings_panel()
        elif self._current_panel == 'other':
            if self.mutable_panel.isVisible():
                # Если панель уже видна - анимируем переключение
                self._animate_content_switch(self._load_other_panel)
            else:
                self._load_other_panel()
        elif self._current_panel == 'guide':
            if self.mutable_panel.isVisible():
                # Если панель уже видна - анимируем переключение
                self._animate_content_switch(self._load_guide_panel)
            else:
                self._load_guide_panel()
        elif self._current_panel == 'commands':
            if self.mutable_panel.isVisible():
                # Если панель уже видна - анимируем переключение
                self._animate_content_switch(self._load_commands_panel)
            else:
                self._load_commands_panel()

    def hide_widget(self):
        """Закрывает панель настроек"""
        # Сброс эффектов
        for item in self.btn_svg_list:
            btn = item['button']
            btn.setGraphicsEffect(None)
            btn.setVisible(False)
        self.get_size_widget(self.mutable_panel)
        # Сжимаем
        self.animation.stop()
        self.animation.setPropertyName(b"maximumWidth")
        self.animation.setStartValue(self._get_panel_width())
        self.animation.setEndValue(1)
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InBack)
        self.animation.finished.connect(self._restore_buttons_panel)
        self.animation.start()

    def show_compact_buttons(self):
        for item in self.btn_svg_list:
            btn = item['button']
            btn.setVisible(True)

    def _restore_buttons_panel(self):
        """Восстанавливаем основную панель"""
        try:
            self.animation.finished.disconnect(self._restore_buttons_panel)
        except:
            pass

        self.mutable_panel.hide()
        self.left_buttons_panel.show()

        # Восстанавливаем ширину
        self.animation.setPropertyName(b"maximumWidth")
        self.animation.setStartValue(1)
        self.animation.setEndValue(220)
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self.animation.start()

    def _animate_content_switch(self, new_content_callback):
        """Анимация смены контента в видимой панели"""
        # Анимация исчезновения текущего контента
        self.get_size_widget(self.mutable_panel)
        self.animation.stop()
        self.animation.setPropertyName(b"maximumWidth")
        self.animation.setStartValue(self._get_panel_width())
        self.animation.setEndValue(1)
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.InBack)
        self.get_size_widget(self.mutable_panel)

        # После сжатия - загружаем новый контент и расширяем
        self.animation.finished.connect(lambda: self._expand_after_switch(new_content_callback))
        self.animation.start()

    def _expand_after_switch(self, new_content_callback):
        """Вызывается после сжатия при переключении контента"""
        self.animation.finished.disconnect()

        # Загружаем новый контент
        new_content_callback()

        # Анимация расширения
        self.animation.setStartValue(1)
        self.animation.setEndValue(self._get_panel_width())
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self.animation.start()

    def _get_panel_width(self):
        """Возвращает ширину панели в зависимости от текущего контента"""
        return 360

    def _load_settings_panel(self):
        """Инициализация виджетов настроек с SVG на вкладках"""
        if not hasattr(self, 'mutable_layout') or self.mutable_layout is None:
            return
        self.svg_settings_list = []
        self._clear_mutable_panel()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")
        self.tabs.setDocumentMode(True)

        self.tab_bar = self.tabs.tabBar()
        self.tab_bar.setObjectName("WSMainTabBar")

        # Создаем виджеты для содержимого вкладок
        main_widget = SettingsWidget(self)
        other_widget = OtherSettingsWidget(self)
        speech_hook_widget = SpeechHookManagerWidget(self)
        interface_widget = InterfaceWidget(self)
        settings_panel = SettingsWidgetPanel(self)

        self.tabs.addTab(main_widget, "")
        self.tabs.addTab(other_widget, "")
        self.tabs.addTab(speech_hook_widget, "")
        self.tabs.addTab(interface_widget, "")
        self.tabs.addTab(settings_panel, "")

        tab_bar = self.tabs.tabBar()

        def create_centered_svg_tab(svg_path):
            svg = CustomSvgWidget(svg_path)
            svg.setFixedSize(30, 30)

            svg.setStyleSheet("background: transparent;")
            self.style_manager.apply_color_svg(svg, strength=0.90)
            self.svg_settings_list.append({"svg": svg})
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 0, 0, 5)
            layout.addStretch()
            layout.addWidget(svg)
            layout.addStretch()
            return container

        tab_bar.setTabButton(0, QTabBar.ButtonPosition.LeftSide,
                             create_centered_svg_tab(self.icon_settings_path))
        tab_bar.setTabButton(1, QTabBar.ButtonPosition.LeftSide,
                             create_centered_svg_tab(self.icon_advance_settings_path))
        tab_bar.setTabButton(2, QTabBar.ButtonPosition.LeftSide,
                             create_centered_svg_tab(self.icon_speech_hook_path))
        tab_bar.setTabButton(3, QTabBar.ButtonPosition.LeftSide,
                             create_centered_svg_tab(self.icon_styles_path))
        tab_bar.setTabButton(4, QTabBar.ButtonPosition.LeftSide,
                             create_centered_svg_tab(self.icon_panel_path))

        self.tabs.setTabToolTip(0, "Основные настройки")
        self.tabs.setTabToolTip(1, "Дополнительные настройки")
        self.tabs.setTabToolTip(2, "Менеджер управления хук-словами")
        self.tabs.setTabToolTip(3, "Настройки интерфейса")
        self.tabs.setTabToolTip(4, "Настройки виджет-панели")

        self.mutable_layout.addWidget(self.tabs)
        self.mutable_layout.addSpacerItem(QSpacerItem(self._get_panel_width(), 1,
                                                      QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))

        if isinstance(self.tabs.widget(0), SettingsWidget):
            self.tabs.widget(0).voice_changed.connect(self.update_voice)

    def open_commands_settings(self):
        """Открывает встроенную панель 'Ваши Команды'"""
        try:
            if self.mutable_panel.isVisible() and self._current_panel == 'commands':
                self.hide_widget()
                return

            self._current_panel = 'commands'

            if self.mutable_panel.isVisible():
                # Уже открыто — запускаем анимацию переключения
                self._load_current_panel()
            else:
                self.show_widget()  # Запускаем анимацию открытия
        except Exception as e:
            debug_logger.error(f"Ошибка при открытии настроек команд: {e}", exc_info=True)
            self.show_message(f"Ошибка при открытии настроек команд: {str(e)}", "Ошибка", "error")

    def _load_commands_panel(self):
        """Инициализация виджетов настроек с SVG на вкладках"""
        if not hasattr(self, 'mutable_layout') or self.mutable_layout is None:
            return
        self.svg_settings_list = []
        self._clear_mutable_panel()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("CommandsTabs")
        self.tabs.setDocumentMode(True)

        self.tab_bar = self.tabs.tabBar()
        self.tab_bar.setObjectName("WSMainTabBar")

        # Создаем виджеты для содержимого вкладок
        new_com_widget = CreateCommandsWidget(self)
        added_com_widget = CommandsWidget(self)
        process_links_widget = ProcessLinksWidget(self)

        self.tabs.addTab(new_com_widget, "")
        self.tabs.addTab(added_com_widget, "")
        self.tabs.addTab(process_links_widget, "")

        tab_bar = self.tabs.tabBar()

        def create_centered_svg_tab(svg_path):
            svg = CustomSvgWidget(svg_path)
            svg.setFixedSize(30, 30)
            svg.setStyleSheet("background: transparent;")
            self.style_manager.apply_color_svg(svg, strength=0.90)
            self.svg_settings_list.append({"svg": svg})
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 0, 0, 5)
            layout.addStretch()
            layout.addWidget(svg)
            layout.addStretch()
            return container

        tab_bar.setTabButton(0, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_create_command_path))
        tab_bar.setTabButton(1, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_added_commands_path))
        tab_bar.setTabButton(2, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_process_link_path))

        self.tabs.setTabToolTip(0, "Создание новых команд")
        self.tabs.setTabToolTip(1, "Список ваших команд")
        self.tabs.setTabToolTip(2, "Процессы ярлыков")

        self.mutable_layout.addWidget(self.tabs)
        self.mutable_layout.addSpacerItem(QSpacerItem(self._get_panel_width() + 30, 1, QSizePolicy.Policy.Fixed,
                                                      QSizePolicy.Policy.Fixed))

    def other_options(self):
        """Открывает встроенную панель 'Прочее'"""
        try:
            if self.mutable_panel.isVisible() and hasattr(self, '_current_panel') and self._current_panel == 'other':
                self.hide_widget()
                return

            self._current_panel = 'other'

            if self.mutable_panel.isVisible():
                self._load_current_panel()
            else:
                self.show_widget()

        except Exception as e:
            debug_logger.error(f"Ошибка при открытии раздела 'Прочее': {e}")
            self.show_message("Ошибка при открытии 'Прочее'", "Ошибка", "error")

    def _load_other_panel(self):
        """Инициализация виджетов настроек (вызывается один раз)"""
        if not hasattr(self, 'mutable_layout') or self.mutable_layout is None:
            return

        self._clear_mutable_panel()

        # Создаём вкладки
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.svg_others_list = []

        self.tab_bar = self.tabs.tabBar()
        self.tab_bar.setObjectName("WSMainTabBar")

        # Добавляем вкладки
        self.tabs.addTab(CensorCounterWidget(self), "")
        self.tabs.addTab(CheckUpdateWidget(self), "")
        self.tabs.addTab(DebugLoggerWidget(self), "")
        self.tabs.addTab(RelaxWidget(self), "")

        # Добавляем вкладку для открытия папки
        folder_tab = QWidget()
        self.tabs.addTab(folder_tab, "")

        tab_bar = self.tabs.tabBar()

        def create_centered_svg_tab(svg_path):
            svg = CustomSvgWidget(svg_path)
            svg.setFixedSize(30, 30)
            svg.setStyleSheet("background: transparent;")
            self.style_manager.apply_color_svg(svg, strength=0.90)
            self.svg_others_list.append({"svg": svg})
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 0, 0, 5)
            layout.addStretch()
            layout.addWidget(svg)
            layout.addStretch()
            return container

        tab_bar.setTabButton(0, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_censor_path))
        tab_bar.setTabButton(1, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_updates_path))
        tab_bar.setTabButton(2, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_logs_path))
        tab_bar.setTabButton(3, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_relax_path))
        tab_bar.setTabButton(4, QTabBar.ButtonPosition.LeftSide, create_centered_svg_tab(self.icon_screenshot_path))

        self.tabs.setTabToolTip(0, "Счетчик цензуры")
        self.tabs.setTabToolTip(1, "Обновления")
        self.tabs.setTabToolTip(2, "Подробные логи")
        self.tabs.setTabToolTip(3, "Релакс?")
        self.tabs.setTabToolTip(4, "Папка скриншотов")

        # Обработчик переключения вкладок
        def on_tab_changed(index):
            if index == 4:  # Если выбрана вкладка "Папка скриншотов"
                self.open_folder_screenshots()
                self.tabs.setCurrentIndex(0)

        self.tabs.currentChanged.connect(on_tab_changed)

        # Добавляем в layout
        self.mutable_layout.addWidget(self.tabs)
        self.spacer = QSpacerItem(self._get_panel_width(), 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.mutable_layout.addSpacerItem(self.spacer)

    def guide_options(self):
        """Открывает панель гайдов"""
        try:
            if self.mutable_panel.isVisible() and self._current_panel == 'guide':
                self.hide_widget()
                return

            self._current_panel = 'guide'

            if self.mutable_panel.isVisible():
                self._load_current_panel()
            else:
                self.show_widget()

        except Exception as e:
            debug_logger.error(f"Ошибка при открытии гайдов: {e}")
            self.show_message("Ошибка", "error")

    def _load_guide_panel(self):
        """Загружает интерфейс гайдов в mutable_panel"""
        self._clear_mutable_panel()
        self._current_panel = 'guide'  # Флаг для отслеживания

        self.main = QWidget()
        self.main_layout = QVBoxLayout(self.main)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        self.spacer = QSpacerItem(self._get_panel_width(), 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.main_layout.addSpacerItem(self.spacer)
        # Заголовок
        label = QLabel("🎥 Обучение")
        label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px; background: transparent;")
        self.main_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кнопки для видео
        path_guides = get_path("bin", "guides")
        videos = [
            ("Создание команд", f"{path_guides}/new_commands.mp4"),
            ("Настройки и опции", f"{path_guides}/settings.mp4"),
        ]

        for title, video_path in videos:
            btn = QPushButton(title)
            btn.clicked.connect(lambda _, p=video_path: self._open_video(p))
            self.main_layout.addWidget(btn)

        # Кнопка "Встроенные команды"
        cmd_btn = QPushButton("Встроенные команды")
        cmd_btn.clicked.connect(self._load_commands_info)
        self.main_layout.addWidget(cmd_btn)
        self.mutable_layout.addWidget(self.main)

    def _open_video(self, video_path):
        full_path = get_path(video_path)
        if os.path.exists(full_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))
        else:
            debug_logger.error(f"Видео не найдено: {full_path}")
            self.show_message("Видео не найдено", "Ошибка", "error")

    def _load_commands_info(self):
        self._clear_mutable_panel()
        self._current_panel = 'commands'

        sections = [
            ("Формула команды",
             "'Имя ассистента'\n+\n'открой, включи'/'закрой выключи'\n+\n'команда, созданная вручную или из списка "
             "встроенных'"),
            ("Встроенные команды (открыть/закрыть)",
             "'Пейнт', 'Калькулятор', 'Корзина', 'Ап Дата', 'Переменные окружения', 'Диспетчер задач', 'Микшер',"
             "'Панель(для вызова виджета)', 'Микро'"),
            ("Прочие команды",
             "'Выключи комп', 'Перезагрузи комп', 'Найди, поищи, загугли', 'Скрин, область', 'Фулл скрин, сфоткай, "
             "весь экран'"),
            ("Управление плеером без произношения имени бота", "(Плеер) + (Действие)\n\n" +
             "Пауза, врубай, включи, запусти\n" +
             "Стоп, выключи, отключи, останови\n" +
             "Следующий, дальше, вперед\n" +
             "Предыдущий, назад"),
        ]

        for title, text in sections:
            lbl_title = QLabel(f"<b>{title}</b>")
            lbl_title.setStyleSheet("background: transparent;")
            lbl_text = QLabel(text)
            lbl_text.setWordWrap(True)
            lbl_text.setStyleSheet("margin-left: 10px; margin-bottom: 10px; font-size: 13px; background: transparent;")
            self.mutable_layout.addWidget(lbl_title)
            self.mutable_layout.addWidget(lbl_text)

        back_btn = QPushButton("Назад к гайдам")
        back_btn.clicked.connect(self._load_guide_panel)
        self.mutable_layout.addWidget(back_btn)

    def changelog_window(self, event):
        """Открываем окно с логами изменений"""
        dialog = ChangelogWindow(self)
        dialog.exec()

    def update_app(self, type_version=None, batch_update=False):
        """Обработка нажатия кнопки 'Установить обновление'"""
        debug_logger.info(f"Вызвано создание update_app c флагами type_version {type_version}, batch_update {batch_update}")
        dialog = UpdateApp(self, type_version, batch_update)
        dialog.main()

    def update_voice(self, new_voice):
        """Обновление голоса и путей к аудиофайлам"""
        self.speaker = new_voice
        self.audio_paths = get_audio_paths(self.speaker)  # Обновляем пути к аудиофайлам
        logger.info(f"Голос изменен на: {new_voice}")
        debug_logger.info(f"Голос изменен на: {new_voice}")

    def clear_logs(self):
        """Очистка файла логов и текстового поля"""
        log_file_path = get_path('assistant.log')  # Используем правильный путь к логам
        try:
            with open(log_file_path, 'w', encoding='utf-8') as file:
                file.write("")  # Записываем пустую строку
            self.log_area.clear()
            self.last_position = 0  # Сбрасываем позицию последнего прочитанного байта
        except Exception as e:
            self.log_area.append(f"Ошибка при очистке логов: {e}")

    def check_start_win(self):
        """Переключает состояние и меняет цвет иконки"""
        if self.toggle_start:
            self.update_svg_color(self.start_svg, self.color_path)
        else:
            self.update_svg_contrast_color(self.start_svg)

    def check_start_widget(self):
        if self.is_widget:
            self.open_widget(is_auto_start=True)

    def toggle_start_win(self):
        """Переключает состояние и меняет цвет иконки"""
        self.toggle_start = not self.toggle_start

        if self.toggle_start:
            self.add_to_autostart()
            self.update_svg_color(self.start_svg, self.color_path)
        else:
            self.remove_from_autostart()
            self.update_svg_contrast_color(self.start_svg)

    def update_svg_color(self, svg_widget: CustomSvgWidget, style_file: str) -> None:
        """Обновляет цвет SVG, учитывая градиенты и контрастность"""
        svg_template = '''<?xml version="1.0" encoding="utf-8"?>
        <svg fill="{color}" width="20px" height="20px" viewBox="0 0 24 24"
             xmlns="http://www.w3.org/2000/svg">
            <path d="m9.84 12.663v9.39l-9.84-1.356v-8.034zm0-10.72v9.505h-9.84v-8.145zm14.16 
            10.72v11.337l-13.082-1.803v-9.534zm0-12.663v11.452h-13.082v-9.649z"/>
        </svg>'''

        def extract_primary_color(color_value: str) -> str:
            """Извлекает основной цвет (первый цвет градиента или HEX)"""
            if not color_value:
                return "#FFFFFF"

            # Ищем градиент
            gradient_match = re.search(r"qlineargradient\([^)]+stop:0\s+(#[0-9a-fA-F]+)", color_value)
            if gradient_match:
                return gradient_match.group(1)

            # Ищем обычный HEX-цвет
            hex_match = re.search(r"#[0-9a-fA-F]{3,6}", color_value)
            return hex_match.group(0) if hex_match else "#FFFFFF"

        try:
            # 1. Загружаем стили
            with open(style_file) as f:
                styles = json.load(f)

            # 2. Извлекаем цвета с поддержкой градиентов
            border_color = extract_primary_color(
                styles.get("TitleBar", {}).get("border-bottom", "")
            )

            bg_color = extract_primary_color(
                styles.get("QWidget", {}).get("background-color", "")
            )
            base_bg_color = QColor(bg_color)

            # 3. Вычисляем яркость фона (формула восприятия яркости)
            brightness = (0.299 * base_bg_color.red() +
                          0.587 * base_bg_color.green() +
                          0.114 * base_bg_color.blue()) / 255

            # 4. Выбираем контрастный цвет
            final_color = "#369EFF" if brightness > 0.5 else border_color

            # 5. Генерируем SVG с новым цветом
            svg_widget.load(svg_template.format(color=final_color).encode('utf-8'))

        except Exception as e:
            logger.error(f"Ошибка при обновлении цвета SVG: {e}")
            debug_logger.error(f"Ошибка при обновлении цвета SVG: {e}")
            # Fallback на белый цвет при ошибке
            svg_widget.load(svg_template.format(color="#FFFFFF").encode('utf-8'))

    def update_svg_contrast_color(self, svg_widget: CustomSvgWidget) -> None:
        """Автоматически устанавливает контрастный цвет для SVG"""
        # 1. Определяем цвет фона основного окна
        bg_color = self.central_widget.palette().window().color()

        # 2. Вычисляем яркость фона (формула восприятия яркости)
        brightness = (0.299 * bg_color.red() +
                      0.587 * bg_color.green() +
                      0.114 * bg_color.blue()) / 255

        # 3. Выбираем контрастный цвет
        contrast_color = "#545454" if brightness > 0.5 else "#FFFFFF"

        # 4. Обновляем SVG
        try:
            svg_template = '''<?xml version="1.0" encoding="utf-8"?>
                        <svg fill="{color}" width="20px" height="20px" viewBox="0 0 24 24"
                             xmlns="http://www.w3.org/2000/svg">
                            <path d="m9.84 12.663v9.39l-9.84-1.356v-8.034zm0-10.72v9.505h-9.84v-8.145zm14.16 
                            10.72v11.337l-13.082-1.803v-9.534zm0-12.663v11.452h-13.082v-9.649z"/>
                        </svg>'''
            colored_svg = svg_template.format(color=contrast_color)
            svg_widget.load(bytes(colored_svg, 'utf-8'))
        except Exception as e:
            # Fallback - используем эффект цвета
            effect = QGraphicsColorizeEffect()
            effect.setColor(QColor(contrast_color))
            svg_widget.setGraphicsEffect(effect)

    def add_to_autostart(self):
        """Добавление программы в автозапуск через планировщик задач"""
        current_directory = get_path()
        write_directory = os.path.dirname(current_directory)

        # Базовые имена задач
        task_name_base = "VirtualAssistant"

        # Определяем тип запуска и пути
        if getattr(sys, 'frozen', False):
            # Запуск как EXE
            task_name = task_name_base
            target_path = os.path.join(write_directory, 'Assistant.exe')
        else:
            # Запуск как скрипт Python
            task_name = f"{task_name_base}-script"
            bat_path = os.path.join(current_directory, 'start_assistant.bat')

            # Создаем BAT-файл если его нет
            if not os.path.isfile(bat_path):
                try:
                    with open(bat_path, 'w', encoding='utf-8') as bat_file:
                        bat_file.write(f'@echo off\npython "{os.path.abspath(__file__)}"')
                    debug_logger.info(f"Создан .bat файл: {bat_path}")
                except Exception as e:
                    debug_logger.error(f"Ошибка при создании .bat файла: {e}")
                    return

            target_path = bat_path

        logger.info(f"Путь для планировщика: {target_path}")
        debug_logger.debug(f"Путь для планировщика: {target_path}")

        # Проверка наличия файла
        if not os.path.isfile(target_path):
            error_msg = f"Ошибка: Файл '{target_path}' не найден."
            logger.error(error_msg)
            debug_logger.error(error_msg)
            return

        # Команда для создания задачи в планировщике
        command = [
            'schtasks',
            '/create',
            '/tn', task_name,
            '/tr', f'"{target_path}"',  # Путь в кавычках для поддержки пробелов
            '/sc', 'onlogon',
            '/rl', 'highest',
            '/f'
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )

            success_msg = f"Программа добавлена в автозапуск"
            logger.info(success_msg)
            debug_logger.info(success_msg)
            self.show_notification_message(message=f"Программа добавлена в автозапуск")

        except subprocess.CalledProcessError as e:
            error_msg = f"Ошибка при добавлении в автозапуск: {e.stderr}"
            logger.error(error_msg)
            debug_logger.error(error_msg)

    def remove_from_autostart(self):
        """Удаление программы из автозапуска через планировщик задач"""
        # Определяем имя задачи в зависимости от типа запуска
        if getattr(sys, 'frozen', False):
            task_name = "VirtualAssistant"  # Для EXE-версии
        else:
            task_name = "VirtualAssistant-script"  # Для Python-скрипта

        command = [
            'schtasks',
            '/delete',
            '/tn', task_name,
            '/f'
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )
            success_msg = f"Задача '{task_name}' удалена из автозапуска"
            debug_logger.info(success_msg)
            self.show_notification_message(message=f"Программа удалена из автозапуска")
        except subprocess.CalledProcessError as e:
            if "не существует" not in e.stderr:
                error_msg = f"Ошибка при удалении задачи '{task_name}': {e.stderr}"
                self.show_notification_message(message=f"{error_msg}")
                debug_logger.error(error_msg)
            else:
                debug_logger.info(f"Задача '{task_name}' не найдена в планировщике")

    def check_autostart(self):
        """Проверка, добавлена ли программа в автозапуск"""
        # Определяем имя задачи в зависимости от типа запуска
        if getattr(sys, 'frozen', False):
            task_name = "VirtualAssistant"  # Для EXE-версии
        else:
            task_name = "VirtualAssistant-script"  # Для Python-скрипта

        command = ['schtasks', '/query', '/tn', task_name]

        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
                encoding='cp866'
            )
            debug_logger.info(f"Найдена задача автозапуска: '{task_name}'")
            self.toggle_start = True
        except subprocess.CalledProcessError as e:
            if "не существует" not in e.stderr:
                error_msg = f"Ошибка при проверке задачи '{task_name}': {e.stderr}"
                logger.error(error_msg)
                debug_logger.error(error_msg)
            self.toggle_start = False
            debug_logger.info(f"Задача '{task_name}' не найдена в планировщике")

    def capture_area(self):
        try:
            self.screenshot_tool.capture_area()
        except Exception as e:
            logger.error(f'Ошибка {e}')
            debug_logger.error(f'Ошибка {e}')

    def capture_fullscreen(self):
        try:
            self.screenshot_tool.capture_fullscreen()
            thread_play_sound(type_sound="ok")
        except Exception as e:
            thread_play_sound(type_sound="error")
            logger.error(f'Ошибка {e}')
            debug_logger.error(f'Ошибка {e}')


class UpdateApp(QDialog):
    def __init__(self, parent=None, type_version="stable", batch_update=False):
        super().__init__(parent)
        self.assistant = parent
        self.batch = batch_update
        self.type_version = type_version
        self.extract_dir = get_path("update_pack")
        os.makedirs(self.extract_dir, exist_ok=True)

    def main(self):
        if not self.batch:
            self.update_file_path = self.find_update_file()
            if not self.update_file_path:
                debug_logger.error("Не найден файл обновления (*.zip)")
                return

            if not self.extract_archive(self.update_file_path):
                self.assistant.show_notification_message("Не удалось распаковать архив с новой версией")
                return
            debug_logger.info(f"Архив с новой версией распакован по пути {self.extract_dir}")
        self.assistant.show_notification_message("Начинаю установку...")
        QTimer.singleShot(800, lambda: self.start_update())

    def start_update(self):
        try:
            if not self.batch:
                # флаг no-checked для пропуска проверки новой версии в апдейте
                subprocess.Popen([get_path("Update.exe"), "--no-checked"], shell=True)
                debug_logger.info("Update.exe успешно запущен с флагом --no-checked")
            else:
                # flag --batch-update for package update
                subprocess.Popen([get_path("Update.exe"), "--batch-update"], shell=True)
                debug_logger.info("Update.exe успешно запущен с флагом --batch-update")
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске Update.exe: {e}")

    def find_update_file(self):
        update_dir = get_path("update")
        pattern = f"{self.type_version}_Assistant_*.zip"
        # Ищем самый свежий файл по дате изменения
        files = []
        for file in os.listdir(update_dir):
            if file.lower().startswith(self.type_version.lower()) and file.lower().endswith('.zip'):
                file_path = os.path.join(update_dir, file)
                files.append((file_path, os.path.getmtime(file_path)))

        if files:
            # Сортируем по дате изменения (новые сначала)
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
        return None

    def extract_archive(self, archive_path):
        """Безопасная распаковка архива с обработкой кодировок"""
        try:
            # Очищаем папку перед распаковкой
            for item in os.listdir(self.extract_dir):
                item_path = os.path.join(self.extract_dir, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                else:
                    shutil.rmtree(item_path)

            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Безопасное извлечение имени файла
                    file_name = self._safe_decode_filename(file_info.filename)

                    # Защита от Zip Slip
                    target_path = os.path.join(self.extract_dir, file_name)
                    if not os.path.abspath(target_path).startswith(os.path.abspath(self.extract_dir)):
                        raise ValueError(f"Попытка распаковки вне целевой папки: {file_name}")

                    # Создаем папки если нужно
                    if file_name.endswith('/'):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as f:
                            f.write(zip_ref.read(file_info))
            return True

        except Exception as e:
            debug_logger.error(f"Ошибка распаковки: {str(e)}", exc_info=True)
            self.assistant.show_message(f"Ошибка распаковки: {str(e)}", "Ошибка", "error")
            return False

    def _safe_decode_filename(self, filename):
        """Безопасное декодирование имени файла из архива с поддержкой русского"""
        # Список кодировок для попытки декодирования (в порядке приоритета)
        encodings = [
            'cp866',  # DOS/Windows Russian
            'cp1251',  # Windows Cyrillic
            'utf-8',  # Unicode
            'cp437',  # DOS English
            'iso-8859-1',  # Latin-1
            'koi8-r'  # Russian KOI8-R
        ]

        # Сначала пробуем стандартное декодирование (для современных ZIP)
        try:
            return filename.encode('cp437').decode('utf-8')
        except UnicodeError:
            pass

        # Если не получилось, пробуем все кодировки по очереди
        for enc in encodings:
            try:
                return filename.encode('cp437').decode(enc)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

        # Если ничего не помогло, возвращаем как есть и логируем проблему
        debug_logger.warning(f"Не удалось декодировать имя файла: {filename}")
        return filename


class ChangelogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(700, 600)

        # Основной контейнер с рамкой
        container = QWidget(self)
        container.setObjectName("WindowContainer")
        container.setGeometry(0, 0, self.width(), self.height())

        # Заголовок с крестиком
        title_bar = QWidget(container)
        title_bar.setObjectName("TitleBar")
        title_bar.setGeometry(1, 1, self.width() - 2, 35)

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        title_layout.setSpacing(5)

        link_label = QLabel()
        link_label.setText('''
            <a href="https://owl-app.ru" 
            style="color: white;">
            owl-app.ru
            </a>
        ''')
        link_label.setStyleSheet("background: transparent;")
        link_label.setOpenExternalLinks(True)
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        title_layout.addWidget(link_label)
        title_layout.addStretch()
        
        title_label = QLabel("История изменений")
        title_label.setStyleSheet("background: transparent;")
        title_label.setObjectName("TitleLabel")
        title_label.setFixedSize(150, 20)
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        close_btn = QPushButton("")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(25, 25)
        close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.assistant.icon_close_path, close_btn)
        self.close_svg.setFixedSize(19, 19)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        title_layout.addWidget(close_btn)

        # Основное содержимое
        content_widget = QWidget(container)
        content_widget.setObjectName("ContentWidget")
        content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)

        # Вертикальный layout
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Текстовый браузер
        self.text_browser = QTextBrowser()
        self.text_browser.setStyleSheet("background: transparent;")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setReadOnly(True)
        layout.addWidget(self.text_browser)

        # Стили для Markdown
        self.text_browser.document().setDefaultStyleSheet("""
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                padding: 15px;
            }
            h1 {
                font-size: 24px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            h2 {
                font-size: 20px;
                margin-top: 25px;
            }
            h3 {
                font-size: 16px;
            }
            code {
                padding: 2px 5px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
            }
            pre {
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }
            blockquote {
                border-left: 4px solid #ddd;
                padding-left: 15px;
                color: #777;
                margin-left: 0;
            }
            a {
                color: #1e88e5;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            ul, ol {
                padding-left: 25px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        """)

        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.load_changelog()
        self.assistant.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#FF6666")

    def load_changelog(self):
        """Загружает и отображает Markdown файл"""
        try:
            if not hasattr(self.assistant, 'changelog_file_path'):
                self._show_error("Не указан путь к файлу изменений")
                return

            changelog_path = self.assistant.changelog_file_path

            if not os.path.exists(changelog_path):
                self._show_error(f"Файл не найден: {changelog_path}")
                return

            with open(changelog_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Конвертируем Markdown в HTML
            html = markdown2.markdown(
                md_content,
                extras=[
                    'fenced-code-blocks',  # Блоки кода ```
                    'tables',  # Таблицы
                    'footnotes',  # Сноски
                    'toc',  # Оглавление
                    'cuddled-lists',  # Компактные списки
                    'task_list',  # Списки задач
                    'spoiler'  # Скрытый текст
                ]
            )

            self.text_browser.setHtml(html)

        except Exception as e:
            self._show_error(f"Ошибка загрузки Markdown: {str(e)}")

    def _show_error(self, message):
        """Отображает сообщение об ошибке"""
        self.text_browser.setPlainText(message)


class InitScreen(QWidget):
    """
    Окно инициализации программы, проверка файлов и необходимых параметров перед основным запуском
    """
    init_complete = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth = None
        self.style_manager = ApplyColor(self)
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_path = get_path('user_settings', 'color_settings.json')
        self.svg_path = get_path("bin", "logo.svg")
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(250, 250)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(15, 0, 15, 20)
        content_layout.addStretch()

        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(120, 110)
        self.svg_image.setStyleSheet("""
                    background: transparent;
                    border: none;
                    outline: none;
                """)
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)

        content_layout.addStretch()

        self.progress = SVGProgressBar(
            svg_widget=self.svg_image,
            style="circle",
            circle_size=180,
            show_text=False,
            line_width=3)
        # self.progress = CustomProgressBar()
        content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Инициализация...", self)
        self.label.setStyleSheet("background: transparent; min-height: 35px; max-height: 35px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content_layout.addWidget(self.label)

        # Кнопка выхода при ошибке
        self.error_button = QPushButton("Закрыть программу", self)
        self.error_button.clicked.connect(self.quit_application)
        self.error_button.hide()
        content_layout.addWidget(self.error_button)

        self.setLayout(layout)
        layout.addWidget(self.main_widget, 1)

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            # Применение к SVG
            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_progressbar(key="QPushButton", widget=self.progress)

            # Применение общего стиля окна
            if hasattr(self, 'central_widget'):
                self.central_widget.setObjectName("CentralWidget")
            if hasattr(self, 'title_bar_widget'):
                self.title_bar_widget.setObjectName("TitleBar")
            # if hasattr(self, 'container'):
            #     self.title_bar_widget.setObjectName("ConfirmDialogContainer")
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
            self.main_widget.setStyleSheet("""border-radius:20px""")
        except Exception as e:
            debug_logger.error(f"Ошибка в методе apply_styles: {e}")

    def show_message(self, text, title="Уведомление", message_type="info", buttons=QMessageBox.StandardButton.Ok):
        try:
            message = SimpleNotice(
                parent=self,
                message=text,
                title=title,
                message_type=message_type,
                buttons=buttons
            )
            return message.exec_()
        except Exception as e:
            debug_logger.error(f"Ошибка при показе уведомления(оконного): {e}")
            # В случае ошибки тоже нужно что-то вернуть, например, QDialog.Rejected или None
            return QDialog.DialogCode.Rejected  # или return None

    def quit_application(self):
        """Перенаправляем запрос на закрытие в главное окно"""
        self.main_window.cleanup_before_exit()
        
    def open_login(self):
        try:
            # Закрываем текущее окно инициализации
            self.login_window = LoginWindow(auth=self.auth)
            self.login_window.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.login_window.show()
            
            # Подключаем сигнал завершения логина
            self.login_window.login_successful.connect(self.on_login_success)
            self.login_window.login_cancelled.connect(self.on_login_cancelled)
            
        except Exception as e:
            debug_logger.error(f"Ошибка при запуске окна авторизации: {e}")

    def on_login_success(self):
        """Обработка успешного логина"""
        if hasattr(self, 'main_window') and self.auth.user_data:
            self.main_window.set_user_data(self.auth.user_data)
        
        self.start_checks()

    def on_login_cancelled(self):
        """Обработка отмены логина"""
        debug_logger.info("❌ Логин отменен")
        self.quit_application()
        
    def check_auth(self, main_window, auth):
        self.main_window = main_window
        self.auth = auth
        # Проверяем сохраненную авторизацию
        if self.auth.is_authenticated():
            if self.auth.is_guest():
                debug_logger.info(f"✅ Автоматический вход: Гость")
            else:
                debug_logger.info(f"✅ Автоматический вход: {self.auth.user_data['username']}")
            self.main_window.set_user_data(self.auth.user_data)
            self.start_checks()
        else:
            self.open_login()

    def start_checks(self):
        self.check_thread = CheckThread()
        self.check_thread.progress_update.connect(self.update_progress)
        self.check_thread.checks_complete.connect(self.on_checks_complete)
        self.check_thread.start()

    def update_progress(self, message, value):
        self.label.setText(message)
        self.progress.setValue(value)
        QApplication.processEvents()  # Обновляем интерфейс

    def on_checks_complete(self, result, missing_file="", error=""):
        if result:
            self.progress.setValue(100)
            QTimer.singleShot(1000, lambda: self.finalize_initialization(True))
        else:
            if hasattr(self, 'main_window'):
                self.main_window.clear_user_data()
            self.label.setText(f"Произошла ошибка")
            self.progress.setValue(0)
            self.show_message(text=f"{error}", title="Ошибка", message_type="error")
            self.init_complete.emit(False)  # Отправляем сигнал об ошибке
            QTimer.singleShot(1000, lambda: self.close())

    def finalize_initialization(self, success):
        self.init_complete.emit(success)
        self.close()


class CheckThread(QThread):
    checks_complete = Signal(bool, str, str)
    progress_update = Signal(str, int)

    def run(self):
        try:
            total_steps = 100
            admin_weight = 10
            device_weight = 10
            path_weight = 10
            files_weight = 70

            self.progress_update.emit("Проверка прав администратора...", 0)
            if not self.check_admin():
                self.progress_update.emit("Ошибка: Нет прав администратора!", 0)
                self.checks_complete.emit(False, "", "Ошибка: Нет прав администратора!")
                return
            for i in range(admin_weight):
                QThread.msleep(5)  # имитация долгой проверки
                self.progress_update.emit("Проверка прав администратора...", i + 1)

            if not self.check_audio_devices(device_weight):
                return

            if self.check_main_path(get_path(), path_weight):
                self.checks_complete.emit(False, "", "Ошибка: В пути обнаружена кириллица!")
                return

            files_ok = self.check_main_files(files_weight)
            if not files_ok:
                return

            self.progress_update.emit("Запуск...", 100)
            self.checks_complete.emit(True, "", "")
        except Exception as e:
            self.progress_update.emit(f"Критическая ошибка: {str(e)}", 0)
            self.checks_complete.emit(False, "", "")

    # noinspection PyUnresolvedReferences
    def check_admin(self):
        """Проверка прав администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def check_main_files(self, files_weight):
        files_to_check = (
            "apply_color_methods.py", "audio_control.py", "check_update.py", "choose_color_window.py",
            "commands_widgets.py", "custom_svg_widget.py", "download_thread.py", "function_list_main.py",
            "lists.py", "other_options_widgets.py", "progress_bar_widget.py",  "register_module.py",
            "screenshot_tool.py", "settings_widgets.py", "signals.py", "speak_functions.py", "toast_notification.py",
            "toggle_mute_discord.py", "utils.py", "widget_window.py")

        total_files = len(files_to_check)
        step_per_file = files_weight / total_files if total_files else 0

        for i, file in enumerate(files_to_check):
            path = get_path("bin", file)
            if not os.path.exists(path):
                self.progress_update.emit(f"Файл {file} не найден!", 0)
                self.checks_complete.emit(False, "", f"Файл {file} не найден!")  # Добавляем имя файла в сигнал
                return False

            progress = int((i + 1) * step_per_file) + 20
            self.progress_update.emit(f"Проверка {file}...", progress)
            QThread.msleep(5)  # Имитация работы

        return True

    def check_main_path(self, path, path_weight):
        self.progress_update.emit("Проверяю путь до исполняемого файла...", 21)
        for i in range(path_weight):
            QThread.msleep(5)  # имитация долгой проверки
            self.progress_update.emit("Проверяю путь до исполняемого файла...", 29)
        cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]')
        return bool(cyrillic_pattern.search(path))

    def input_device(self, device_weight):
        p = pyaudio.PyAudio()

        self.progress_update.emit("Ищу устройства ввода-вывода...", 10)
        for i in range(device_weight):
            QThread.msleep(5)  # имитация долгой проверки
            self.progress_update.emit("Ищу устройства ввода-вывода...", 14)

            try:
                default_input_device = p.get_default_input_device_info()
                return True
            except IOError:
                self.progress_update.emit("Ошибка: Нет устройств ввода звука.", 10)
                self.checks_complete.emit(False, "", "Ошибка: Нет устройств ввода звука")
                return False

    def output_device(self, device_weight):
        p = pyaudio.PyAudio()

        self.progress_update.emit("Ищу устройства ввода-вывода...", 15)
        for i in range(device_weight):
            QThread.msleep(5)  # имитация долгой проверки
            self.progress_update.emit("Ищу устройства ввода-вывода...", 19)
        try:
            default_output_device = p.get_default_output_device_info()
            return True
        except IOError:
            self.progress_update.emit("Ошибка: Нет устройств вывода звука.", 10)
            self.checks_complete.emit(False, "", "Ошибка: Нет устройств вывода звука")
            return False
        finally:
            p.terminate()

    def check_audio_devices(self, device_weight):
        if not self.input_device(device_weight) or not self.output_device(device_weight):
            return False

        self.progress_update.emit("Аудиоустройства проверены.", 20)
        return True
    
    
class LoginWindow(QWidget):
    """
    Окно регистрации и авторизации в системе
    """
    # Добавляем сигналы
    login_successful = Signal()
    login_cancelled = Signal()

    def __init__(self, parent=None, auth=None):
        super().__init__(parent)
        self.auth = auth
        if not self.auth:
            self.auth = AuthManager(domain)
        self.style_manager = ApplyColor(self)
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_path = get_path('user_settings', 'color_settings.json')
        self.svg_path = get_path("bin", "logo.svg")
        self.is_login_mode = False
        self.is_2fa_mode = False
        self.init_ui()
        self.apply_styles()
        self.switch_mode()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(350, 660)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        
        # Основной layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(10)
        
        # Добавляем логотип
        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(80, 80)
        self.svg_image.setStyleSheet("background: transparent; border: none;")
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addSpacing(20)

        # Заголовок окна (будет меняться)
        self.title_label = QLabel("Создание аккаунта")
        self.title_label.setStyleSheet("""
            background: transparent; 
            font-size: 18px; 
            font-weight: bold;
            margin-bottom: 10px;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.title_label)
        
        content_layout.addSpacing(10)
        
        self.notice_widget = QWidget()
        self.notice_widget.setObjectName("NoticeWidget")
        self.notice_widget.setFixedHeight(60)
        self.notice_widget.show()
        
        notice_layout = QHBoxLayout(self.notice_widget)
        notice_layout.setContentsMargins(15, 10, 15, 10)
        
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color: white; font-size: 14px; background: transparent;")
        notice_layout.addWidget(self.notice_label)
        
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: transparent;
                border: none;
            }
        """)
        
        content_layout.addWidget(self.notice_widget)

        # Поля формы
        self.label_username = QLabel("Логин")
        self.label_username.setStyleSheet("background: transparent;")
        self.field_username = QLineEdit()
        self.field_username.setStyleSheet("background: transparent;")
        self.field_username.setPlaceholderText("Введите логин")
        content_layout.addWidget(self.label_username, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.field_username)
        
        # Поле email (будет скрыто в режиме авторизации)
        self.label_email = QLabel("Почта")
        self.label_email.setStyleSheet("background: transparent;")
        self.field_email = QLineEdit()
        self.field_email.setStyleSheet("background: transparent;")
        self.field_email.setPlaceholderText("Введите email")
        content_layout.addWidget(self.label_email, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.field_email)
        
        self.label_password = QLabel("Пароль")
        self.label_password.setStyleSheet("background: transparent;")
        self.password_container = self.create_password_field("Введите пароль")
        self.password_container.setStyleSheet("background: transparent;")
        content_layout.addWidget(self.label_password, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.password_container)
        
        # Поле повторения пароля (будет скрыто в режиме авторизации)
        self.label_2password = QLabel("Повторите пароль")
        self.label_2password.setStyleSheet("background: transparent;")
        self.password2_container  = self.create_password_field("Повторите пароль")
        self.password2_container .setStyleSheet("background: transparent;")
        content_layout.addWidget(self.label_2password, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.password2_container )
        
        self.label_2fa = QLabel("Код двухфакторной аутентификации")
        self.label_2fa.setStyleSheet("background: transparent; font-weight: bold;")
        self.field_2fa = QLineEdit()
        self.field_2fa.setStyleSheet("background: transparent;")
        self.field_2fa.setPlaceholderText("Введите 6-значный код с почты")
        self.field_2fa.setMaxLength(6)
        
        self.resend_2fa_btn = QPushButton("Отправить код повторно")
        self.resend_2fa_btn.clicked.connect(self.resend_2fa_code)
        self.resend_2fa_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        
        # Скрываем 2FA поля изначально
        self.hide_2fa_fields()
        
        content_layout.addWidget(self.label_2fa)
        content_layout.addWidget(self.field_2fa)
        content_layout.addWidget(self.resend_2fa_btn)
        
        content_layout.addSpacing(20)
        
        # Кнопки
        self.submit_btn = QPushButton("Создать аккаунт")
        self.submit_btn.clicked.connect(self.handle_submit)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel_login)
        
        self.back_btn = QPushButton("Назад")  # ← Новая кнопка "Назад" для 2FA
        self.back_btn.clicked.connect(self.back_to_login)
        self.back_btn.hide()
        
        self.local_launch_btn = QPushButton("Локальный запуск (Гость)")
        self.local_launch_btn.clicked.connect(self.login_as_guest)
        self.local_launch_btn.hide()
        
        # Layout для кнопок
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.submit_btn)
        
        content_layout.addLayout(buttons_layout)
        content_layout.addWidget(self.back_btn)
        content_layout.addWidget(self.local_launch_btn)
        
        # Текст-ссылка для переключения между режимами
        self.switch_mode_label = QLabel(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Уже есть аккаунт? <a href='login'>Войти</a>"
        )
        self.switch_mode_label.setStyleSheet("background: transparent; margin-top: 10px;")
        self.switch_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.switch_mode_label.setOpenExternalLinks(False)
        self.switch_mode_label.linkActivated.connect(self.switch_mode)
        content_layout.addWidget(self.switch_mode_label)
        
        link_label = QLabel()
        link_label.setText('''
            <a href="https://owl-app.ru" 
            style="color: #1E88E5; text-decoration: none; font-size: 13px;">
            owl-app.ru
            </a>
        ''')
        link_label.setStyleSheet("background: transparent;")
        link_label.setOpenExternalLinks(True)
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        content_layout.addWidget(link_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addStretch()

        # Добавляем основной виджет в главный layout
        main_layout.addWidget(self.main_widget, 1)
        
    def login_as_guest(self):
        """Вход в режиме гостя"""
        debug_logger.info("👤 Вход как гость")

        # Создаем гостевые данные
        guest_data = {
            'id': -1,
            'username': 'Username',
            'display_name': 'Username',
            'email_verified': False,
            'avatar': None
        }
        
        # Устанавливаем гостевой режим в AuthManager
        self.auth.user_data = guest_data
        self.auth.token = None  # Нет токена для гостя
        
        # Сохраняем информацию о гостевом режиме
        self.auth._save_auth_data()
        
        # Показываем сообщение
        self.show_message("Локальный запуск", "info")
        
        # Закрываем окно и отправляем сигнал
        QTimer.singleShot(1000, self.finish_guest_login)
        
    def hide_2fa_fields(self):
        """Скрыть поля 2FA"""
        self.label_2fa.hide()
        self.field_2fa.hide()
        self.resend_2fa_btn.hide()

    def show_2fa_fields(self):
        """Показать поля 2FA"""
        self.label_2fa.show()
        self.field_2fa.show()
        self.resend_2fa_btn.show()

    def switch_to_2fa_mode(self):
        """Переключиться в режим 2FA"""
        self.is_2fa_mode = True
        
        # Скрываем основные поля
        self.label_username.hide()
        self.field_username.hide()
        self.label_email.hide()
        self.field_email.hide()
        self.label_password.hide()
        self.password_container.hide()
        self.label_2password.hide()
        self.password2_container.hide()
        self.local_launch_btn.hide()
        self.switch_mode_label.hide()
        
        # Показываем 2FA поля
        self.show_2fa_fields()
        
        # Обновляем кнопки
        self.title_label.setText("Аутентификация")
        self.submit_btn.setText("Подтвердить")
        self.cancel_btn.hide()
        self.back_btn.show()
        
        # Обновляем сообщение
        self.show_message("Код отправлен на вашу почту", "info")

    def back_to_login(self):
        """Вернуться к обычному логину"""
        self.is_2fa_mode = False
        
        # Скрываем 2FA поля
        self.hide_2fa_fields()
        
        self.title_label.setText("Вход в аккаунт")
        self.label_email.show()
        self.field_email.show()
        self.label_password.show()
        self.password_container.show()
            
        # Обновляем кнопки
        self.back_btn.hide()
        self.cancel_btn.show()
        self.local_launch_btn.show()
        self.switch_mode_label.show()
        self.setFixedSize(350, 560)

    def handle_submit(self):
        """Обработка отправки формы"""
        try:
            if self.is_2fa_mode:
                self.handle_2fa_verification()
            elif self.is_login_mode:
                self.handle_login()
            else:
                self.handle_register()
                
        except Exception as e:
            debug_logger.error(f"Ошибка при обработке формы: {e}")
            self.show_message(f"Ошибка: {e}", "error")

    def handle_2fa_verification(self):
        """Обработка верификации 2FA кода"""
        code = self.field_2fa.text().strip()
        
        if len(code) != 6 or not code.isdigit():
            self.show_message("Введите 6-значный код", "error")
            return
            
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Проверка...")
        
        success, message = self.auth.verify_2fa(code)
        
        if success:
            self.show_message("Успешная верификация!", "info")
            self.login_successful.emit()
            self.close()
        else:
            self.show_message(f"Ошибка: {message}", "error")
            
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Подтвердить")

    def resend_2fa_code(self):
        """Повторная отправка кода 2FA"""
        if not self.auth.temp_2fa_token:
            self.show_message("Нет активной сессии 2FA", "error")
            return
        
        debug_logger.info(f"🔄 Запрос повторной отправки с токеном: {self.auth.temp_2fa_token}")
            
        self.resend_2fa_btn.setEnabled(False)
        self.resend_2fa_btn.setText("Отправка...")
        
        success, message = self.auth.resend_2fa_code()
        
        if success:
            self.show_message("✅ Код отправлен повторно!", "info")
        else:
            self.show_message(f"❌ {message}", "error")
            # Если токен невалидный, возвращаем к логину
            if "неверный" in message.lower() or "истек" in message.lower():
                self.back_to_login()
                
        self.resend_2fa_btn.setEnabled(True)
        self.resend_2fa_btn.setText("Отправить код повторно")
        
    def finish_guest_login(self):
        """Завершить вход как гость"""
        self.login_successful.emit()
        self.close()

    def switch_mode(self):
        """Переключение между режимами регистрации и авторизации"""
        self.is_login_mode = not self.is_login_mode
        
        if self.is_login_mode:
            # Переключаемся в режим авторизации
            self.title_label.setText("Вход в аккаунт")
            self.submit_btn.setText("Войти")
            self.switch_mode_label.setText(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Нет аккаунта? <a href='register'>Зарегистрироваться</a>")
            
            # Скрываем ненужные поля
            self.label_username.hide()
            self.field_username.hide()
            self.label_2password.hide()
            self.password2_container.hide()
            self.setFixedSize(350, 560)
            
            self.local_launch_btn.show()
            
        else:
            # Переключаемся в режим регистрации
            self.title_label.setText("Создание аккаунта")
            self.submit_btn.setText("Создать аккаунт")
            self.switch_mode_label.setText(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Уже есть аккаунт? <a href='login'>Войти</a>")
            
            # Показываем все поля
            self.label_username.show()
            self.field_username.show()
            self.label_2password.show()
            self.password2_container.show()
            self.setFixedSize(350, 660)
            
            self.local_launch_btn.hide()
        
        # Очищаем поля при переключении
        self.clear_fields()

    def clear_fields(self):
        """Очистка полей ввода"""
        self.field_username.clear()
        self.field_email.clear()
        self.password_container.password_field.clear()
        self.password2_container.password_field.clear()

    # def handle_submit(self):
    #     """Обработка отправки формы (регистрация или авторизация)"""
    #     try:
    #         if self.is_login_mode:
    #             self.handle_login()
    #         else:
    #             self.handle_register()
                
    #     except Exception as e:
    #         debug_logger.error(f"Ошибка при обработке формы: {e}")
    #         self.show_message(f"Ошибка: {e}", "error")

    def handle_register(self):
        """Обработка регистрации"""
        username = self.field_username.text().strip()
        email = self.field_email.text().strip()
        password = self.password_container.password_field.text()
        password_confirm = self.password2_container.password_field.text()

        # Валидация
        if not username:
            self.show_message("Введите логин", "error")
            return

        if not email or "@" not in email:
            self.show_message("Введите корректный email", "error")
            return

        if not password:
            self.show_message("Введите пароль", "error")
            return

        if len(password) < 6:
            self.show_message("Пароль должен содержать минимум 6 символов", "error")
            return

        if password != password_confirm:
            self.show_message("Пароли не совпадают", "error")
            return

        # Блокируем кнопку
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Регистрация...")

        # Регистрация через AuthManager
        success, result = self.auth.register(username, email, password)
        
        if success:
            # ⚠️ РЕГИСТРАЦИЯ УСПЕШНА - ПЕРЕКЛЮЧАЕМ НА АВТОРИЗАЦИЮ
            message = result['message'] if isinstance(result, dict) else result
            self.show_message(message, "success")
            
            # Сохраняем email для возможности повторной отправки
            self.pending_verification_email = email
            
            # Переключаемся на режим авторизации
            QTimer.singleShot(1500, self.switch_to_login_mode)
        else:
            self.show_message(f"Ошибка регистрации: {result}", "error")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Создать аккаунт")

    def switch_to_login_mode(self):
        """Переключиться на режим авторизации после регистрации"""
        self.switch_mode()
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Войти")
        
        # ⚠️ Добавляем кнопку повторной отправки письма
        self.add_resend_verification_button()
        self.setFixedSize(350, 600)

    def add_resend_verification_button(self):
        """Добавить кнопку повторной отправки письма подтверждения"""
        if hasattr(self, 'resend_btn'):
            self.resend_btn.show()
            return
            
        self.resend_btn = QPushButton("Отправить письмо подтверждения повторно")
        self.resend_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0078D7;
                border: 1px solid #0078D7;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #0078D7;
                color: white;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
                border: 1px solid #cccccc;
            }
        """)
        self.resend_btn.clicked.connect(self.resend_verification)
        
        # Добавляем кнопку в layout (перед switch_mode_label)
        content_layout = self.main_widget.layout()
        index = content_layout.indexOf(self.switch_mode_label)
        content_layout.insertWidget(index, self.resend_btn)

    def resend_verification(self):
        """Повторно отправить письмо подтверждения"""
        if not hasattr(self, 'pending_verification_email'):
            self.show_message("Email не найден", "error")
            return
            
        # Блокируем кнопку на 40 секунд
        self.resend_btn.setEnabled(False)
        self.resend_btn.setText("Отправка...")
        
        success, message = self.auth.resend_verification_email(self.pending_verification_email)
        
        if success:
            self.show_message("Письмо отправлено!", "success")
            # ⚠️ Таймер разблокировки кнопки через 40 секунд
            QTimer.singleShot(40000, self.enable_resend_button)
            
            # Обновляем счетчик на кнопке
            self.start_resend_countdown()
        else:
            self.show_message(f"Ошибка: {message}", "error")
            self.resend_btn.setEnabled(True)
            self.resend_btn.setText("Отправить письмо подтверждения повторно")

    def start_resend_countdown(self):
        """Запустить отсчет времени до возможности повторной отправки"""
        self.countdown_seconds = 40
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_resend_button)
        self.countdown_timer.start(1000)
        self.update_resend_button()

    def update_resend_button(self):
        """Обновить текст кнопки с отсчетом"""
        if self.countdown_seconds > 0:
            self.resend_btn.setText(f"Повторная отправка через {self.countdown_seconds}с")
            self.countdown_seconds -= 1
        else:
            self.countdown_timer.stop()
            self.enable_resend_button()

    def enable_resend_button(self):
        """Разблокировать кнопку повторной отправки"""
        self.resend_btn.setEnabled(True)
        self.resend_btn.setText("Отправить письмо подтверждения повторно")

    def handle_login(self):
        """Обработка авторизации"""
        try:
            email = self.field_email.text().strip()
            password = self.password_container.password_field.text()

            # Валидация
            if not self.auth.is_valid_email(email):
                self.show_message("Некорректная почта", "error")
                return
            
            if not email:
                self.show_message("Введите почту", "error")
                return

            if len(email) > 100:
                self.show_message("Email должен содержать не более 100 символов", "error")
                return

            if not password:
                self.show_message("Введите пароль", "error")
                return
            
            if len(password) < 6:
                self.show_message("Пароль должен содержать не менее 6 символов", "error")
                return

            if len(password) > 50:
                self.show_message("Пароль должен содержать не более 50 символов", "error")
                return

            debug_logger.info(f"🔄 Начинаем авторизацию для: {email}")
            
            # Блокируем кнопку на время авторизации
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("Вход...")

            # Авторизация через AuthManager
            result, message = self.auth.login(email, password)
            
            debug_logger.info(f"📊 Результат авторизации: {result}, {message}")
            
            if result == True:
                # Обычный вход без 2FA
                self.show_message("Успешный вход!", "info")
                self.login_successful.emit()
                self.close()
            elif result == '2fa_required':
                # Требуется 2FA - показываем окно верификации
                self.show_message("Требуется двухфакторная аутентификация", "info")
                debug_logger.info(f"🔐 Переход в режим 2FA с токеном: {self.auth.temp_2fa_token}")
                self.switch_to_2fa_mode()
            else:
                # Ошибка входа
                self.show_message(f"Ошибка входа: {message}", "error")

        except Exception as e:
            debug_logger.error(f"Ошибка при авторизации: {e}")
            self.show_message(f"Неожиданная ошибка: {e}", "error")
        finally:
            # Разблокируем кнопку
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Войти")

    def cancel_login(self):
        """Обработка отмены"""
        self.login_cancelled.emit()
        self.close()

    def on_2fa_success(self):
        """Обработка успешной верификации 2FA"""
        self.show_message("Успешный вход!", "info")
        self.login_successful.emit()
        self.close()

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            # Применение к SVG
            if hasattr(self, 'svg_image'):
                self.style_manager.apply_color_svg(self.svg_image, strength=0.95)

            # Применение общего стиля окна
            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):  # Для стандартных виджетов
                    selector = widget
                else:  # Для виджетов с objectName
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            # Устанавливаем стиль для текущего окна
            self.setStyleSheet(style_sheet)
            self.main_widget.setStyleSheet("border-radius: 20px;")
        except Exception as e:
            debug_logger.error(f"Ошибка в методе apply_styles: {e}")

    def cancel_login(self):
        """Обработка отмены"""
        self.login_cancelled.emit()
        self.close()

    def setup_notice_widget(self):
        """Создать виджет уведомления"""
        self.notice_widget = QWidget(self)
        self.notice_widget.setObjectName("NoticeWidget")
        self.notice_widget.setFixedSize(300, 50)
        self.notice_widget.hide()
        
        layout = QHBoxLayout(self.notice_widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.notice_label)
        
        # Позиционируем вверху
        self.notice_widget.move(25, 25)
        
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: #F44336;
                border-radius: 8px;
                border: 1px solid #D32F2F;
            }
        """)

    def show_message(self, text, message_type="error"):
        """Показать уведомление"""
        try:
            self.notice_label.setText(text)
            
            # Меняем цвет в зависимости от типа
            colors = {
                "info": "#2196F3",
                "success": "#4CAF50", 
                "warning": "#FF9800",
                "error": "#F44336"
            }
            color = colors.get(message_type, "#F44336")
            
            # Показываем с цветом
            self.notice_widget.setStyleSheet(f"""
                #NoticeWidget {{
                    background: {color};
                    border-radius: 8px;
                    border: 1px solid {color};
                }}
            """)
            
            # Через 3 секунды возвращаем прозрачный стиль
            QTimer.singleShot(3000, self.hide_notice)
            
        except Exception as e:
            debug_logger.error(f"Ошибка при показе уведомления: {e}")

    def hide_notice(self):
        """Скрыть уведомление (оставить место)"""
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: transparent;
                border: none;
            }
        """)
        self.notice_label.clear() 
        
    def create_password_field(self, placeholder):
        """Создать поле пароля с кнопкой глазком рядом"""
        # Создаем контейнер для поля и кнопки
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Поле ввода
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(placeholder)
        field.setStyleSheet("background: transparent;")
        
        # Кнопка глазок
        toggle_btn = QPushButton()
        toggle_btn.setFixedSize(33, 33)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;

            }
            QPushButton:hover {
                background: rgba(100,100,100,0.4);
            }
        """)
        
        # SVG иконка
        eye_svg_path = get_path("bin", "icons", "visible.svg")
        svg_widget = CustomSvgWidget(eye_svg_path)
        svg_widget.setFixedSize(25, 25)
        svg_widget.setStyleSheet("background: transparent; border: none;")
        
        # Эффект цвета
        color_effect = QGraphicsColorizeEffect()
        svg_widget.setGraphicsEffect(color_effect)
        self.style_manager.apply_color_svg(svg_widget, strength=0.8)
        
        # Layout для кнопки с центрированием
        btn_layout = QHBoxLayout(toggle_btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(svg_widget)
        
        # Добавляем в контейнер
        container_layout.addWidget(field)
        container_layout.addWidget(toggle_btn)
        
        # Подключаем обработчик
        toggle_btn.clicked.connect(lambda: self.toggle_password_visibility(field, toggle_btn))
        
        # Сохраняем ссылки
        container.password_field = field
        container.toggle_btn = toggle_btn
        container.svg_widget = svg_widget
        
        return container

    def toggle_password_visibility(self, field, toggle_btn):
        """Переключить видимость пароля"""
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(100,100,100,0.7);
                }
            """)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            toggle_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                }
                QPushButton:hover {
                    background: rgba(100,100,100,0.4);
                }
            """)


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
        app.setWindowIcon(QIcon(get_path('icon_assist.ico')))
        window = Assistant()
        app.exec()

    except Exception as e:
        logger.error(f"Произошла ошибка при запуске программы: {e}")
        debug_logger.error(f"Произошла ошибка при запуске программы: {e}")

# if __name__ == '__main__':
#     try:
#         if activate_existing_window():
#             sys.exit(0)
#         app = QApplication([])
#         app.setWindowIcon(QIcon(get_path('icon_assist.ico')))
#         window = Assistant()
#
#         app.exec_()
#
#     except Exception as e:
#         logger.error(f"Произошла ошибка при запуске программы: {e}")
#         debug_logger.error(f"Произошла ошибка при запуске программы: {e}")
