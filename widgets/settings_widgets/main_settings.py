import json
import os
from bin.utils import setup_custom_font_label
from bin.speak_functions import thread_react
from log_config import assist_log, logger
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QLineEdit, QComboBox, QSlider, QFileDialog
from PySide6.QtCore import Signal, Qt

speakers = dict(Персик="persik", Джарвис="jarvis", Пласид='placide', Бестия='rogue',
                Джонни='johnny', СанСаныч='sanych', Санбой='sanboy', Woman='tigress', Стейтем='stathem')


class SettingsWidget(QWidget):
    """
    Виджет общих настроек
    """
    voice_changed = Signal(str)

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.current_voice = None
        self.current_name = None
        self.current_name2 = None
        self.current_name3 = None
        self.current_steam_path = None
        self.current_volume = None
        self.name_1 = None
        self._help_initialized = False
        self.load_current_settings()
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.init_ui()

    def load_current_settings(self):
        self.current_voice = self.main.speaker
        self.current_name = self.main.assistant_name
        self.current_name2 = self.main.assist_name2
        self.current_name3 = self.main.assist_name3
        self.current_steam_path = self.main.steam_path
        self.current_volume = self.main.volume_assist

    def hide_method(self):
        """Закрывает панель настроек через главный класс"""
        if hasattr(self.main, 'hide_widget'):
            self.main.hide_widget()
        else:
            logger.error("[SETTINGS-WIDGET] Метод close_settings не найден в main")
            
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        content_widget = QWidget()
        content_widget.setObjectName("CustomPageContent")
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title = setup_custom_font_label("Основные настройки")
        self.title.setStyleSheet("background: transparent; font-size: 18px")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Поле для ввода имени ассистента
        name_label = setup_custom_font_label("Основное имя ассистента:")
        name_label.setStyleSheet("background: transparent; font-size: 14px;")
        name_label.setProperty("helpId", "name_label")
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit(self)
        self.name_input.setText(self.main.assistant_name)
        self.name_input.setProperty("helpId", "name_label")
        layout.addWidget(self.name_input)

        # Поле для ввода имени №2
        name2_label = setup_custom_font_label("Дополнительно:")
        name2_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        name2_label.setStyleSheet("background: transparent; font-size: 14px;")
        name2_label.setProperty("helpId", "name2_label")
        layout.addWidget(name2_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name2_input = QLineEdit(self)
        self.name2_input.setText(self.main.assist_name2)
        self.name2_input.setProperty("helpId", "name2_label")
        layout.addWidget(self.name2_input)

        # Поле для ввода имени №3
        self.name3_input = QLineEdit(self)
        self.name3_input.setText(self.main.assist_name3)
        self.name3_input.setProperty("helpId", "name2_label")
        layout.addWidget(self.name3_input)

        # Выбор голоса
        voice_label = setup_custom_font_label("Выберите голос:")
        voice_label.setStyleSheet("background: transparent; font-size: 14px;")
        voice_label.setProperty("helpId", "voice_label")
        layout.addWidget(voice_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems(list(speakers.keys()))
        current_key = next(key for key, value in speakers.items() if value == self.main.speaker)
        self.voice_combo.setCurrentText(current_key)
        self.voice_combo.currentIndexChanged.connect(self.on_voice_change)
        self.voice_combo.setProperty("helpId", "voice_label")
        layout.addWidget(self.voice_combo)

        # Громкость
        volume_label = setup_custom_font_label("Громкость ассистента")
        volume_label.setStyleSheet("background: transparent; font-size: 14px;")
        volume_label.setProperty("helpId", "volume_label")
        layout.addWidget(volume_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setStyleSheet("background: transparent;")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.main.volume_assist * 100))
        self.volume_slider.valueChanged.connect(self.update_volume)
        self.volume_slider.setProperty("helpId", "volume_label")
        layout.addWidget(self.volume_slider)

        self.check_voice = QPushButton("Тест голоса", self)
        self.check_voice.clicked.connect(self.check_new_voice)
        layout.addWidget(self.check_voice)

        # Путь к Steam
        steam_label = setup_custom_font_label("Путь к файлу steam.exe")
        steam_label.setStyleSheet("background: transparent; font-size: 14px;")
        steam_label.setProperty("helpId", "steam_label")
        layout.addWidget(steam_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.steam_path_input = QLineEdit(self)
        self.steam_path_input.setText(self.main.steam_path)
        self.steam_path_input.setProperty("helpId", "steam_label")
        layout.addWidget(self.steam_path_input)

        select_steam_button = QPushButton("Выбрать папку", self)
        select_steam_button.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        select_steam_button.clicked.connect(self.select_steam_folder)
        layout.addWidget(select_steam_button, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()

        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.default_btn.clicked.connect(self.set_default_settings)
        self.default_btn.setProperty("helpId", "default_btn")
        layout.addWidget(self.default_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Кнопка применения
        apply_button = QPushButton("Применить", self)
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignBottom)

    def update_volume(self, value):
        self.main.volume_assist = value / 100.0
        self.main.save_settings()

    def select_steam_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с steam.exe")

        if folder_path:
            # Проверяем наличие steam.exe в выбранной папке
            steam_exe_path = os.path.normpath(os.path.join(folder_path, "steam.exe"))
            if os.path.exists(steam_exe_path):
                self.steam_path_input.setText(steam_exe_path)
            else:
                self.main.show_message("Файл steam.exe не найден в выбранной папке!", "Предупреждение", "warning")

    def on_voice_change(self):
        new_voice_key = self.voice_combo.currentText()
        if new_voice_key in speakers:
            self.voice_changed.emit(speakers[new_voice_key])
            self.main.save_settings()

    def check_new_voice(self):
        """
        Метод для озвучивания выбранного голоса (в качестве проверки)
        """
        try:
            path = self.main.audio_paths
            get_path = path.get("echo_folder")
            thread_react(get_path)
        except Exception as e:
            assist_log.error(f"При тесте голоса произошла ошибка:{e}")
            logger.error(f"[SETTINGS-WIDGET] При тесте голоса произошла ошибка:{e}")

    def update_ui(self):
        """Обновляет UI виджета текущими настройками"""
        self.name_input.setText(self.main.assistant_name)
        self.name2_input.setText(self.main.assist_name2)
        self.name3_input.setText(self.main.assist_name3)
        self.steam_path_input.setText(self.main.steam_path)
        self.volume_slider.setValue(int(self.main.volume_assist * 100))

        # Установка текущего голоса в комбобокс
        current_key = next((key for key, value in speakers.items() if value == self.main.speaker), None)
        if current_key:
            self.voice_combo.setCurrentText(current_key)

    def set_default_settings(self):
        default_settings = {
            "voice": "johnny",
            "assistant_name": "джон",
            "assist_name2": "джонни",
            "assist_name3": "джон",
            "steam_path": "",
            "is_censored": True,
            "volume_assist": 0.15,
            "run_updater": True,
            "is_min_tray": False,
            "autostart_app": False,
            "is_widget": True,
            "is_keep_watch": False,
            "input_device_id": None,
            "input_device_name": None
        }

        if os.path.exists(self.main.settings_file_path):
            with open(self.main.settings_file_path, "r", encoding="utf-8") as file:
                try:
                    settings = json.load(file)
                except json.JSONDecodeError:
                    settings = {}
        else:
            settings = {}

        for key, value in default_settings.items():
            settings[key] = value

        with open(self.main.settings_file_path, "w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=4)
            self.main.show_toast("Установлены настройки по умолчанию!")

        # Загружаем настройки в ассистента
        self.main.install_settings()
        # Обновляем текущие настройки в виджете
        self.load_current_settings()
        # Обновляем UI
        self.update_ui()

    def apply_settings(self):
        new_name = self.name_input.text().strip().lower()
        if not new_name:
            self.main.show_message(f"Имя ассистента не может быть пустым", "Предупреждение", "warning")
            return

        new_name2 = self.name2_input.text().strip().lower()
        new_name3 = self.name3_input.text().strip().lower()
        new_steam_path = self.steam_path_input.text().strip()

        # if not os.path.isfile(new_steam_path):
        #     self.main.show_message(f"Укажите правильный путь к steam.exe", "Предупреждение", "warning")
        #     return

        # Обновляем параметры в родительском окне
        self.main.assistant_name = new_name
        self.main.assist_name2 = new_name2 if new_name2 else new_name
        self.main.assist_name3 = new_name3 if new_name3 else new_name
        self.main.steam_path = new_steam_path
        self.main.speaker = speakers[self.voice_combo.currentText()]

        self.main.save_settings()
        self.hide_method()
        self.main.show_toast(message="Настройки применены!")