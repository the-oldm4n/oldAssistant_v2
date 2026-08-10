import os
import sounddevice as sd
import winshell
from mygui import  CustomToggle
from bin.utils import setup_custom_font_label
from path_builder import get_full_filepath
from log_config import  debuglog
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QComboBox
from PySide6.QtCore import Qt
from config import app_name


class OtherSettingsWidget(QWidget):
    """ Виджет с дополнительными настройками (перенёс сюда чекбоксы) """

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._help_initialized = False
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()
        self.get_devices()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        try:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)

            self.title = setup_custom_font_label("Дополнительные настройки")
            self.title.setStyleSheet("background: transparent; font-size: 18px")
            layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

            # Чекбоксы
            self.censor_check = CustomToggle("Реагировать на мат")
            self.censor_check.setStyleSheet("background: transparent;")
            self.censor_check.setChecked(self.main.is_censored)
            self.censor_check.stateChanged.connect(self.toggle_censor)
            self.censor_check.setProperty("helpId", "censor_check")
            layout.addWidget(self.censor_check)
            
            self.correct_command_check = CustomToggle("Запоминать предыдущую команду")
            self.correct_command_check.setStyleSheet("background: transparent;")
            self.correct_command_check.setChecked(self.main.is_corrected_command)
            self.correct_command_check.stateChanged.connect(self.toggle_correct_command)
            self.correct_command_check.setProperty("helpId", "correct_command_check")
            layout.addWidget(self.correct_command_check)

            self.update_check = CustomToggle("Запуск утилиты обновления \n перед стартом программы")
            self.update_check.setStyleSheet("background: transparent;")
            self.update_check.setChecked(self.main.run_updater)
            self.update_check.stateChanged.connect(self.toggle_update)
            self.update_check.setProperty("helpId", "update_check")
            layout.addWidget(self.update_check)

            self.start_win_check = CustomToggle("Запуск с Windows")
            self.start_win_check.setStyleSheet("background: transparent;")
            self.start_win_check.setChecked(self.main.autostart_app)
            self.start_win_check.stateChanged.connect(self.main.autostart_manager.toggle_autostart_win)
            self.start_win_check.setProperty("helpId", "start_win_check")
            layout.addWidget(self.start_win_check)

            # Чекбокс для сворачивания в трей
            self.minimize_check = CustomToggle("Сворачивать в трей при запуске")
            self.minimize_check.setStyleSheet("background: transparent;")
            self.minimize_check.setChecked(self.main.is_min_tray)
            self.minimize_check.stateChanged.connect(self.toggle_minimize)
            self.minimize_check.setProperty("helpId", "minimize_check")
            layout.addWidget(self.minimize_check)

            self.widget_check = CustomToggle("Запускать виджет")
            self.widget_check.setStyleSheet("background: transparent;")
            self.widget_check.setToolTip("Открытие виджета при запуске программы")
            self.widget_check.setChecked(self.main.is_widget)
            self.widget_check.stateChanged.connect(self.toggle_widget)
            self.widget_check.setProperty("helpId", "widget_check")
            layout.addWidget(self.widget_check)

            self.keep_watch_check = CustomToggle("Обрабатывать команды \nбез имени ассистента"
                                            "\n(возможны ложные срабатывания)")
            self.keep_watch_check.setStyleSheet("background: transparent;")
            self.keep_watch_check.setToolTip("Расширенная обработка команд")
            self.keep_watch_check.setChecked(self.main.is_keep_watch)
            self.keep_watch_check.stateChanged.connect(self.toggle_keep_watch)
            self.keep_watch_check.setProperty("helpId", "keep_watch_check")
            layout.addWidget(self.keep_watch_check)
            
            self.snow_check = CustomToggle("Снег на главном окне")
            self.snow_check.setStyleSheet("background: transparent;")
            self.snow_check.setToolTip("Показывать снег на главном окне")
            self.snow_check.setChecked(self.main.is_snow)
            self.snow_check.stateChanged.connect(self.toggle_snow_main)
            self.snow_check.setProperty("helpId", "snow_check")
            layout.addWidget(self.snow_check)
            
            self.garland_check = CustomToggle("Гирлянда на главном окне")
            self.garland_check.setStyleSheet("background: transparent;")
            self.garland_check.setToolTip("Показывать гирлянду")
            self.garland_check.setChecked(self.main.is_garland)
            self.garland_check.stateChanged.connect(self.toggle_garland_main)
            self.garland_check.setProperty("helpId", "garland_check")
            layout.addWidget(self.garland_check)

            self.add_link_btn = QPushButton("Добавить ярлык на Рабочий стол", self)
            self.add_link_btn.clicked.connect(self.add_link_desktop)
            self.add_link_btn.setProperty("helpId", "add_link_btn")
            layout.addWidget(self.add_link_btn)

            self.label_input = setup_custom_font_label("Устройство ввода")
            self.label_input.setStyleSheet("background: transparent; font-size: 14px;")
            self.label_input.setProperty("helpId", "label_input")
            self.device_list = QComboBox()
            self.device_list.setProperty("helpId", "label_input")
            layout.addWidget(self.label_input)
            layout.addWidget(self.device_list)

            layout.addStretch()

            self.device_list.activated.connect(self.on_microphone_selected)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        
    def toggle_snow_main(self):
        self.main.is_snow = self.snow_check.isChecked()
        self.main.save_settings()
        self.main.update_snow_state()
        
    def toggle_garland_main(self):
        self.main.is_garland = self.garland_check.isChecked()
        self.main.save_settings()
        self.main.update_garland_state()

    def toggle_censor(self):
        self.main.is_censored = self.censor_check.isChecked()
        self.main.save_settings()

    def toggle_update(self):
        self.main.run_updater = self.update_check.isChecked()
        self.main.save_settings()
        
    def toggle_correct_command(self):
        self.main.is_corrected_command = self.correct_command_check.isChecked()
        self.main.save_settings()

    def toggle_minimize(self):
        """Обработка чекбокса 'Сворачивать в трей'"""
        self.main.is_min_tray = self.minimize_check.isChecked()
        self.main.save_settings()

    def toggle_widget(self):
        """Обработка чекбокса 'Запускать виджет'"""
        self.main.is_widget = self.widget_check.isChecked()
        self.main.save_settings()

    def toggle_keep_watch(self):
        """Обработка чекбокса 'Запускать виджет'"""
        self.main.is_keep_watch = self.keep_watch_check.isChecked()
        self.main.save_settings()

    def add_link_desktop(self):
        """
        Создает ярлыки на рабочем столе и в меню "Пуск" с проверкой на существование
        """
        executable_path = get_full_filepath()

        if not os.path.exists(executable_path):
            self.main.show_toast(f"Ошибка: Файл {executable_path} не существует")
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
                debuglog.info(f"[SETTINGS-WIDGET] Ярлык создан на рабочем столе: {desktop_shortcut}")
            else:
                debuglog.error(f"[SETTINGS-WIDGET] Ярлык на рабочем столе уже существует: {desktop_shortcut}")

        except Exception as e:
            self.main.show_toast(f"Ошибка создания ярлыка на рабочем столе: {e}")

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
                debuglog.info(f"[SETTINGS-WIDGET] Ярлык создан в меню 'Пуск': {startup_shortcut}")
            else:
                debuglog.error(f"[SETTINGS-WIDGET] Ярлык в меню 'Пуск' уже существует: {startup_shortcut}")

        except Exception as e:
            self.main.show_toast(f"Ошибка создания ярлыка в меню 'Пуск': {e}")

        # Показываем сообщение только если были созданы новые ярлыки
        if shortcuts_created:
            self.main.show_toast("Ярлык успешно создан!")
        else:
            self.main.show_toast("Ярлык уже существует!")

    def get_devices(self):
        self.device_list.clear()

        try:
            devices = self.get_input_devices()
            if devices is None:
                devices = []

            if not devices:
                self.device_list.addItem("Нет активных микрофонов")
                return

            for name, index in devices:
                self.device_list.addItem(name, index)

        except Exception as e:
            self.device_list.addItem("Нет активных микрофонов")
            self.main.show_toast(f"Ошибка при получении данных аудиоустройств: {str(e)}")
            debuglog.error(f"[SETTINGS-WIDGET] Ошибка при получении данных аудиоустройств: {str(e)}")

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
            debuglog.error(f"[SETTINGS-WIDGET] Ошибка в проверке активных микрофонов: {str(e)}")
            return []

    def on_microphone_selected(self):
        device_id = self.device_list.currentData()  # int или None
        if device_id is not None:
            # Получаем имя устройства по ID
            device_info = sd.query_devices(device_id)
            device_name = device_info['name']

            # Сохраняем и ID, и имя
            self.main.input_device_id = device_id
            self.main.input_device_name = device_name

            # Сохраняем в файл настроек
            self.main.save_settings()
            self.main.save_settings_signal.emit()

            debuglog.info(f"[SETTINGS-WIDGET] Выбрано устройство: '{device_name}' (ID={device_id})")

    def hide_method(self):
        """Закрывает панель настроек через главный класс"""
        if hasattr(self.main, 'hide_widget'):
            self.main.hide_widget()
        else:
            debuglog.error("[SETTINGS-WIDGET] Метод close_settings не найден в main")     