import json
import os
import secrets
import string
import sounddevice as sd
import winshell
from bin.apply_color_methods import main_apply_colors
from bin.custom_svg_widget import CustomSvgWidget
from bin.custom_widgets import CustomToggle
from bin.edit_dialog import EditDialog
from bin.lists import fonts_list, default_keywords_data, setup_custom_font_label
from bin.shortcut_monitor import ShortcutMonitor
from bin.signals import color_signal, widget_btns_signal, update_presets_signal
from bin.speak_functions import thread_react
from bin.choose_color_window import ColorSettingsWindow
from bin.widget_window import WindowStateManager
from path_builder import get_path
from logging_config import logger, debug_logger
from PySide6.QtGui import QAction, QFontDatabase, QRegularExpressionValidator
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QWidget,\
    QDialog, QMenu, QMessageBox, QLineEdit, QComboBox, QSlider, QListWidget, QScrollArea, QFrame,\
    QListWidgetItem, QCheckBox, QSizePolicy, QGridLayout
from PySide6.QtCore import Signal, QTimer, Qt, QEvent, QRegularExpression


speakers = dict(Персик="persik", Джарвис="jarvis", Пласид='placide', Бестия='rogue',
                Джонни='johnny', СанСаныч='sanych', Санбой='sanboy', Woman='tigress', Стейтем='stathem')


class InterfaceWidget(QWidget):
    """Виджет настроек оформления интерфейса"""

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._help_initialized = False
        self.setProperty("helpId", "style_widget")
        update_presets_signal.presets_updated.connect(self.load_custom_styles)
        self.init_ui()

    style_applied = Signal(dict)  # Сигнал для передачи стиля
    
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        title = setup_custom_font_label("Выбор стиля интерфейса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.styles_widget = QWidget()
        self.styles_layout = QVBoxLayout(self.styles_widget)
        self.styles_layout.setSpacing(15)
        self.styles_layout.setContentsMargins(5, 5, 5, 5)

        base_presets = get_path('bin', 'color_presets')
        self.load_styles_from_folder(base_presets, self.styles_layout, is_custom=False)

        self.custom_label = setup_custom_font_label("Кастомные стили")
        self.custom_label.setStyleSheet("background: transparent; font-size: 14px;")
        self.styles_layout.addWidget(self.custom_label)

        self.custom_styles_container = QWidget()
        self.custom_styles_container.setStyleSheet("background: transparent;")
        self.custom_styles_layout = QVBoxLayout(self.custom_styles_container)
        self.custom_styles_layout.setContentsMargins(0, 0, 0, 0)
        self.styles_layout.addWidget(self.custom_styles_container)

        self.load_custom_styles()

        self.styles_layout.addStretch()

        scroll_area.setWidget(self.styles_widget)
        layout.addWidget(scroll_area, stretch=1)

        create_btn = QPushButton("Настроить свой стиль")
        create_btn.setMinimumHeight(40)
        create_btn.clicked.connect(self.open_color_settings)
        layout.addWidget(create_btn)

    def load_custom_styles(self):
        """Загружает пользовательские стили в отдельный контейнер"""
        custom_presets = get_path('user_settings', 'presets')
        while self.custom_styles_layout.count():
            child = self.custom_styles_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_nested_layout(child.layout())

        custom_grid = QGridLayout()
        custom_grid.setSpacing(10)
        custom_grid.setContentsMargins(0, 5, 0, 5)

        grid_container = QWidget()
        grid_container.setLayout(custom_grid)
        self.custom_styles_layout.addWidget(grid_container)
        
        if os.path.exists(custom_presets):
            try:
                style_files = [f for f in os.listdir(custom_presets) 
                            if f.endswith('.json') and os.path.isfile(os.path.join(custom_presets, f))]
                style_files.sort()
                
                if not style_files:
                    no_styles_label = QLabel("Пусто")
                    no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                    custom_grid.addWidget(no_styles_label, 0, 0, 1, 3)
                else:
                    for i, filename in enumerate(style_files):
                        row = i // 3
                        col = i % 3
                        
                        btn = self.create_style_button(filename, custom_presets, is_custom=True)
                        if btn:
                            custom_grid.addWidget(btn, row, col)
            
            except Exception as e:
                debug_logger.error(f"[SETTINGS-WIDGET] Ошибка чтения кастомных стилей: {e}")
                error_label = QLabel("Ошибка загрузки стилей")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_label.setStyleSheet("background-color: transparent; color: red;")
                custom_grid.addWidget(error_label, 0, 0, 1, 3)
        else:
            no_styles_label = QLabel("Папка со стилями не найдена")
            no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
            custom_grid.addWidget(no_styles_label, 0, 0, 1, 3)

    def clear_nested_layout(self, layout):
        """Рекурсивно очищает вложенные layout"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_nested_layout(child.layout())

    def load_styles_from_folder(self, folder_path, container_layout, is_custom=False):
        """Загружает стили из папки и создает кнопки"""
        if not os.path.exists(folder_path):
            if is_custom:
                no_styles_label = QLabel("Папка со стилями не найдена")
                no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                container_layout.addWidget(no_styles_label, 0, 0, 1, 3)
            return

        try:
            style_files = [f for f in os.listdir(folder_path) 
                        if f.endswith('.json') and os.path.isfile(os.path.join(folder_path, f))]
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка чтения папки {folder_path}: {e}")
            return

        if not style_files:
            if is_custom:
                no_styles_label = QLabel("Папка со стилями не найдена")
                no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                container_layout.addWidget(no_styles_label, 0, 0, 1, 3)
            return

        style_files.sort()

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 5, 0, 5)

        for i, filename in enumerate(style_files):
            row = i // 3
            col = i % 3
            
            btn = self.create_style_button(filename, folder_path, is_custom)
            if btn:
                grid_layout.addWidget(btn, row, col)
        container_layout.addLayout(grid_layout)

    def apply_style_from_button(self, file_path, filename, is_custom=False):
        """Применяет стиль при клике на кнопку"""
        try:
            file_name_only = os.path.basename(filename) if isinstance(filename, str) else filename
            self.apply_style_file(file_name_only)
            
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка применения стиля {filename}: {e}")
            self.assistant.show_notification_message(f"Ошибка: {str(e)[:50]}...")

    def create_style_button(self, filename, folder_path, is_custom=False):
        """Создает кнопку стиля с предпросмотром цвета"""
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                style_data = json.load(f)

            preview_color = self.extract_preview_color(style_data)
            style_name = os.path.splitext(filename)[0]
            style_name = style_name.replace('_', ' ').replace('-', ' ').title()

            btn = QPushButton(f"{style_name}")
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(10, 5, 10, 5)
            btn_layout.setSpacing(10)

            btn_layout.addStretch()
            btn.setLayout(btn_layout)

            btn_style = self.create_button_style(preview_color)
            btn.setStyleSheet(btn_style)

            if is_custom:
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, f=filename, p=folder_path: self.show_style_context_menu(pos, f, p, btn)
                )
                # Сохраняем оригинальное имя файла в свойстве кнопки
                btn.setProperty("original_filename", filename)
                btn.setProperty("folder_path", folder_path)

            btn.clicked.connect(lambda checked, fp=file_path, fn=filename: 
                            self.apply_style_from_button(fp, fn, is_custom))

            return btn
            
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка создания кнопки для {filename}: {e}")
            btn = QPushButton(filename.replace('.json', ''))
            btn.clicked.connect(lambda: self.apply_style_file(filename))
            return btn

    def extract_preview_color(self, style_data):
        """Извлекает цвет/градиент ТОЛЬКО из BasedColors["svg"]"""
        if "BasedColors" in style_data and "svg" in style_data["BasedColors"]:
            return style_data["BasedColors"]["svg"]
        
        return "#4A90E2"

    def create_button_style(self, color_str):
        """Создает стиль кнопки на основе цвета/градиента"""
        return f"""
            QPushButton {{
                background: {color_str};
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            QPushButton:hover {{
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
        """

    def apply_style_file(self, filename):
        """Применяет стиль из указанного файла, проверяя обе директории."""
        base_presets = get_path('bin', 'color_presets')
        custom_presets = get_path('user_settings', 'presets')

        preset_path = None
        custom_path = os.path.join(custom_presets, filename)
        base_path = os.path.join(base_presets, filename)

        if os.path.exists(custom_path):
            preset_path = custom_path
        elif os.path.exists(base_path):
            preset_path = base_path
        else:
            logger.error(f"Пресет '{filename}' не найден ни в одной из папок.")
            debug_logger.error(f"[SETTINGS-WIDGET] Пресет '{filename}' не найден ни в одной из папок.")
            return

        try:
            with open(preset_path, 'r', encoding='utf-8') as json_file:
                styles = json.load(json_file)

                with open(self.assistant.color_path, 'w') as f:
                    json.dump(styles, f, indent=4)

                self.assistant.styles = styles
                self.assistant.apply_styles()
                self.assistant.check_start_win()
                color_signal.color_changed.emit()
                self.assistant.show_notification_message("Стиль успешно применен!")
                debug_logger.info(f"[SETTINGS-WIDGET] Применён стиль из файла: {filename}")

        except json.JSONDecodeError:
            logger.error(f"Ошибка: файл пресета повреждён ({preset_path}).")
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка: файл пресета повреждён ({preset_path}).")
        except Exception as e:
            logger.error(f"Ошибка загрузки пресета: {e}")
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки пресета: {e}")
            self.assistant.show_notification_message(f"Ошибка загрузки пресета: {e}")

    def show_style_context_menu(self, pos, filename, folder_path, button):
        """Показывает контекстное меню для кастомного стиля"""
        menu = QMenu(self)

        edit_action = QAction("Редактировать название", self)
        edit_action.triggered.connect(lambda: self.edit_style_name(filename, folder_path, button))

        delete_action = QAction("Удалить стиль", self)
        delete_action.triggered.connect(lambda: self.delete_custom_style(filename, folder_path))
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)

        menu.exec_(button.mapToGlobal(pos))

    def edit_style_name(self, filename, folder_path, button):
        """Редактирует название кастомного стиля"""
        current_display_name = button.text()

        dialog = EditDialog(
            self.assistant, 
            title="Редактирование названия стиля", 
            text=current_display_name
        )

        if dialog.exec_() != QDialog.DialogCode.Accepted:
            return
        
        new_name = dialog.get_text().strip()
        
        if not new_name or new_name == current_display_name:
            return

        old_file_path = os.path.join(folder_path, filename)
        new_filename = new_name.lower().replace(' ', '_') + '.json'
        new_file_path = os.path.join(folder_path, new_filename)
        
        try:
            if os.path.exists(new_file_path):
                self.assistant.show_notification_message(f"Файл с именем '{new_name}' уже существует!")
                return

            os.rename(old_file_path, new_file_path)
            button.setText(new_name)
            button.setProperty("original_filename", new_filename)
            self.load_custom_styles()

            update_presets_signal.presets_updated.emit()
            
            self.assistant.show_notification_message(f"Название изменено на: {new_name}")
            
        except FileNotFoundError:
            debug_logger.error(f"[SETTINGS-WIDGET] Файл не найден: {old_file_path}")
            self.assistant.show_notification_message("Ошибка: файл не найден!")
        except PermissionError:
            debug_logger.error(f"[SETTINGS-WIDGET] Нет прав на переименование файла: {old_file_path}")
            self.assistant.show_notification_message("Ошибка: нет прав на изменение файла!")
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка при переименовании файла: {e}")
            self.assistant.show_notification_message(f"Ошибка: {str(e)}")

    def delete_custom_style(self, filename, folder_path):
        """Удаляет кастомный стиль"""
        file_path = os.path.join(folder_path, filename)

        reply = self.assistant.show_message(
            text=f"Вы уверены, что хотите удалить стиль '{filename.replace('.json', '')}'?",
            title="Подтверждение удаления",
            message_type="question",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            debug_logger.info("[SETTINGS-WIDGET] Удаление стиля отменено")
            return
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(file_path)
                self.assistant.show_notification_message(f"Стиль '{filename.replace('.json', '')}' удален")
                self.load_custom_styles()
                update_presets_signal.presets_updated.emit()
                
            except Exception as e:
                debug_logger.error(f"[SETTINGS-WIDGET] Ошибка удаления стиля {filename}: {e}")
                self.assistant.show_notification_message(f"Ошибка удаления: {str(e)[:50]}...")

    def open_color_settings(self):
        """Открывает диалоговое окно для настройки цветов."""
        try:
            color_dialog = ColorSettingsWindow(assistant=self.assistant, parent=self)
            color_dialog.colorChanged.connect(self.assistant.apply_styles)
            color_dialog.exec_()
        except Exception as e:
            logger.error(f"Ошибка при открытии окна настроек цветов: {e}")
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка при открытии окна настроек цветов: {e}")
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
        self._help_initialized = False
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
            debug_logger.error("[SETTINGS-WIDGET] Метод close_settings не найден в assistant")
            
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        # Создаем виджет-контейнер для содержимого
        content_widget = QWidget()
        # content_widget.setMaximumWidth(420)
        content_widget.setObjectName("WMSettingsContent")
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
        self.name_input.setText(self.assistant.assistant_name)
        self.name_input.setProperty("helpId", "name_label")
        layout.addWidget(self.name_input)

        # Поле для ввода имени №2
        name2_label = setup_custom_font_label("Дополнительно:")
        name2_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        name2_label.setStyleSheet("background: transparent; font-size: 14px;")
        name2_label.setProperty("helpId", "name2_label")
        layout.addWidget(name2_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name2_input = QLineEdit(self)
        self.name2_input.setText(self.assistant.assist_name2)
        self.name2_input.setProperty("helpId", "name2_label")
        layout.addWidget(self.name2_input)

        # Поле для ввода имени №3
        self.name3_input = QLineEdit(self)
        self.name3_input.setText(self.assistant.assist_name3)
        self.name3_input.setProperty("helpId", "name2_label")
        layout.addWidget(self.name3_input)

        # Выбор голоса
        voice_label = setup_custom_font_label("Выберите голос:")
        voice_label.setStyleSheet("background: transparent; font-size: 14px;")
        voice_label.setProperty("helpId", "voice_label")
        layout.addWidget(voice_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems(list(speakers.keys()))
        current_key = next(key for key, value in speakers.items() if value == self.assistant.speaker)
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
        self.volume_slider.setValue(int(self.assistant.volume_assist * 100))
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
        self.steam_path_input.setText(self.assistant.steam_path)
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
        self.assistant.volume_assist = value / 100.0
        self.assistant.save_settings()

    def select_steam_folder(self):
        folder_path = QSlider.getExistingDirectory(
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
            debug_logger.error(f"[SETTINGS-WIDGET] При тесте голоса произошла ошибка:{e}")

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
            "steam_path": "",
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

        # if not os.path.isfile(new_steam_path):
        #     self.assistant.show_message(f"Укажите правильный путь к steam.exe", "Предупреждение", "warning")
        #     return

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
        self._help_initialized = False
        self.init_ui()
        self.get_devices()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        content_widget = QWidget()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title = setup_custom_font_label("Дополнительные настройки")
        self.title.setStyleSheet("background: transparent; font-size: 18px")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Чекбоксы
        self.censor_check = CustomToggle("Реагировать на мат")
        self.censor_check.setStyleSheet("background: transparent;")
        self.censor_check.setChecked(self.assistant.is_censored)
        self.censor_check.stateChanged.connect(self.toggle_censor)
        self.censor_check.setProperty("helpId", "censor_check")
        layout.addWidget(self.censor_check)
        
        self.correct_command_check = CustomToggle("Запоминать предыдущую команду")
        self.correct_command_check.setStyleSheet("background: transparent;")
        self.correct_command_check.setChecked(self.assistant.is_corrected_command)
        self.correct_command_check.stateChanged.connect(self.toggle_correct_command)
        self.correct_command_check.setProperty("helpId", "correct_command_check")
        layout.addWidget(self.correct_command_check)

        self.update_check = CustomToggle("Запуск утилиты обновления \n перед стартом программы")
        self.update_check.setStyleSheet("background: transparent;")
        self.update_check.setChecked(self.assistant.run_updater)
        self.update_check.stateChanged.connect(self.toggle_update)
        self.update_check.setProperty("helpId", "update_check")
        layout.addWidget(self.update_check)

        self.start_win_check = CustomToggle("Запуск с Windows")
        self.start_win_check.setStyleSheet("background: transparent;")
        self.start_win_check.setChecked(self.assistant.toggle_start)
        self.start_win_check.stateChanged.connect(self.assistant.toggle_start_win)
        self.start_win_check.setProperty("helpId", "start_win_check")
        layout.addWidget(self.start_win_check)

        # Чекбокс для сворачивания в трей
        self.minimize_check = CustomToggle("Сворачивать в трей при запуске")
        self.minimize_check.setStyleSheet("background: transparent;")
        self.minimize_check.setChecked(self.assistant.is_min_tray)
        self.minimize_check.stateChanged.connect(self.toggle_minimize)
        self.minimize_check.setProperty("helpId", "minimize_check")
        layout.addWidget(self.minimize_check)

        self.widget_check = CustomToggle("Запускать виджет")
        self.widget_check.setStyleSheet("background: transparent;")
        self.widget_check.setToolTip("Открытие виджета при запуске программы")
        self.widget_check.setChecked(self.assistant.is_widget)
        self.widget_check.stateChanged.connect(self.toggle_widget)
        self.widget_check.setProperty("helpId", "widget_check")
        layout.addWidget(self.widget_check)

        self.keep_watch_check = CustomToggle("Обрабатывать команды \nбез имени ассистента"
                                          "\n(возможны ложные срабатывания)")
        self.keep_watch_check.setStyleSheet("background: transparent;")
        self.keep_watch_check.setToolTip("Расширенная обработка команд")
        self.keep_watch_check.setChecked(self.assistant.is_keep_watch)
        self.keep_watch_check.stateChanged.connect(self.toggle_keep_watch)
        self.keep_watch_check.setProperty("helpId", "keep_watch_check")
        layout.addWidget(self.keep_watch_check)
        
        self.snow_check = CustomToggle("Снег на главном окне")
        self.snow_check.setStyleSheet("background: transparent;")
        self.snow_check.setToolTip("Показывать снег на главном окне")
        self.snow_check.setChecked(self.assistant.is_snow)
        self.snow_check.stateChanged.connect(self.toggle_snow_main)
        self.snow_check.setProperty("helpId", "snow_check")
        layout.addWidget(self.snow_check)
        
        self.garland_check = CustomToggle("Гирлянда на главном окне")
        self.garland_check.setStyleSheet("background: transparent;")
        self.garland_check.setToolTip("Показывать гирлянду")
        self.garland_check.setChecked(self.assistant.is_garland)
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
        
    def toggle_snow_main(self):
        self.assistant.is_snow = self.snow_check.isChecked()
        self.assistant.save_settings()
        self.assistant.update_snow_state()
        
    def toggle_garland_main(self):
        self.assistant.is_garland = self.garland_check.isChecked()
        self.assistant.save_settings()
        self.assistant.update_garland_state()

    def toggle_censor(self):
        self.assistant.is_censored = self.censor_check.isChecked()
        self.assistant.save_settings()

    def toggle_update(self):
        self.assistant.run_updater = self.update_check.isChecked()
        self.assistant.save_settings()
        
    def toggle_correct_command(self):
        self.assistant.is_corrected_command = self.correct_command_check.isChecked()
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
                debug_logger.info(f"[SETTINGS-WIDGET] Ярлык создан на рабочем столе: {desktop_shortcut}")
            else:
                debug_logger.error(f"[SETTINGS-WIDGET] Ярлык на рабочем столе уже существует: {desktop_shortcut}")

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
                debug_logger.info(f"[SETTINGS-WIDGET] Ярлык создан в меню 'Пуск': {startup_shortcut}")
            else:
                debug_logger.error(f"[SETTINGS-WIDGET] Ярлык в меню 'Пуск' уже существует: {startup_shortcut}")

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
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка при получении данных аудиоустройств: {str(e)}")

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
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка в проверке активных микрофонов: {str(e)}")

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

            debug_logger.info(f"[SETTINGS-WIDGET] Выбрано устройство: '{device_name}' (ID={device_id})")

    def hide_method(self):
        """Закрывает панель настроек через главный класс"""
        if hasattr(self.assistant, 'hide_widget'):
            self.assistant.hide_widget()
        else:
            debug_logger.error("[SETTINGS-WIDGET] Метод close_settings не найден в assistant")     
            
class SpeechHookManagerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        self.default_path = get_path("bin", "default_keywords.json")
        self.user_path = get_path("user_settings", "keywords.json")
        self.default_keywords = {}
        self.user_keywords = {}
        self.current_list = None
        self._help_initialized = False
        self.init_data()
        self.init_ui()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True
    
    def init_ui(self):
        """Инициализация интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем скроллируемую область
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Создаем виджет для контента
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        # Создаем layout для контента
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.title = setup_custom_font_label("Менеджер управления хук-словами")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Выбор списка команд
        list_selection_layout = QHBoxLayout()
        
        self.list_selector = QComboBox()
        # Заполняем выпадающий список читаемыми названиями
        sorted_keys = sorted(self.user_keywords.keys(), key=lambda k: self.get_display_name(k))
        for key in sorted_keys:
            self.list_selector.addItem(self.get_display_name(key), key)
    
        self.list_selector.currentIndexChanged.connect(self.on_list_changed)
        self.list_selector.setProperty("helpId", "list_selector")
        list_selection_layout.addWidget(self.list_selector)
        
        layout.addLayout(list_selection_layout)

        # Список слов
        self.words_list = QListWidget()
        self.words_list.setStyleSheet("font-size: 15px;")
        self.words_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.words_list.customContextMenuRequested.connect(self.show_context_menu)
        self.words_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.words_list.setProperty("helpId", "words_list")
        layout.addWidget(self.words_list)

        # Добавление нового слова
        add_word_layout = QHBoxLayout()
        self.new_word_input = QLineEdit()
        self.new_word_input.setPlaceholderText("Введите новое слово-команду...")
        self.new_word_input.returnPressed.connect(self.add_new_word)
        
        self.add_button = QPushButton("Добавить")
        self.add_button.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.add_button.clicked.connect(self.add_new_word)
        
        add_word_layout.addWidget(self.new_word_input)
        add_word_layout.addWidget(self.add_button)
        layout.addLayout(add_word_layout)
        
        layout.addStretch()

        # Кнопка сброса
        self.reset_button = QPushButton("Сбросить к значениям по умолчанию")
        self.reset_button.clicked.connect(self.reset_to_default)
        self.reset_button.setProperty("helpId", "reset_words_list")
        layout.addWidget(self.reset_button)

        # Добавляем скролл в основной layout
        main_layout.addWidget(scroll_area)
        
        # Загружаем первый список
        if sorted_keys:
            self.current_list = sorted_keys[0]
            self.load_current_list()
        
    def init_data(self):
        """Инициализация данных из файлов"""    
        # Загружаем дефолтные значения
        if os.path.exists(self.default_path):
            with open(self.default_path, 'r', encoding='utf-8') as f:
                self.default_keywords = json.load(f)
        else:
            # Если файла нет, создаем из переменных (временное решение)
            self.create_default_file()
            
        # Загружаем пользовательские значения
        if os.path.exists(self.user_path):
            with open(self.user_path, 'r', encoding='utf-8') as f:
                self.user_keywords = json.load(f)
        else:
            # Если файла нет, копируем дефолтные значения
            self.user_keywords = self.default_keywords.copy()
            self.save_user_keywords()
            
    def create_default_file(self):
        """Создает дефолтный файл (временно, пока не перенесете переменные)"""
        self.default_keywords = default_keywords_data

        with open(self.default_path, 'w', encoding='utf-8') as f:
            json.dump(self.default_keywords, f, ensure_ascii=False, indent=2)
            
    def save_user_keywords(self):
        """Сохраняет пользовательские настройки"""
        with open(self.user_path, 'w', encoding='utf-8') as f:
            json.dump(self.user_keywords, f, ensure_ascii=False, indent=2)
        self.assistant.apply_keywords_for_values()
    
    def get_display_name(self, key):
        """Преобразует имя списка в читаемое название"""
        names = {
            "keywords_shutdown": "Выключение компьютера",
            "keywords_restart": "Перезагрузка компьютера", 
            "keywords_search": "Поиск",
            "keywords_yes": "Команды 'Да'",
            "keywords_no": "Команды 'Нет'", 
            "keywords_reject": "Отмена",
            "screen_list": "Вызов скриншота с выбором области",
            "fullscreen_list": "Вызов скриншота в режиме фуллскрин", 
            "action_up": "Команды для открытия",
            "action_down": "Команды для закрытия",
            "keywords_player": "Управление плеером",
            "keywords_playpause": "Пауза/старт для плеера", 
            "keywords_next": "Следующий трек",
            "keywords_prev": "Предыдущий трек",
            "censored_list": "Цензурный список",
        }
        return names.get(key, key.replace("keywords_", "").replace("_", " ").title())
    
    def on_list_changed(self, index):
        """Обработчик смены выбранного списка"""
        if index >= 0:
            self.current_list = self.list_selector.itemData(index)
            self.load_current_list()

    def load_current_list(self):
        """Загружает слова текущего выбранного списка"""
        self.words_list.clear()
        if self.current_list and self.current_list in self.user_keywords:
            for word in self.user_keywords[self.current_list]:
                item = QListWidgetItem(word)
                self.words_list.addItem(item)

    def show_context_menu(self, position):
        """Показывает контекстное меню для элемента списка"""
        item = self.words_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        edit_action = menu.addAction("Изменить")
        delete_action = menu.addAction("Удалить")
        
        action = menu.exec_(self.words_list.mapToGlobal(position))
        
        if action == edit_action:
            self.edit_word(item)
        elif action == delete_action:
            self.delete_word(item)

    def on_item_double_clicked(self, item):
        """Обработчик двойного клика по элементу"""
        self.edit_word(item)

    def edit_word(self, item):
        """Редактирование слова с использованием кастомного диалога"""
        old_word = item.text()
        
        # Получаем текущий список слов для проверки дубликатов
        current_words = self.user_keywords[self.current_list]
        
        dialog = EditCommandDialog(
            current_word=old_word,
            existing_words=current_words,
            parent=self
        )
        
        if dialog.exec_() == QDialog.Accepted:
            new_word = dialog.get_new_word()
            
            # Обновляем в данных
            word_list = self.user_keywords[self.current_list]
            index = word_list.index(old_word)
            word_list[index] = new_word
            
            # Сохраняем и обновляем интерфейс
            self.save_user_keywords()
            self.load_current_list()

    def delete_word(self, item):
        """Удаление слова"""
        word = item.text()
        reply = self.assistant.show_message(
            text="Точно удалить?",
            title="Подтверждение",
            message_type="warning",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.Yes:
            # Удаляем из данных
            self.user_keywords[self.current_list].remove(word)
            
            # Сохраняем и обновляем интерфейс
            self.save_user_keywords()
            self.load_current_list()

    def add_new_word(self):
        """Добавление нового слова"""
        new_word = self.new_word_input.text().strip()
        if not new_word:
            return
            
        if new_word in self.user_keywords[self.current_list]:
            self.assistant.show_notification_message("Такое слово уже есть в списке!")
            return
            
        # Добавляем в данные
        self.user_keywords[self.current_list].append(new_word)
        
        # Сохраняем и обновляем интерфейс
        self.save_user_keywords()
        self.load_current_list()
        
        # Очищаем поле ввода
        self.new_word_input.clear()

    def reset_to_default(self):
        """Сброс к значениям по умолчанию"""
        reply = self.assistant.show_message(
            text="Откатиться к дефолтным значениям?",
            title="Подтверждение",
            message_type="warning",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Восстанавливаем дефолтные значения
            self.user_keywords = self.default_keywords.copy()
            
            # Сохраняем и обновляем интерфейс
            self.save_user_keywords()
            self.load_current_list()
            
            self.assistant.show_notification_message("Команды сброшены к значениям по умолчанию!")
            

class EditCommandDialog(QDialog):
    """Кастомное диалоговое окно для редактирования слов-команд"""

    def __init__(self, current_word="", existing_words=None, parent=None):
        super().__init__(parent)
        self.current_word = current_word
        self.existing_words = existing_words or []  # Список существующих слов в текущей категории
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(320, 150)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.init_ui()

    def init_ui(self):
        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        # Основной контейнер
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        self.container.setGeometry(0, 0, self.width(), self.height())

        # Кастомный заголовок
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setGeometry(1, 1, self.width() - 2, 35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 5, 10, 5)
        self.title_layout.setSpacing(5)

        title_text = "Добавление команды" if not self.current_word else "Редактирование команды"
        self.title_label = QLabel(title_text, self.title_bar)
        self.title_label.setStyleSheet("background: transparent")
        self.title_label.setGeometry(10, 5, 200, 20)
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton("✕", self.title_bar)
        self.close_btn.setFixedSize(25, 25)
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.reject)
        self.title_layout.addWidget(self.close_btn)

        # Основное содержимое
        self.content_widget = QWidget(self.container)
        self.content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)
        self.content_widget.setObjectName("ContentWidget")

        # Поле ввода
        self.input_field = QLineEdit(self.content_widget)
        placeholder = "Введите новую команду..." if not self.current_word else "Введите команду..."
        self.input_field.setPlaceholderText(placeholder)
        
        if self.current_word:
            self.input_field.setText(self.current_word)
            self.input_field.selectAll()

        # Label для ошибок
        self.error_label = QLabel(self.content_widget)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")
        self.error_label.setVisible(False)

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
        main_layout.setSpacing(10)

        main_layout.addWidget(self.input_field)
        main_layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        # Подключаем Enter для быстрого сохранения
        self.input_field.returnPressed.connect(self.try_accept)

    def try_accept(self):
        """Пытается закрыть окно, если ввод корректен."""
        new_word = self.get_text()

        if not new_word:
            self.show_error("Команда не может быть пустой!")
            return

        # Проверяем, не совпадает ли новое слово с текущим (при редактировании)
        if new_word == self.current_word:
            self.reject()  # Если не изменилось, просто закрываем
            return

        # Проверяем, не существует ли уже такой команды в этой категории
        if new_word in self.existing_words:
            self.show_error(f"Команда '{new_word}' уже есть в этом списке!")
            return

        # Сохраняем новое слово
        self.new_word = new_word
        self.accept()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_text(self):
        """Возвращает очищенный текст из поля ввода."""
        return self.input_field.text().strip()

    def get_new_word(self):
        """Возвращает новое слово после принятия диалога."""
        return getattr(self, 'new_word', self.current_word)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.try_accept()
        else:
            super().keyPressEvent(event)

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


class DraggableCheckbox(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_mode_enabled = False
        self.is_dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.original_pos = None

        # Добавляем кастомные атрибуты
        self.is_custom = False
        self.custom_data = None
        self.custom_id = None
        
        # Контекстное меню для кастомных кнопок
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, pos):
        """Показывает контекстное меню только для кастомных кнопок"""
        if not self.is_custom:
            return
            
        menu = QMenu(self)

        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(self.edit_custom)
        menu.addAction(edit_action)
        
        delete_action = QAction("Удалить кнопку", self)
        delete_action.triggered.connect(self.delete_custom)
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))
    
    def delete_custom(self):
        """Удаляет кастомную кнопку"""
        parent = self.parent()
        while parent and not hasattr(parent, 'delete_custom_button_by_id'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'delete_custom_button_by_id'):
            parent.delete_custom_button_by_id(self.custom_id)

    def edit_custom(self):
        parent = self.parent()
        while parent and not hasattr(parent, 'edit_custom_button_by_id'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'edit_custom_button_by_id'):
            parent.edit_custom_button_by_id(self.custom_id)

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
        self.state_manager = WindowStateManager()
        self.loaded_state = self.state_manager.load_state()
        self.is_snow = self.loaded_state["is_snow"]
        self.drag_mode = False
        self._help_initialized = False
        self.fonts_list = fonts_list
        self.init_ui()
        self.load_saved_font()
        self.load_buttons_settings()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title = setup_custom_font_label("Кастомизация виджета",)
        self.title.setStyleSheet("background: transparent; font-size: 18px")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кнопка для включения/выключения режима перетаскивания
        self.drag_toggle_btn = QPushButton("Настроить порядок расположения")
        self.drag_toggle_btn.clicked.connect(self.toggle_drag_mode)
        self.drag_toggle_btn.setProperty("helpId", "drag_toggle_btn")
        layout.addWidget(self.drag_toggle_btn)

        drag_layout = QVBoxLayout()

        self.drag_container = DragContainer()
        self.drag_container.setProperty("helpId", "drag_toggle_btn")
        self.drag_container.setStyleSheet("background: transparent")
        self.drag_container.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.drag_container.layout.setSpacing(10)
        self.drag_container.layout.setContentsMargins(5, 5, 5, 5)

        drag_layout.addWidget(self.drag_container)

        layout.addLayout(drag_layout)

        self.add_custom_btn = QPushButton("Добавить кастомную кнопку")
        self.add_custom_btn.setProperty("helpId", "add_custom_btn")
        self.add_custom_btn.clicked.connect(self.show_create_custom_widget)
        layout.addWidget(self.add_custom_btn)

        font_layout = QHBoxLayout()

        # Лейбл с временем для демонстрации шрифта
        self.font_preview_label = QLabel("12:34")
        self.font_preview_label.setObjectName("preview_clock")
        self.font_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_preview_label.setStyleSheet("background: transparent; padding: 5px;")

        self.font_combo = NonClosingComboBox()
        self.font_combo.setProperty("helpId", "font_combo")
        self.font_combo.addItems(self.fonts_list.keys())
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(self.font_preview_label)
        layout.addLayout(font_layout)
        self.setup_font_selector()
        
        self.toggles_label = setup_custom_font_label("Прочие параметры")
        self.toggles_label.setStyleSheet("background: transparent; font-size: 16px")
        layout.addWidget(self.toggles_label)

        self.delay_layout = QHBoxLayout()


        self.delay_label = QLabel("Задержка перед скрытием кнопок:")
        self.delay_label.setStyleSheet("background: transparent;")
        self.delay_label.setProperty("helpId", "delay_label")
        self.delay_layout.addWidget(self.delay_label)

        self.txt_delay = QLineEdit()
        self.txt_delay.setProperty("helpId", "delay_label")
        self.txt_delay.setFixedSize(50, 30)
        self.txt_delay.setPlaceholderText("10")
        self.txt_delay.setText(str(self.load_saved_delay()))

        # Добавляем валидатор для чисел с плавающей точкой
        regex = QRegularExpression(r'^(\d{1,2}(\.\d)?|\.\d)$')
        validator = QRegularExpressionValidator(regex, self)
        self.txt_delay.setValidator(validator)
        self.delay_layout.addWidget(self.txt_delay)
        self.delay_layout.addStretch()

        layout.addLayout(self.delay_layout)
        
        self.snow_panel_checkbox = CustomToggle("Частицы снега на панели")
        self.snow_panel_checkbox.setStyleSheet("background: transparent;")
        self.snow_panel_checkbox.setToolTip("Показывать снег на панели")
        self.snow_panel_checkbox.setChecked(self.is_snow)
        self.snow_panel_checkbox.stateChanged.connect(self.toggle_snow)
        self.snow_panel_checkbox.setProperty("helpId", "snow_panel_checkbox")
        layout.addWidget(self.snow_panel_checkbox)
        
        layout.addStretch()
        
        bottom_layout = QHBoxLayout()
        
        self.get_widget_btn = QPushButton("Открыть виджет", self)
        self.get_widget_btn.setStyleSheet("padding-left: 10px; padding-right: 10px")
        self.get_widget_btn.clicked.connect(self.get_widget)
        bottom_layout.addWidget(self.get_widget_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        bottom_layout.addStretch()
        
        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setStyleSheet("padding-left: 10px; padding-right: 10px")
        self.default_btn.clicked.connect(self.set_default_buttons_settings)
        bottom_layout.addWidget(self.default_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(bottom_layout)

        self.save_btn = QPushButton("Применить")
        self.save_btn.clicked.connect(self.save_order)
        layout.addWidget(self.save_btn)

        main_layout.addWidget(scroll_area)

    def get_widget(self):
        self.assistant.open_widget()
        
    def toggle_snow(self):
        self.is_snow = self.snow_panel_checkbox.isChecked()
        self.state_manager.update_value("is_snow", self.is_snow)

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

        debug_logger.info(f"[SETTINGS-WIDGET] Применение шрифта для превью: {font_family} с размером: {font_size}")

        styles = f"""
            #preview_clock {{
                font-family: "{font_family}";
                font-size: {font_size};
                font-weight: normal;
                padding: 0px;
                background: transparent;
            }}
        """

        if self.font_preview_label.objectName() != "preview_clock":
            self.font_preview_label.setObjectName("preview_clock")

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
            debug_logger.warning(f"[SETTINGS-WIDGET] Не удалось загрузить сохраненный шрифт: {e}")
            # Устанавливаем шрифт по умолчанию
            default_index = self.font_combo.findText("digital")
            if default_index >= 0:
                self.font_combo.setCurrentIndex(default_index)

    def load_saved_delay(self):
        with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)

        if "delay" in data:
            delay = data["delay"]
        else:
            delay = 10

        return delay

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

        for i in range(self.drag_container.layout.count()):
            widget = self.drag_container.layout.itemAt(i).widget()
            
            if widget and isinstance(widget, DraggableCheckbox):
                # Находим ключ
                for key, checkbox in self.checkboxes.items():
                    if checkbox == widget:
                        buttons_data[key] = checkbox.isChecked()
                        break

        return buttons_data
    
    def reorder_checkboxes_by_buttons(self, buttons_order):
        """Переставляет чекбоксы в порядке из buttons"""
        # Удаляем все из layout
        for i in reversed(range(self.drag_container.layout.count())):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget:
                self.drag_container.layout.removeWidget(widget)
        
        # Добавляем обратно в порядке из buttons
        for key in buttons_order.keys():
            if key in self.checkboxes:
                checkbox = self.checkboxes[key]
                self.drag_container.layout.addWidget(checkbox)

    def load_buttons_settings(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            default_buttons = settings_data.get("default_buttons", {})
            buttons_states = settings_data.get("buttons", {})
            custom_buttons = settings_data.get("custom_buttons", [])

            # Очищаем
            self.checkboxes.clear()
            for i in reversed(range(self.drag_container.layout.count())):
                widget = self.drag_container.layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            # 1. Создаем ВСЕ возможные кнопки
            
            # Стандартные кнопки
            for key, btn_data in default_buttons.items():
                text = btn_data.get('tooltip', key)
                checkbox = DraggableCheckbox(text)
                self.checkboxes[key] = checkbox
            
            # Кастомные кнопки
            for custom_data in custom_buttons:
                key = f"custom_{custom_data['id']}"
                checkbox = DraggableCheckbox(custom_data['name'])
                checkbox.is_custom = True
                checkbox.custom_data = custom_data
                checkbox.custom_id = custom_data['id']
                self.checkboxes[key] = checkbox

            # 2. Обновляем buttons_states чтобы включить ВСЕ кнопки
            updated_buttons_states = buttons_states.copy()
            
            for key in self.checkboxes.keys():
                if key not in updated_buttons_states:
                    updated_buttons_states[key] = True
            
            # Если добавились новые кнопки - сохраняем
            if updated_buttons_states != buttons_states:
                settings_data["buttons"] = updated_buttons_states
                with open(self.widget_state, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, indent=4, ensure_ascii=False)
            
            # 3. Добавляем ВСЕ чекбоксы в layout и устанавливаем состояния
            # Порядок: сначала стандартные как в default_buttons, потом кастомные
            
            # Сначала стандартные в порядке из default_buttons
            for key in default_buttons.keys():
                if key in self.checkboxes:
                    checkbox = self.checkboxes[key]
                    state = updated_buttons_states.get(key, True)
                    checkbox.setChecked(state)
                    self.drag_container.layout.addWidget(checkbox)
            
            # Потом кастомные в порядке из custom_buttons
            for custom_data in custom_buttons:
                key = f"custom_{custom_data['id']}"
                if key in self.checkboxes:
                    checkbox = self.checkboxes[key]
                    state = updated_buttons_states.get(key, True)
                    checkbox.setChecked(state)
                    self.drag_container.layout.addWidget(checkbox)

            if buttons_states:
                self.reorder_checkboxes_by_buttons(buttons_states)
            return True

        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки кнопок: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def default_list(self):
        data = {
            "default_buttons": {
                "turnoff_check": {
                    "tooltip": "Выключение компьютера",
                    "icon_rel_path": "power.svg"
                },
                "settings_check": {
                    "tooltip": "Открыть настройки",
                    "icon_rel_path": "settings.svg"
                },
                "screenshot_check": {
                    "tooltip": "Сделать скриншот",
                    "icon_rel_path": "camera.svg"
                },
                "open_youtube": {
                    "tooltip": "Запустить YouTube",
                    "icon_rel_path": "logo-youtube.svg"
                },
                "microphone_check": {
                    "tooltip": "Управление микрофоном в Discord",
                    "icon_rel_path": "mic_on.svg"
                },
                "links_check": {
                    "tooltip": "Открыть папку с ярлыками",
                    "icon_rel_path": "shortcut.svg"
                },
                "resize_check": {
                    "tooltip": "Развернуть окно ассистента",
                    "icon_rel_path": "open_main.svg"
                }
            }
        }
        return data

    def set_default_buttons_settings(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            
            default_buttons = settings_data.get("default_buttons", {})
            custom_buttons = settings_data.get("custom_buttons", [])
            
            # Создаем дефолтные состояния
            new_buttons = {}
            
            # Стандартные = True
            for key in default_buttons.keys():
                new_buttons[key] = True
            
            # Кастомные = False
            for custom_data in custom_buttons:
                key = f"custom_{custom_data['id']}"
                new_buttons[key] = False
            
            # Сохраняем
            settings_data["buttons"] = new_buttons
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False)
            
            # Перезагружаем
            self.load_buttons_settings()
            
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка сброса настроек: {e}")

    def save_order(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            existing_data["delay"] = float(self.txt_delay.text().strip())

            existing_data["font_family"] = self.font_combo.currentText()
            
            existing_data["buttons"] = self.get_buttons_data()

            if "custom_buttons" not in existing_data:
                current_custom_buttons = []
                for key, checkbox in self.checkboxes.items():
                    if key.startswith('custom_') and hasattr(checkbox, 'custom_data'):
                        current_custom_buttons.append(checkbox.custom_data)
                existing_data["custom_buttons"] = current_custom_buttons
            
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            
            QTimer.singleShot(100, widget_btns_signal.buttons_updated.emit)
            
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка сохранения порядка: {e}")

    def show_create_custom_widget(self):
        """Показывает виджет создания кастомной кнопки"""
        all_commands = {**self.assistant.default_commands, **self.assistant.commands}
        self.create_widget = CustomBtnForPanel(
            parent=self,
            commands=all_commands
        )
        self.create_widget.custom_button_created.connect(self.add_custom_button)
        self.create_widget.show()

    def load_custom_buttons(self):
        """Загружает сохраненные кастомные кнопки"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            
            # Добавляем кастомные кнопки
            for button_data in custom_buttons:
                self.add_custom_button(button_data)
                
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки кастомных кнопок: {e}")

    

    def add_custom_button(self, button_data):
        """Добавляет кастомную кнопку в список"""
        key = f"custom_{button_data['id']}"
        
        checkbox = DraggableCheckbox(button_data['name'])
        
        # Устанавливаем кастомные атрибуты
        checkbox.is_custom = True
        checkbox.custom_data = button_data
        checkbox.custom_id = button_data['id']
        
        self.checkboxes[key] = checkbox
        self.drag_container.layout.addWidget(checkbox)

    def delete_custom_button_by_id(self, custom_id):
        """Удаляет кастомную кнопку по ID"""
        key = f"custom_{custom_id}"
        
        if key in self.checkboxes:
            checkbox = self.checkboxes[key]
            
            # Удаляем из layout
            self.drag_container.layout.removeWidget(checkbox)
            checkbox.deleteLater()
            
            # Удаляем из словаря
            del self.checkboxes[key]
            
            # Удаляем из JSON
            self.remove_btn_from_json(custom_id)
            
            self.save_order()

    def edit_custom_button_by_id(self, custom_id):
        """Открывает диалоговое окно для изменения параметров кнопки"""
        
        # Находим данные кнопки для редактирования
        button_data = None
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            for btn in custom_buttons:
                if btn.get('id') == custom_id:
                    button_data = btn
                    break
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки данных кнопки: {e}")
        
        if not button_data:
            self.assistant.show_message("Кнопка не найдена", "Ошибка", "warning")
            return
        
        # Открываем диалог с данными кнопки для редактирования
        all_commands = {**self.assistant.default_commands, **self.assistant.commands}
        self.edit_widget = CustomBtnForPanel(
            parent=self,
            commands=all_commands,
            button_data=button_data  # Передаем данные для заполнения полей
        )
        self.edit_widget.custom_button_edited.connect(self.handle_custom_button_edited)
        self.edit_widget.show()

    def handle_custom_button_edited(self, edited_button_data):
        """Обрабатывает отредактированную кнопку"""
        custom_id = edited_button_data['id']
        key = f"custom_{custom_id}"
        
        if key in self.checkboxes:
            # Обновляем текст в чекбоксе
            checkbox = self.checkboxes[key]
            checkbox.setText(edited_button_data['name'])
            checkbox.custom_data = edited_button_data
            
            # Обновляем данные в JSON
            self.update_button_in_json(edited_button_data)
            
            # Сохраняем порядок
            self.save_order()

    def update_button_in_json(self, button_data):
        """Обновляет кнопку в JSON файле"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            
            # Находим и заменяем кнопку с таким же ID
            for i, btn in enumerate(custom_buttons):
                if btn.get('id') == button_data['id']:
                    custom_buttons[i] = button_data
                    break
            
            data['custom_buttons'] = custom_buttons
            
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка обновления кнопки в JSON: {e}")


    def remove_btn_from_json(self, custom_id):
        """Удаляет кастомную кнопку из JSON файла"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Получаем список кастомных кнопок
            custom_buttons = data.get('custom_buttons', [])
            
            # Фильтруем, оставляем только те, у которых id не совпадает
            if isinstance(custom_buttons, list):
                data['custom_buttons'] = [
                    btn for btn in custom_buttons 
                    if btn.get('id') != custom_id
                ]
            elif isinstance(custom_buttons, dict):
                # Если вдруг сохранено как словарь
                if custom_id in custom_buttons:
                    del custom_buttons[custom_id]
            
            # Сохраняем обратно
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка удаления кастомной кнопки из JSON: {e}")


class CustomBtnForPanel(QDialog):
    """Виджет для создания/редактирования кастомной кнопки"""
    custom_button_created = Signal(dict)
    custom_button_edited = Signal(dict)

    def __init__(self, parent=None, commands=None, button_data=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.drag_pos = None
        self.button_data = button_data  # Данные редактируемой кнопки (если есть)
        self.is_edit = button_data is not None
        self.btn_icons_folder = get_path("bin", "icons", "script-icons")
        self.user_icons_folder = get_path("user_settings", "user-icons")
        self.check_folder(folder_path=[self.user_icons_folder, self.btn_icons_folder])
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.widget_state = get_path("user_settings", "widget_state.json")
        self.commands = commands or {}
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.monitor = ShortcutMonitor(self.user_icons_folder)
        self.monitor.folder_changed.connect(self.load_svg_list)
        self.monitor.start_monitoring()
        self.init_ui()
        self.load_svg_list()
        self.apply_styles()
        if self.is_edit:
            self.fill_with_button_data()

    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPos() - self.drag_pos
            self.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

    def apply_styles(self):
        if hasattr(self, 'close_svg'):
            self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#ff0000")
    
    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(360, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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

        if self.is_edit:
            self.title_label = setup_custom_font_label("Редактирование кнопки")
        else:
            self.title_label = setup_custom_font_label("Создание кастомной кнопки")
        self.title_label.setStyleSheet("background: transparent; font-size:16px;")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton("", self.title_bar)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)

        # Основной контент
        self.content_widget = QWidget(self.container)
        self.content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)
        self.content_widget.setObjectName("ContentWidget")

        self.main_content_layout = QVBoxLayout(self.content_widget)
        self.main_content_layout.setContentsMargins(15, 15, 15, 15)
        self.main_content_layout.setSpacing(5)

        # Выпадающий список SVG с иконками
        icon_layout = QHBoxLayout()

        self.preview_svg = CustomSvgWidget("")
        self.preview_svg.setFixedSize(30, 30)
        icon_layout.addWidget(self.preview_svg) 

        self.icon_combo = NonClosingComboBox()
        self.icon_combo.currentIndexChanged.connect(self.update_preview)
        icon_layout.addWidget(self.icon_combo)

        self.main_content_layout.addLayout(icon_layout)

        self.name_label = setup_custom_font_label("Назначение кнопки")
        self.name_label.setStyleSheet("background: transparent; font-style: 14px;")
        self.main_content_layout.addWidget(self.name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: Запуск скрипта")
        self.main_content_layout.addWidget(self.name_input)
        
        # Выбор команды
        self.command_label = setup_custom_font_label("Команда:")
        self.command_label.setStyleSheet("background: transparent; font-style: 14px;")
        self.main_content_layout.addWidget(self.command_label)

        self.command_combo = QComboBox()
        self.command_combo.addItems(list(self.commands.keys()))
        self.main_content_layout.addWidget(self.command_combo)

        action_layout = QHBoxLayout()
        
        lbl_action = QLabel("Действие:")
        lbl_action.setStyleSheet("background: transparent;")
        action_layout.addWidget(lbl_action)
        
        self.cmb_action = QComboBox()
        self.cmb_action.addItems(["open", "close"])
        action_layout.addWidget(self.cmb_action)
        
        self.main_content_layout.addLayout(action_layout)

        # Label для ошибок
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")
        self.error_label.setVisible(False)
        self.main_content_layout.addWidget(self.error_label)

        self.main_content_layout.addStretch()
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.open_script_folder = QPushButton("Папка с иконками")
        self.open_script_folder.clicked.connect(lambda: self.open_folder(path=self.user_icons_folder))
        self.open_script_folder.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_layout.addWidget(self.open_script_folder)

        btn_layout.addStretch()

        if self.is_edit:
            self.save_btn = QPushButton("Сохранить")
            self.save_btn.clicked.connect(self.save_button)
        else:
            self.save_btn = QPushButton("Создать")
            self.save_btn.clicked.connect(self.save_button)
        self.save_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)
        
        self.main_content_layout.addLayout(btn_layout)
    
    def load_svg_list(self):
        """Загружает SVG файлы из папки"""
        self.icon_combo.clear()
        self.icon_paths = {}  # Словарь для быстрого поиска индекса по пути

        if os.path.exists(self.btn_icons_folder):
            svg_files = []
            
            for file in sorted(os.listdir(self.btn_icons_folder)):
                if file.lower().endswith('.svg'):
                    svg_files.append(file)
            
            if svg_files:
                for svg_file in svg_files:
                    icon_name = os.path.splitext(svg_file)[0]
                    icon_path = os.path.join(self.btn_icons_folder, svg_file)
                    self.icon_combo.addItem(icon_name, icon_path)
                    self.icon_paths[icon_path] = self.icon_combo.count() - 1

        if os.path.exists(self.user_icons_folder):
            svg_files = []
            
            for file in sorted(os.listdir(self.user_icons_folder)):
                if file.lower().endswith('.svg'):
                    svg_files.append(file)
            
            if svg_files:
                for svg_file in svg_files:
                    icon_name = os.path.splitext(svg_file)[0]
                    icon_path = os.path.join(self.user_icons_folder, svg_file)
                    self.icon_combo.addItem(icon_name, icon_path)
                    self.icon_paths[icon_path] = self.icon_combo.count() - 1

    def fill_with_button_data(self):
        """Заполняет поля данными редактируемой кнопки"""
        if not self.button_data:
            return
        
        # Заполняем название
        self.name_input.setText(self.button_data.get('name', ''))
        
        # Устанавливаем иконку
        icon_path = self.button_data.get('icon_path', '')
        if icon_path and icon_path in self.icon_paths:
            index = self.icon_paths[icon_path]
            self.icon_combo.setCurrentIndex(index)
        elif icon_path and os.path.exists(icon_path):
            # Если путь не найден в списке, добавляем его
            icon_name = os.path.splitext(os.path.basename(icon_path))[0]
            self.icon_combo.addItem(icon_name, icon_path)
            self.icon_combo.setCurrentIndex(self.icon_combo.count() - 1)
        
        # Устанавливаем команду
        name_command = self.button_data.get('name_command', '')
        index = self.command_combo.findText(name_command)
        if index >= 0:
            self.command_combo.setCurrentIndex(index)
        
        # Устанавливаем действие
        move_command = self.button_data.get('move_command', 'open')
        index = self.cmb_action.findText(move_command)
        if index >= 0:
            self.cmb_action.setCurrentIndex(index)

    def update_preview(self, index):
        """Обновляет превью выбранной иконки"""
        icon_path = self.icon_combo.itemData(index)
        
        if icon_path and os.path.exists(icon_path):
            try:
                self.preview_svg.load(icon_path)
                self.style_manager.apply_color_svg(self.preview_svg, strength=0.9)
                self.preview_svg.update()
            except Exception as e:
                debug_logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки превью: {e}")
                self.preview_svg.load("")
        else:
            self.preview_svg.load("")

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def hide_error(self):
        """Скрывает сообщение об ошибке."""
        self.error_label.setVisible(False)

    def check_folder(self, folder_path: list):
        try:
            for path in folder_path:
                if os.path.exists(path) and os.path.isdir(path):
                    pass
                else:
                    os.makedirs(path)
                    debug_logger.info(f'[SETTINGS-WIDGET] Папка "{path}" была создана.')
        except Exception as e:
            debug_logger.error(f'[SETTINGS-WIDGET] Ошибка при создании папки: {e}')

    def open_folder(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            debug_logger.error(f'[SETTINGS-WIDGET] Ошибка при открытии папки: {e}')

    def save_button(self):
        """Создает или обновляет объект кастомной кнопки"""
        name = self.name_input.text().strip()
        if not name:
            self.show_error("Введите название кнопки")
            return
        
        icon_path = self.icon_combo.currentData()
        name_command = self.command_combo.currentText()
        
        if not name_command:
            self.show_error("Выберите команду")
            return
        
        command_data = self.commands.get(name_command)
    
        if not command_data:
            self.show_error("Ошибка: команда не найдена в словаре")
            return
        
        move_command = self.cmb_action.currentText()
        
        # Генерируем новый ID только для создания
        if self.is_edit:
            button_id = self.button_data.get('id')
        else:
            button_id = self.generate_unique_id(8)
        
        # Создаем объект кастомной кнопки
        custom_button_data = {
            'id': button_id,
            'name': name,
            'icon_path': icon_path if icon_path else "",
            'name_command': name_command,
            'type_command': command_data.get('type', 'unknown'),
            'move_command': move_command,
            'command_data': command_data
        }

        if self.is_edit:
            self.update_btn_data(custom_button_data)
            self.custom_button_edited.emit(custom_button_data)
        else:
            self.save_btn_data(custom_button_data)
            self.custom_button_created.emit(custom_button_data)
        
        self.close()

    def save_btn_data(self, custom_data):
        """Сохраняет новую кнопку в JSON"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            if 'custom_buttons' not in existing_data:
                existing_data['custom_buttons'] = []
            elif isinstance(existing_data['custom_buttons'], dict):
                existing_data['custom_buttons'] = [existing_data['custom_buttons']]

            existing_data['custom_buttons'].append(custom_data)

            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка сохранения кнопки: {e}")

    def update_btn_data(self, custom_data):
        """Обновляет существующую кнопку в JSON"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            if 'custom_buttons' not in existing_data:
                existing_data['custom_buttons'] = []
            elif isinstance(existing_data['custom_buttons'], dict):
                existing_data['custom_buttons'] = [existing_data['custom_buttons']]

            # Находим и заменяем кнопку с таким же ID
            updated = False
            for i, btn in enumerate(existing_data['custom_buttons']):
                if btn.get('id') == custom_data['id']:
                    existing_data['custom_buttons'][i] = custom_data
                    updated = True
                    break
            
            if not updated:
                # Если не нашли, добавляем как новую
                existing_data['custom_buttons'].append(custom_data)

            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка обновления кнопки: {e}")

    def generate_unique_id(self, length=8):
        """Генерирует уникальный ID с проверкой на существование"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            existing_ids = set()
            custom_buttons = existing_data.get('custom_buttons', [])
            
            for btn in custom_buttons:
                if isinstance(btn, dict) and 'id' in btn:
                    existing_ids.add(btn['id'])
            
            alphabet = string.ascii_lowercase + string.digits
            while True:
                new_id = ''.join(secrets.choice(alphabet) for _ in range(length))
                if new_id not in existing_ids:
                    return new_id
                    
        except Exception as e:
            debug_logger.error(f"[SETTINGS-WIDGET] Ошибка генерации ID: {e}")
            # Fallback: обычная генерация без проверки
            alphabet = string.ascii_lowercase + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def closeEvent(self, event):
        self.monitor.stop_monitoring()
        super().closeEvent(event)
