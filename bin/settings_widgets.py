import json
import os
import sounddevice as sd
import winshell
from PySide6.QtGui import QFontDatabase, QFont

from bin.lists import fonts_list
from bin.signals import color_signal, widget_btns_signal, update_presets_signal
from bin.speak_functions import thread_react
from bin.choose_color_window import ColorSettingsWindow
from path_builder import get_path
from logging_config import logger, debug_logger
from PySide6.QtCore import Signal, QTimer, QEvent
from PySide6.QtWidgets import QFileDialog, QLineEdit, QSlider, QComboBox, QWidget, QHBoxLayout
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QCheckBox, QApplication, QFrame, QPushButton)
from PySide6.QtCore import Qt

speakers = dict(Персик="persik", Джарвис="jarvis", Пласид='placide', Бестия='rogue',
                Джонни='johnny', СанСаныч='sanych', Санбой='sanboy', Woman='tigress', Стейтем='stathem')


class InterfaceWidget(QWidget):
    """Виджет настроек оформления интерфейса"""

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        update_presets_signal.presets_updated.connect(self.load_custom_presets)
        self.init_ui()

    style_applied = Signal(dict)  # Сигнал для передачи стиля

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("Выбор стиля интерфейса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Контейнер для двух колонок
        cols = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # Левая колонка
        btn_dark_orange = QPushButton("Оранжевый неон")
        btn_dark_orange.clicked.connect(lambda: self.apply_style_file("orange_neon.json"))
        left_col.addWidget(btn_dark_orange)

        btn_dark_blue = QPushButton("Синий неон")
        btn_dark_blue.clicked.connect(lambda: self.apply_style_file("blue_neon.json"))
        left_col.addWidget(btn_dark_blue)

        btn_dark_green = QPushButton("Зеленый неон")
        btn_dark_green.clicked.connect(lambda: self.apply_style_file("green_neon.json"))
        left_col.addWidget(btn_dark_green)

        btn_dark_purple = QPushButton("Розовый неон")
        btn_dark_purple.clicked.connect(lambda: self.apply_style_file("pink_neon.json"))
        left_col.addWidget(btn_dark_purple)

        btn_dark_red = QPushButton("Красный неон")
        btn_dark_red.clicked.connect(lambda: self.apply_style_file("red_neon.json"))
        # left_col.addWidget(btn_dark_red)

        btn_dark_blue = QPushButton("Голубой неон")
        btn_dark_blue.clicked.connect(lambda: self.apply_style_file("dark_blue.json"))
        left_col.addWidget(btn_dark_blue)

        btn_purple_neon = QPushButton("Фиолетовый неон")
        btn_purple_neon.clicked.connect(lambda: self.apply_style_file("purple_neon.json"))
        left_col.addWidget(btn_purple_neon)

        btn_ice_flame = QPushButton("Ice&Flame")
        btn_ice_flame.clicked.connect(lambda: self.apply_style_file("ice_and_flame.json"))
        # left_col.addWidget(btn_ice_flame)

        # Правая колонка
        btn_dark = QPushButton("Dark")
        btn_dark.clicked.connect(lambda: self.apply_style_file("dark.json"))
        right_col.addWidget(btn_dark)

        btn_legacy = QPushButton("Legacy")
        btn_legacy.clicked.connect(lambda: self.apply_style_file("legacy.json"))
        # right_col.addWidget(btn_legacy)

        btn_white = QPushButton("White")
        btn_white.clicked.connect(lambda: self.apply_style_file("white.json"))
        # right_col.addWidget(btn_white)

        btn_white_orange = QPushButton("Blue-Orange")
        btn_white_orange.clicked.connect(lambda: self.apply_style_file("blue_orange.json"))
        right_col.addWidget(btn_white_orange)

        btn_purple = QPushButton("MoonLight")
        btn_purple.clicked.connect(lambda: self.apply_style_file("moonlight.json"))
        right_col.addWidget(btn_purple)

        btn_pink_blue = QPushButton("Pink-Blue")
        btn_pink_blue.clicked.connect(lambda: self.apply_style_file("pink_blue.json"))
        right_col.addWidget(btn_pink_blue)

        btn_orange_purple = QPushButton("Закат")
        btn_orange_purple.clicked.connect(lambda: self.apply_style_file("sunset.json"))
        right_col.addWidget(btn_orange_purple)

        btn_mint = QPushButton("Mint")
        btn_mint.clicked.connect(lambda: self.apply_style_file("mint.json"))
        right_col.addWidget(btn_mint)

        cols.addLayout(left_col)
        cols.addLayout(right_col)
        layout.addLayout(cols)

        # Выпадающий список для кастомных стилей
        self.custom_presets_combo = QComboBox()
        self.custom_presets_combo.addItem("Выберите пользовательский стиль...")
        self.load_custom_presets()
        self.custom_presets_combo.currentIndexChanged.connect(self.apply_custom_style)

        layout.addWidget(self.custom_presets_combo)

        layout.addStretch()

        btn_default = QPushButton("Default")
        btn_default.clicked.connect(lambda: self.apply_style_file("dark.json"))
        layout.addWidget(btn_default)

        # Кнопка создания своего стиля
        create_btn = QPushButton("Создать свой стиль")
        create_btn.clicked.connect(self.open_color_settings)
        layout.addWidget(create_btn)

    def apply_style_file(self, filename):
        """Применяет стиль из указанного файла, проверяя обе директории."""
        base_presets = get_path('bin', 'color_presets')
        custom_presets = get_path('user_settings', 'presets')

        # Проверяем, в какой папке есть файл (приоритет у custom_presets)
        preset_path = None
        custom_path = os.path.join(custom_presets, filename)
        base_path = os.path.join(base_presets, filename)

        if os.path.exists(custom_path):
            preset_path = custom_path
        elif os.path.exists(base_path):
            preset_path = base_path
        else:
            logger.error(f"Пресет '{filename}' не найден ни в одной из папок.")
            debug_logger.error(f"Пресет '{filename}' не найден ни в одной из папок.")
            return

        try:
            with open(preset_path, 'r', encoding='utf-8') as json_file:
                styles = json.load(json_file)

                # Сохраняем стили в основной файл настроек
                with open(self.assistant.color_path, 'w') as f:
                    json.dump(styles, f, indent=4)

                # Применяем стили
                self.assistant.styles = styles
                self.assistant.apply_styles()
                self.assistant.check_start_win()
                color_signal.color_changed.emit()
                self.assistant.show_notification_message(message=f"Стиль успешно применен!")
                debug_logger.info(f"Применён стиль из файла: {filename}")

        except json.JSONDecodeError:
            logger.error(f"Ошибка: файл пресета повреждён ({preset_path}).")
            debug_logger.error(f"Ошибка: файл пресета повреждён ({preset_path}).")
        except Exception as e:
            logger.error(f"Ошибка загрузки пресета: {e}")
            debug_logger.error(f"Ошибка загрузки пресета: {e}")
            self.assistant.show_message(f"Ошибка загрузки пресета: {e}", "Ошибка", "error")

    def load_custom_presets(self):
        """Загружает список пользовательских пресетов в выпадающий список"""
        self.custom_presets_combo.clear()
        self.custom_presets_combo.addItem("Тут Ваши созданные стили...")

        custom_presets_dir = get_path('user_settings', 'presets')

        if os.path.exists(custom_presets_dir):
            for filename in sorted(os.listdir(custom_presets_dir)):
                if filename.endswith('.json'):
                    preset_name = filename[:-5]  # Убираем расширение .json
                    self.custom_presets_combo.addItem(preset_name)

    def apply_custom_style(self, index):
        """Применяет выбранный пользовательский стиль"""
        if index == 0:  # Первый элемент - заглушка
            return

        preset_name = self.custom_presets_combo.currentText()
        if preset_name:
            # Добавляем расширение .json, если его нет
            if not preset_name.endswith('.json'):
                preset_name += '.json'
            self.apply_style_file(preset_name)

    def open_color_settings(self):
        """Открывает диалоговое окно для настройки цветов."""
        try:
            color_dialog = ColorSettingsWindow(assistant=self.assistant, parent=self)
            color_dialog.colorChanged.connect(self.assistant.apply_styles)
            color_dialog.exec_()
        except Exception as e:
            logger.error(f"Ошибка при открытии окна настроек цветов: {e}")
            debug_logger.error(f"Ошибка при открытии окна настроек цветов: {e}")
            self.assistant.show_message(f"Не удалось открыть настройки цветов: {e}", "Ошибка", "error")


class SettingsWidget(QWidget):
    """
    Виджет общих настроек
    """
    voice_changed = Signal(str)

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.current_voice = None
        self.current_name = None
        self.current_name2 = None
        self.current_name3 = None
        self.current_steam_path = None
        self.current_volume = None
        self.name_1 = None
        self.load_current_settings()
        self.setObjectName("WMSettingsWidget")
        self.init_ui()

    def load_current_settings(self):
        self.current_voice = self.assistant.speaker
        self.current_name = self.assistant.assistant_name
        self.current_name2 = self.assistant.assist_name2
        self.current_name3 = self.assistant.assist_name3
        self.current_steam_path = self.assistant.steam_path
        self.current_volume = self.assistant.volume_assist

    def hide_method(self):
        """Закрывает панель настроек через главный класс"""
        if hasattr(self.assistant, 'hide_widget'):
            self.assistant.hide_widget()
        else:
            debug_logger.error("Метод close_settings не найден в assistant")

    def init_ui(self):
        # Создаем виджет-контейнер для содержимого
        content_widget = QWidget()
        content_widget.setMaximumWidth(420)
        content_widget.setObjectName("WMSettingsContent")
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Поле для ввода имени ассистента
        name_label = QLabel("Основное имя ассистента:", self)
        name_label.setStyleSheet("background: transparent;")
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit(self)
        self.name_input.setText(self.assistant.assistant_name)
        layout.addWidget(self.name_input)

        # Поле для ввода имени №2
        name2_label = QLabel("Дополнительно:", self)
        name2_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        name2_label.setStyleSheet("background: transparent;")
        layout.addWidget(name2_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name2_input = QLineEdit(self)
        self.name2_input.setText(self.assistant.assist_name2)
        layout.addWidget(self.name2_input)

        # Поле для ввода имени №3
        self.name3_input = QLineEdit(self)
        self.name3_input.setText(self.assistant.assist_name3)
        layout.addWidget(self.name3_input)

        # Выбор голоса
        voice_label = QLabel("Выберите голос:", self)
        voice_label.setStyleSheet("background: transparent;")
        layout.addWidget(voice_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems(list(speakers.keys()))
        current_key = next(key for key, value in speakers.items() if value == self.assistant.speaker)
        self.voice_combo.setCurrentText(current_key)
        self.voice_combo.currentIndexChanged.connect(self.on_voice_change)
        layout.addWidget(self.voice_combo)

        # Громкость
        volume_label = QLabel("Громкость ассистента", self)
        volume_label.setStyleSheet("background: transparent;")
        layout.addWidget(volume_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setStyleSheet("background: transparent;")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.assistant.volume_assist * 100))
        self.volume_slider.valueChanged.connect(self.update_volume)
        layout.addWidget(self.volume_slider)

        self.check_voice = QPushButton("Тест голоса", self)
        self.check_voice.clicked.connect(self.check_new_voice)
        layout.addWidget(self.check_voice)

        # Путь к Steam
        steam_label = QLabel("Укажите полный путь к файлу steam.exe", self)
        steam_label.setStyleSheet("background: transparent;")
        layout.addWidget(steam_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.steam_path_input = QLineEdit(self)
        self.steam_path_input.setText(self.assistant.steam_path)
        layout.addWidget(self.steam_path_input)

        select_steam_button = QPushButton("Выбрать папку", self)
        select_steam_button.setStyleSheet("padding-left: 5px; padding-right: 5px;")
        select_steam_button.clicked.connect(self.select_steam_folder)
        layout.addWidget(select_steam_button, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()

        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setStyleSheet("padding-left: 5px; padding-right: 5px;")
        self.default_btn.clicked.connect(self.set_default_settings)
        layout.addWidget(self.default_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Кнопка применения
        apply_button = QPushButton("Применить", self)
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignBottom)

    def update_volume(self, value):
        self.assistant.volume_assist = value / 100.0
        self.assistant.save_settings()

    def select_steam_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с steam.exe")

        if folder_path:
            # Проверяем наличие steam.exe в выбранной папке
            steam_exe_path = os.path.normpath(os.path.join(folder_path, "steam.exe"))
            if os.path.exists(steam_exe_path):
                self.steam_path_input.setText(steam_exe_path)
            else:
                self.assistant.show_message("Файл steam.exe не найден в выбранной папке!", "Предупреждение", "warning")

    def on_voice_change(self):
        new_voice_key = self.voice_combo.currentText()
        if new_voice_key in speakers:
            self.voice_changed.emit(speakers[new_voice_key])
            self.assistant.save_settings()

    def check_new_voice(self):
        """
        Метод для озвучивания выбранного голоса (в качестве проверки)
        """
        try:
            path = self.assistant.audio_paths
            get_path = path.get("echo_folder")
            thread_react(get_path)
        except Exception as e:
            logger.error(f"При тесте голоса произошла ошибка:{e}")
            debug_logger.error(f"При тесте голоса произошла ошибка:{e}")

    def update_ui(self):
        """Обновляет UI виджета текущими настройками"""
        self.name_input.setText(self.assistant.assistant_name)
        self.name2_input.setText(self.assistant.assist_name2)
        self.name3_input.setText(self.assistant.assist_name3)
        self.steam_path_input.setText(self.assistant.steam_path)
        self.volume_slider.setValue(int(self.assistant.volume_assist * 100))

        # Установка текущего голоса в комбобокс
        current_key = next((key for key, value in speakers.items() if value == self.assistant.speaker), None)
        if current_key:
            self.voice_combo.setCurrentText(current_key)

    def set_default_settings(self):
        default_settings = {
            "voice": "johnny",
            "assistant_name": "джон",
            "assist_name2": "джонни",
            "assist_name3": "джон",
            "steam_path": "D:/Steam/steam.exe",
            "is_censored": True,
            "volume_assist": 0.15,
            "run_updater": True,
            "minimize_to_tray": False,
            "start_win": True,
            "is_widget": True,
            "is_keep_watch": False,
            "input_device_id": None,
            "input_device_name": None
        }

        if os.path.exists(self.assistant.settings_file_path):
            with open(self.assistant.settings_file_path, "r", encoding="utf-8") as file:
                try:
                    settings = json.load(file)
                except json.JSONDecodeError:
                    settings = {}
        else:
            settings = {}

        for key, value in default_settings.items():
            settings[key] = value

        with open(self.assistant.settings_file_path, "w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=4)
            self.assistant.show_notification_message("Установлены настройки по умолчанию!")

        # Загружаем настройки в ассистента
        self.assistant.install_settings()
        # Обновляем текущие настройки в виджете
        self.load_current_settings()
        # Обновляем UI
        self.update_ui()

    def apply_settings(self):
        new_name = self.name_input.text().strip().lower()
        if not new_name:
            self.assistant.show_message(f"Имя ассистента не может быть пустым", "Предупреждение", "warning")
            return

        new_name2 = self.name2_input.text().strip().lower()
        new_name3 = self.name3_input.text().strip().lower()
        new_steam_path = self.steam_path_input.text().strip()

        if not os.path.isfile(new_steam_path):
            self.assistant.show_message(f"Укажите правильный путь к steam.exe", "Предупреждение", "warning")
            return

        # Обновляем параметры в родительском окне
        self.assistant.assistant_name = new_name
        self.assistant.assist_name2 = new_name2 if new_name2 else new_name
        self.assistant.assist_name3 = new_name3 if new_name3 else new_name
        self.assistant.steam_path = new_steam_path
        self.assistant.speaker = speakers[self.voice_combo.currentText()]

        self.assistant.save_settings()
        self.hide_method()
        self.assistant.show_notification_message(message="Настройки применены!")


class OtherSettingsWidget(QWidget):
    """ Виджет с дополнительными настройками (перенёс сюда чекбоксы) """

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.init_ui()
        self.get_devices()

    def init_ui(self):
        content_widget = QWidget()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Чекбоксы
        self.censor_check = QCheckBox("Реагировать на мат", self)
        self.censor_check.setStyleSheet("background: transparent;")
        self.censor_check.setChecked(self.assistant.is_censored)
        self.censor_check.stateChanged.connect(self.toggle_censor)
        layout.addWidget(self.censor_check)

        self.update_check = QCheckBox("Запуск утилиты обновления \n перед стартом программы", self)
        self.update_check.setStyleSheet("background: transparent;")
        self.update_check.setChecked(self.assistant.run_updater)
        self.update_check.stateChanged.connect(self.toggle_update)
        layout.addWidget(self.update_check)

        self.start_win_check = QCheckBox("Запуск с Windows", self)
        self.start_win_check.setStyleSheet("background: transparent;")
        self.start_win_check.setChecked(self.assistant.toggle_start)
        self.start_win_check.stateChanged.connect(self.assistant.toggle_start_win)
        layout.addWidget(self.start_win_check)

        # Чекбокс для сворачивания в трей
        self.minimize_check = QCheckBox("Сворачивать в трей при запуске", self)
        self.minimize_check.setStyleSheet("background: transparent;")
        self.minimize_check.setChecked(self.assistant.is_min_tray)
        self.minimize_check.stateChanged.connect(self.toggle_minimize)
        layout.addWidget(self.minimize_check)

        self.widget_check = QCheckBox("Запускать виджет", self)
        self.widget_check.setStyleSheet("background: transparent;")
        self.widget_check.setToolTip("Открытие виджета при запуске программы")
        self.widget_check.setChecked(self.assistant.is_widget)
        self.widget_check.stateChanged.connect(self.toggle_widget)
        layout.addWidget(self.widget_check)

        self.keep_watch_check = QCheckBox("Обрабатывать команды \nбез имени ассистента"
                                          "\n(возможны ложные срабатывания)", self)
        self.keep_watch_check.setStyleSheet("background: transparent;")
        self.keep_watch_check.setToolTip("Расширенная обработка команд")
        self.keep_watch_check.setChecked(self.assistant.is_keep_watch)
        self.keep_watch_check.stateChanged.connect(self.toggle_keep_watch)
        layout.addWidget(self.keep_watch_check)

        self.add_link_btn = QPushButton("Добавить ярлык на Рабочий стол", self)
        self.add_link_btn.clicked.connect(self.add_link_desktop)
        layout.addWidget(self.add_link_btn)

        self.label_input = QLabel("Устройство ввода")
        self.label_input.setStyleSheet("background: transparent;")
        self.device_list = QComboBox()
        layout.addWidget(self.label_input)
        layout.addWidget(self.device_list)

        layout.addStretch()

        self.device_list.activated.connect(self.on_microphone_selected)

    def toggle_censor(self):
        self.assistant.is_censored = self.censor_check.isChecked()
        self.assistant.save_settings()

    def toggle_update(self):
        self.assistant.run_updater = self.update_check.isChecked()
        self.assistant.save_settings()

    def toggle_minimize(self):
        """Обработка чекбокса 'Сворачивать в трей'"""
        self.assistant.is_min_tray = self.minimize_check.isChecked()
        self.assistant.save_settings()

    def toggle_widget(self):
        """Обработка чекбокса 'Запускать виджет'"""
        self.assistant.is_widget = self.widget_check.isChecked()
        self.assistant.save_settings()

    def toggle_keep_watch(self):
        """Обработка чекбокса 'Запускать виджет'"""
        self.assistant.is_keep_watch = self.keep_watch_check.isChecked()
        self.assistant.save_settings()

    def add_link_desktop(self):
        """
        Создает ярлыки на рабочем столе и в меню "Пуск" с проверкой на существование
        """
        dir_path = os.path.dirname(get_path())
        executable_path = os.path.join(dir_path, "Assistant.exe")
        app_name = "Ассистент"

        # Проверяем существование исполняемого файла
        if not os.path.exists(executable_path):
            self.assistant.show_notification_message(f"Ошибка: Файл {executable_path} не существует")
            return

        shortcuts_created = False

        try:
            # Создаем ярлык на рабочем столе (если его нет)
            desktop_path = winshell.desktop()
            desktop_shortcut = os.path.join(desktop_path, f"{app_name}.lnk")

            if not os.path.exists(desktop_shortcut):
                with winshell.shortcut(desktop_shortcut) as shortcut:
                    shortcut.path = executable_path
                    shortcut.working_directory = os.path.dirname(executable_path)
                    shortcut.description = f"Ярлык для {app_name}"
                    shortcut.icon_location = (executable_path, 0)
                shortcuts_created = True
                debug_logger.info(f"Ярлык создан на рабочем столе: {desktop_shortcut}")
            else:
                debug_logger.error(f"Ярлык на рабочем столе уже существует: {desktop_shortcut}")

        except Exception as e:
            self.assistant.show_notification_message(f"Ошибка создания ярлыка на рабочем столе: {e}")

        try:
            # Создаем ярлык в меню "Пуск" (если его нет)
            programs_folder = winshell.programs()

            # Создаем папку для нашего приложения в меню "Пуск"
            app_startup_folder = os.path.join(programs_folder, app_name)
            os.makedirs(app_startup_folder, exist_ok=True)

            startup_shortcut = os.path.join(app_startup_folder, f"{app_name}.lnk")

            if not os.path.exists(startup_shortcut):
                with winshell.shortcut(startup_shortcut) as shortcut:
                    shortcut.path = executable_path
                    shortcut.working_directory = os.path.dirname(executable_path)
                    shortcut.description = f"Ярлык для {app_name}"
                    shortcut.icon_location = (executable_path, 0)
                shortcuts_created = True
                debug_logger.info(f"Ярлык создан в меню 'Пуск': {startup_shortcut}")
            else:
                debug_logger.error(f"Ярлык в меню 'Пуск' уже существует: {startup_shortcut}")

        except Exception as e:
            self.assistant.show_notification_message(f"Ошибка создания ярлыка в меню 'Пуск': {e}")

        # Показываем сообщение только если были созданы новые ярлыки
        if shortcuts_created:
            self.assistant.show_notification_message("Ярлык успешно создан!")
        else:
            self.assistant.show_notification_message("Ярлык уже существует!")

    def get_devices(self):
        self.device_list.clear()

        try:
            devices = self.get_input_devices()

            if not devices:
                self.device_list.addItem("Нет активных микрофонов")
                return

            for name, index in devices:
                self.device_list.addItem(name, index)

        except Exception as e:
            self.device_list.addItem("Нет активных микрофонов")
            self.assistant.show_notification_message(f"Ошибка при получении данных аудиоустройств: {str(e)}")
            debug_logger.error(f"Ошибка при получении данных аудиоустройств: {str(e)}")

    def get_input_devices(self):
        devices = sd.query_devices()
        active_mics = []
        seen_names = set()  # Для борьбы с дублями
        try:
            for device in devices:
                try:
                    if device.get('max_input_channels', 0) == 0:
                        continue  # Только вход

                    name = device.get('name', '').strip()
                    idx = device['index']

                    # --- Фильтр: исключаем системные/виртуальные ---
                    if any(keyword in name.lower() for keyword in [
                        'mapper', 'primary', 'wave', 'звуковой маршрутизатор',
                        'драйвер записи', 'default', 'аналоговый'
                    ]):
                        continue

                    # Получаем тип API
                    host_api_name = sd.query_hostapis(device['hostapi'])['name']
                    if host_api_name.lower() in ['mm', 'mme', 'directsound']:
                        # Пропускаем MME и DirectSound, если есть WASAPI аналог
                        # Но можно временно добавить для теста с пометкой
                        continue  # ← лучше использовать только WASAPI

                    # Упрощаем имя для сравнения (убираем цифры в скобках и т.п.)
                    clean_name = name.split('(')[0].strip()

                    # Избегаем дублей по базовому имени
                    if clean_name in seen_names:
                        continue
                    seen_names.add(clean_name)

                    # Проверяем, можно ли открыть поток
                    try:
                        with sd.InputStream(
                                device=idx,
                                channels=1,
                                samplerate=44100,
                                blocksize=1024
                        ):
                            active_mics.append((name, idx))
                    except Exception:
                        continue  # Не удалось открыть

                except Exception:
                    continue

            return active_mics
        except Exception as e:
            debug_logger.error(f"Ошибка в проверке активных микрофонов: {str(e)}")

    def on_microphone_selected(self):
        device_id = self.device_list.currentData()  # int или None
        if device_id is not None:
            # Получаем имя устройства по ID
            device_info = sd.query_devices(device_id)
            device_name = device_info['name']

            # Сохраняем и ID, и имя
            self.assistant.input_device_id = device_id
            self.assistant.input_device_name = device_name

            # Сохраняем в файл настроек
            self.assistant.save_settings()
            self.assistant.save_settings_signal.emit()

            debug_logger.info(f"Выбрано устройство: '{device_name}' (ID={device_id})")

    def hide_method(self):
        """Закрывает панель настроек через главный класс"""
        if hasattr(self.assistant, 'hide_widget'):
            self.assistant.hide_widget()
        else:
            debug_logger.error("Метод close_settings не найден в assistant")


class DraggableCheckbox(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_mode_enabled = False
        self.is_dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.original_pos = None

    def set_drag_mode(self, enabled):
        self.drag_mode_enabled = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_mode_enabled:
            self.is_dragging = False
            self.drag_start_position = event.pos()
            self.original_pos = self.pos()
        else:
            # В обычном режиме разрешаем стандартную обработку чекбокса
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.drag_mode_enabled:
            return super().mouseMoveEvent(event)

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if not hasattr(self, 'drag_start_position'):
            return

        if not self.is_dragging:
            # В PySide6 используем startDragDistance как свойство
            if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                return

            # Начинаем перетаскивание
            self.is_dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            # Сообщаем родителю о начале перетаскивания
            parent = self.parent()
            while parent and not hasattr(parent, 'start_dragging'):
                parent = parent.parent()

            if parent and hasattr(parent, 'start_dragging'):
                parent.start_dragging(self)

        # Обновляем позицию перетаскиваемого элемента
        if self.is_dragging:
            parent = self.parent()
            while parent and not hasattr(parent, 'update_drag_position'):
                parent = parent.parent()

            if parent and hasattr(parent, 'update_drag_position'):
                global_pos = self.mapToGlobal(event.pos())
                local_pos = parent.mapFromGlobal(global_pos)
                parent.update_drag_position(local_pos, self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

            # Сообщаем родителю о завершении перетаскивания
            parent = self.parent()
            while parent and not hasattr(parent, 'stop_dragging'):
                parent = parent.parent()

            if parent and hasattr(parent, 'stop_dragging'):
                parent.stop_dragging(self)

        if hasattr(self, 'drag_start_position'):
            delattr(self, 'drag_start_position')

        super().mouseReleaseEvent(event)


class DragContainer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_target_index = -1
        self.setAcceptDrops(True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.dragged_widget = None

        self.drop_indicator = QFrame()
        self.drop_indicator.setFixedHeight(3)
        # self.drop_indicator.setStyleSheet("background-color: #0078d4;")
        self.drop_indicator.hide()

        self.placeholder = QFrame()
        self.placeholder.setFixedHeight(40)
        self.placeholder.setStyleSheet("background-color: transparent")
        self.placeholder.hide()

    def addCheckbox(self, checkbox):
        self.layout.addWidget(checkbox)

    def set_drag_mode(self, enabled):
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, DraggableCheckbox):
                widget.set_drag_mode(enabled)

    def start_dragging(self, widget):
        self.dragged_widget = widget

        self.original_object_name = widget.objectName()
        widget.setObjectName("DraggedCheckbox")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

        # УДАЛЯЕМ виджет из layout перед началом перетаскивания
        self.layout.removeWidget(widget)
        widget.setParent(self)
        widget.show()

        # Запоминаем оригинальную позицию для плейсхолдера
        self.placeholder_index = self.layout.indexOf(widget)

        # Поднимаем перетаскиваемый виджет над остальными
        widget.raise_()

    def update_drag_position(self, pos, widget):
        if not self.dragged_widget:
            return

        # Перемещаем виджет за курсором
        widget.move(pos.x() - widget.drag_start_position.x(),
                    pos.y() - widget.drag_start_position.y())

        # Находим новую позицию для вставки
        new_index = self.find_drop_index(pos)

        # Обновляем плейсхолдер только если позиция изменилась
        if hasattr(self, 'current_target_index') and new_index != self.current_target_index:
            self.current_target_index = new_index
            self.update_placeholder_position(new_index)

        # Обновляем индикатор
        self.update_drop_indicator(new_index)

    def update_placeholder_position(self, new_index):
        # Удаляем плейсхолдер если он уже есть
        if self.placeholder.parent() == self:
            self.layout.removeWidget(self.placeholder)

        # Вставляем плейсхолдер на новую позицию
        self.layout.insertWidget(new_index, self.placeholder)
        self.placeholder.show()

    def stop_dragging(self, widget):
        if not self.dragged_widget:
            return

        # Восстанавливаем оригинальное имя
        if hasattr(self, 'original_object_name'):
            widget.setObjectName(self.original_object_name)

        # Определяем финальную позицию
        final_index = self.drop_indicator_index if hasattr(self, 'drop_indicator_index') else self.placeholder_index

        # Удаляем плейсхолдер
        if self.placeholder.parent() == self:
            self.layout.removeWidget(self.placeholder)
        self.placeholder.hide()

        # ВОЗВРАЩАЕМ виджет в layout на новую позицию
        self.layout.insertWidget(final_index, widget)

        # Сбрасываем стиль и курсор
        widget.setStyleSheet("")
        widget.setCursor(Qt.CursorShape.OpenHandCursor)

        # Скрываем индикатор
        self.drop_indicator.hide()
        self.dragged_widget = None
        self.current_target_index = -1

    def find_drop_index(self, pos):
        closest_index = -1
        min_distance = float('inf')

        # Буферная зона вверху (первые 20 пикселей) - всегда вставляем в начало
        if pos.y() < 20:
            return 0

        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if widget and widget != self.placeholder and widget != self.dragged_widget:
                widget_rect = widget.geometry()

                # Проверяем попадание в область виджета
                if widget_rect.contains(pos):
                    # Решаем, вставлять до или после элемента
                    if pos.y() < widget_rect.center().y():
                        return i  # Вставляем перед этим элементом
                    else:
                        return i + 1  # Вставляем после этого элемента

                # Если не попали в область, ищем ближайший элемент
                distance_to_top = abs(widget_rect.top() - pos.y())
                distance_to_bottom = abs(widget_rect.bottom() - pos.y())
                distance = min(distance_to_top, distance_to_bottom)

                if distance < min_distance:
                    min_distance = distance
                    if pos.y() < widget_rect.center().y():
                        closest_index = i
                    else:
                        closest_index = i + 1

        return closest_index if closest_index != -1 else self.layout.count()

    def update_drop_indicator(self, index):
        if index == -1:
            self.drop_indicator.hide()
            return

        self.drop_indicator_index = index

        if index < self.layout.count():
            target_widget = self.layout.itemAt(index).widget()
            if target_widget and target_widget != self.placeholder:
                indicator_y = target_widget.geometry().top() - 2
                self.drop_indicator.setParent(self)
                self.drop_indicator.move(10, indicator_y)
                self.drop_indicator.setFixedWidth(self.width() - 20)
                self.drop_indicator.show()
                return

        # Если вставляем в конец
        if self.layout.count() > 0:
            last_widget = self.layout.itemAt(self.layout.count() - 1).widget()
            if last_widget and last_widget != self.placeholder:
                indicator_y = last_widget.geometry().bottom() + 2
                self.drop_indicator.setParent(self)
                self.drop_indicator.move(10, indicator_y)
                self.drop_indicator.setFixedWidth(self.width() - 20)
                self.drop_indicator.show()
            else:
                self.drop_indicator.hide()
        else:
            self.drop_indicator.hide()


class NonClosingComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_open = False

    def showPopup(self):
        super().showPopup()
        self._popup_open = True
        # Устанавливаем глобальный фильтр событий
        QApplication.instance().installEventFilter(self)

    def hidePopup(self):
        # Блокируем автоматическое закрытие
        if not self._popup_open:
            super().hidePopup()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and self._popup_open:
            # Получаем позицию клика в глобальных координатах
            mouse_event = event
            global_pos = mouse_event.globalPos()

            # Геометрия выпадающего списка
            popup = self.view()
            popup_global_rect = popup.rect()
            popup_global_rect.moveTo(popup.mapToGlobal(popup_global_rect.topLeft()))

            # Геометрия комбобокса
            combo_global_rect = self.rect()
            combo_global_rect.moveTo(self.mapToGlobal(combo_global_rect.topLeft()))

            # Если клик вне обоих областей - закрываем
            if not popup_global_rect.contains(global_pos) and not combo_global_rect.contains(global_pos):
                self._popup_open = False
                QApplication.instance().removeEventFilter(self)
                super().hidePopup()
                return True

        return False

    def closePopup(self):
        self._popup_open = False
        QApplication.instance().removeEventFilter(self)
        super().hidePopup()


class SettingsWidgetPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.assistant = parent
        self.widget_state = get_path("user_settings", "widget_state.json")
        self.drag_mode = False
        self.fonts_list = fonts_list
        self.init_ui()
        self.load_saved_font()
        self.load_buttons_settings()

    def init_ui(self):
        content_widget = QWidget()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.get_widget_btn = QPushButton("Открыть виджет", self)
        self.get_widget_btn.clicked.connect(self.get_widget)
        layout.addWidget(self.get_widget_btn)

        self.title = QLabel("Настройка кнопок на виджет-панели")
        self.title.setStyleSheet("font-size: 16px; background: transparent")
        layout.addWidget(self.title)

        # Кнопка для включения/выключения режима перетаскивания
        self.drag_toggle_btn = QPushButton("Настроить порядок расположения")
        self.drag_toggle_btn.clicked.connect(self.toggle_drag_mode)
        layout.addWidget(self.drag_toggle_btn)

        drag_layout = QVBoxLayout()

        # Создаем контейнер для перетаскивания
        self.drag_container = DragContainer()
        self.drag_container.setMinimumHeight(300)
        self.drag_container.setStyleSheet("background: transparent")
        self.drag_container.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.drag_container.layout.setSpacing(10)  # Добавляем отступы между чекбоксами
        self.drag_container.layout.setContentsMargins(5, 5, 5, 5)

        drag_layout.addWidget(self.drag_container)

        # Создаем чекбоксы
        self.create_checkboxes()
        layout.addLayout(drag_layout)

        # Создание виджетов
        font_layout = QHBoxLayout()

        # Лейбл с временем для демонстрации шрифта
        self.font_preview_label = QLabel("12:34")
        self.font_preview_label.setObjectName("preview_clock")
        self.font_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_preview_label.setStyleSheet("background: transparent; padding: 5px;")

        self.font_combo = NonClosingComboBox()
        self.font_combo.addItems(self.fonts_list.keys())
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(self.font_preview_label)
        layout.addLayout(font_layout)
        self.setup_font_selector()

        layout.addStretch()

        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setStyleSheet("padding-left: 10px; padding-right: 10px")
        self.default_btn.clicked.connect(self.set_default_buttons_settings)
        layout.addWidget(self.default_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.save_btn = QPushButton("Применить")
        self.save_btn.clicked.connect(self.save_order)
        layout.addWidget(self.save_btn)

    def get_widget(self):
        self.assistant.open_widget()

    def setup_font_selector(self):
        """Настройка выбора шрифта"""
        # Подключаем сигнал изменения выбора
        self.font_combo.currentTextChanged.connect(self.change_font_preview)

        # Устанавливаем начальный шрифт
        if self.font_combo.currentText():
            self.change_font_preview(self.font_combo.currentText())

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

        debug_logger.info(f"Применение шрифта для превью: {font_family} с размером: {font_size}")

        styles = f"""
            #preview_clock {{
                font-family: "{font_family}";
                font-size: {font_size};
                font-weight: normal;
                padding: 0px;
                background: transparent;
            }}
        """

        # ✅ Убедимся, что objectName установлен
        if self.font_preview_label.objectName() != "preview_clock":
            self.font_preview_label.setObjectName("preview_clock")

        # ✅ Применяем стили к preview_label
        self.font_preview_label.setStyleSheet(styles)

    def change_font_preview(self, font_name):
        """Изменение шрифта в превью"""
        if font_name in self.fonts_list:
            font_path = self.fonts_list[font_name]
            # Загружаем шрифт
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    font_family = font_families[0]

                    # Используем новый метод apply_font_styles
                    self.apply_font_styles(font_family, font_name)

    def get_selected_font(self):
        """Получить выбранный шрифт"""
        font_name = self.font_combo.currentText()
        if font_name in self.fonts_list:
            return self.fonts_list[font_name]
        return None

    def get_selected_font_family(self):
        """Получить семейство выбранного шрифта"""
        font_name = self.font_combo.currentText()
        if font_name in self.fonts_list:
            font_path = self.fonts_list[font_name]
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        return "Arial"  # Fallback шрифт

    def load_saved_font(self):
        """Загрузка сохраненного шрифта при запуске"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем есть ли сохраненный шрифт
            if "font_family" in data:
                saved_font = data["font_family"]

                # Устанавливаем в комбобокс
                if saved_font in self.fonts_list:
                    index = self.font_combo.findText(saved_font)
                    if index >= 0:
                        self.font_combo.setCurrentIndex(index)

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            debug_logger.warning(f"Не удалось загрузить сохраненный шрифт: {e}")
            # Устанавливаем шрифт по умолчанию
            default_index = self.font_combo.findText("digital")
            if default_index >= 0:
                self.font_combo.setCurrentIndex(default_index)

    def create_checkboxes(self):
        checkboxes_data = [
            ("turnoff_check", "Выключение компьютера"),
            ("settings_check", "Открыть настройки"),
            ("screenshot_check", "Сделать скриншот"),
            ("open_youtube", "Запустить YouTube"),
            ("microphone_check", "Управление микрофоном в Discord"),
            ("links_check", "Открыть папку с ярлыками"),
            ("resize_check", "Развернуть окно ассистента"),
        ]

        # Очищаем контейнер перед добавлением
        for i in reversed(range(self.drag_container.layout.count())):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for key, text in checkboxes_data:
            checkbox = DraggableCheckbox(text)
            self.checkboxes[key] = checkbox
            self.drag_container.layout.addWidget(checkbox)

    def toggle_drag_mode(self):
        self.drag_mode = not self.drag_mode
        self.drag_container.set_drag_mode(self.drag_mode)

        if self.drag_mode:
            self.drag_toggle_btn.setText("Режим перетаскивания: ВКЛ")
            # В режиме перетаскивания только меняем курсор, но не блокируем чекбоксы
            for checkbox in self.checkboxes.values():
                checkbox.setCursor(Qt.CursorShape.OpenHandCursor)
                # Сохраняем текущее состояние checked для отображения
                checkbox.update()
        else:
            self.drag_toggle_btn.setText("Настроить порядок расположения")
            # Возвращаем обычный курсор
            for checkbox in self.checkboxes.values():
                checkbox.setCursor(Qt.CursorShape.ArrowCursor)

    def get_checkbox_order(self):
        order = []
        for i in range(self.drag_container.layout.count()):
            widget = self.drag_container.layout.itemAt(i).widget()
            if isinstance(widget, DraggableCheckbox):
                for key, cb in self.checkboxes.items():
                    if cb == widget:
                        order.append(key)
                        break
        return order

    def get_buttons_data(self):
        """Получить данные о кнопках в порядке их расположения"""
        buttons_data = {}

        # Проходим по layout в текущем порядке
        for i in range(self.drag_container.layout.count()):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget and hasattr(widget, 'text'):
                # Находим ключ этого чекбокса
                for key, checkbox in self.checkboxes.items():
                    if checkbox == widget:
                        buttons_data[key] = checkbox.isChecked()
                        break

        return buttons_data

    def load_buttons_settings(self):
        """Загрузить настройки кнопок из файла (порядок и состояния)"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            if "buttons" not in settings_data:
                return False

            buttons_data = settings_data["buttons"]

            # Удаляем все чекбоксы из layout
            for i in reversed(range(self.drag_container.layout.count())):
                widget = self.drag_container.layout.itemAt(i).widget()
                if widget and hasattr(widget, 'text'):
                    self.drag_container.layout.removeWidget(widget)

            # Добавляем чекбоксы в порядке из файла и устанавливаем состояния
            for key, state in buttons_data.items():
                if key in self.checkboxes:
                    checkbox = self.checkboxes[key]
                    checkbox.setChecked(state)
                    self.drag_container.layout.addWidget(checkbox)

            return True

        except FileNotFoundError:
            debug_logger.error(f"Файл {self.widget_state} не найден")
            return False
        except json.JSONDecodeError:
            debug_logger.error(f"Ошибка чтения JSON из {self.widget_state}")
            return False

    def set_default_buttons_settings(self):
        """Установить стандартные настройки кнопок (все активны, стандартный порядок)"""
        # Удаляем все чекбоксы из layout
        for i in reversed(range(self.drag_container.layout.count())):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget and hasattr(widget, 'text'):
                self.drag_container.layout.removeWidget(widget)

        # Стандартный порядок чекбоксов
        default_order = [
            "turnoff_check",
            "settings_check",
            "screenshot_check",
            "open_youtube",
            "microphone_check",
            "links_check",
            "resize_check",
        ]

        # Добавляем в стандартном порядке и включаем все чекбоксы
        for key in default_order:
            if key in self.checkboxes:
                checkbox = self.checkboxes[key]
                checkbox.setChecked(True)  # Все активны
                self.drag_container.layout.addWidget(checkbox)

        self.save_order()

    def save_order(self):
        order = self.get_checkbox_order()
        with open(self.widget_state, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

        # Добавляем данные о кнопках (порядок сохранится в словаре)
        existing_data["buttons"] = self.get_buttons_data()

        existing_data["font_family"] = self.font_combo.currentText()

        # Сохраняем обратно
        with open(self.widget_state, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)

        QTimer.singleShot(100, widget_btns_signal.buttons_updated.emit)
