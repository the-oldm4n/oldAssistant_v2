import json
import os
import re
import uuid
import time
import subprocess
import pythoncom
import win32com.client
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from bin.apply_color_methods import ApplyColor
from bin.custom_svg_widget import CustomSvgWidget
from bin.lists import setup_custom_font_label
from bin.shortcut_monitor import ShortcutMonitor
from bin.signals import commands_signal
from logging_config import debug_logger
from path_builder import get_path


class CreateCommandsWidget(QWidget):
    """
    Виджет создания команд с динамическим отображением форм
    """

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.current_form = None  # Текущая активная форма
        self._help_initialized = False
        self.folder_path = get_path('user_settings', "links for assist")
        self.monitor = ShortcutMonitor(self.folder_path)
        self.monitor.folder_changed.connect(self.on_folder_changed)
        self.monitor.file_added.connect(self.on_file_added)
        self.monitor.file_removed.connect(self.on_file_removed)
        self.init_ui()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        self.monitor.start_monitoring()
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Заголовок
        title = setup_custom_font_label(text="Для чего создаем команду?", font_style="Comfortaa", weight="Medium")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(title)

        # Контейнер для кнопок выбора типа
        btn_layout = QHBoxLayout()

        # Кнопка для создания команды ярлыка
        self.btn_shortcut = QPushButton("Для ярлыка")
        self.btn_shortcut.setCheckable(True)
        self.btn_shortcut.clicked.connect(self.show_shortcut_form)
        self.btn_shortcut.setProperty("helpId", "btn_shortcut")
        btn_layout.addWidget(self.btn_shortcut)

        # Кнопка для создания команды папки
        self.btn_folder = QPushButton("Для папки")
        self.btn_folder.setCheckable(True)
        self.btn_folder.clicked.connect(self.show_folder_form)
        self.btn_folder.setProperty("helpId", "btn_folder")
        btn_layout.addWidget(self.btn_folder)

        # Кнопка для создания команды папки
        self.btn_url = QPushButton("Для сайта")
        self.btn_url.setCheckable(True)
        self.btn_url.clicked.connect(self.show_url_form)
        self.btn_url.setProperty("helpId", "btn_url")
        btn_layout.addWidget(self.btn_url)

        layout.addLayout(btn_layout)

        # Контейнер для динамических форм
        self.form_container = QStackedWidget()
        self.form_container.setObjectName("CreateCommandsWidgets")
        self.form_container.hide()
        layout.addWidget(self.form_container)

        # Создаем формы (но пока не добавляем в layout)
        self.create_forms()

        layout.addStretch()
        
        self.open_folder_lnk = QPushButton("Открыть папку с ярлыками")
        self.open_folder_lnk.clicked.connect(self.assistant.open_folder_shortcuts)
        layout.addWidget(self.open_folder_lnk)

        self.ps = QLabel("Добавьте необходимые ярлыки через автопоиск или вручную, нажав на кнопку выше.")
        self.ps.setWordWrap(True)
        self.ps.setStyleSheet("background-color: transparent; font-size: 15px;")
        layout.addWidget(self.ps)

        self.search_btn = QPushButton("Автопоиск ярлыков")
        self.search_btn.clicked.connect(self.autosearch_shortcuts)
        self.search_btn.setProperty("helpId", "search_btn")
        layout.addWidget(self.search_btn)

    def autosearch_shortcuts(self):
        """Поиск ярлыков в стандартном расположении"""
        self.assistant.commands_manager.scan_and_copy_shortcuts()
        self.assistant.commands_manager.search_links()
        self.assistant.show_notification_message(f"Поиск завершен!")

        # Обновляем список в форме
        if hasattr(self.shortcut_form, 'refresh_shortcuts'):
            self.shortcut_form.refresh_shortcuts()

    def create_forms(self):
        """Создаем все формы заранее"""
        # Форма для ярлыка
        self.shortcut_form = AppCommandForm(self.assistant)
        self.form_container.addWidget(self.shortcut_form)

        # Форма для папки
        self.folder_form = FolderCommandForm(self.assistant)
        self.form_container.addWidget(self.folder_form)

        self.url_form = UrlCommandForm(self.assistant)
        self.form_container.addWidget(self.url_form)

        # Изначально скрываем все формы
        self.form_container.setCurrentIndex(-1)

    def show_shortcut_form(self):
        """Показывает форму для создания команды ярлыка"""
        self.btn_shortcut.setChecked(True)
        self.btn_folder.setChecked(False)
        self.btn_url.setChecked(False)
        self.form_container.show()
        self.form_container.setCurrentWidget(self.shortcut_form)

    def show_folder_form(self):
        """Показывает форму для создания команды папки"""
        self.btn_folder.setChecked(True)
        self.btn_shortcut.setChecked(False)
        self.btn_url.setChecked(False)
        self.form_container.show()
        self.form_container.setCurrentWidget(self.folder_form)

    def show_url_form(self):
        """Показывает форму для создания команды папки"""
        self.btn_folder.setChecked(False)
        self.btn_shortcut.setChecked(False)
        self.btn_url.setChecked(True)
        self.form_container.show()
        self.form_container.setCurrentWidget(self.url_form)
        
    def hideEvent(self, event):
        """При закрытии виджета - выключить мониторинг"""
        super().hideEvent(event)
        self.monitor.stop_monitoring()
    
    def closeEvent(self, event):
        """При полном закрытии - выключить мониторинг"""
        self.monitor.stop_monitoring()
        super().closeEvent(event)
        
    def on_folder_changed(self):
        """Общее изменение в папке"""
        debug_logger.info("Обнаружены изменения в папке")
        self.refresh_file_list()
    
    def on_file_added(self, filepath):
        """Конкретный файл добавлен"""
        debug_logger.info(f"Файл добавлен: {filepath}")
    
    def on_file_removed(self, filepath):
        """Конкретный файл удален"""
        debug_logger.info(f"Файл удален: {filepath}")
    
    def refresh_file_list(self):
        """Обновить список файлов в GUI"""
        self.assistant.commands_manager.search_links()

        if hasattr(self.shortcut_form, 'refresh_shortcuts'):
            self.shortcut_form.refresh_shortcuts()
            self.assistant.show_notification_message(f"Список ярлыков обновлен!")

        

class AppCommandForm(QWidget):
    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.assistant.commands_manager.search_links()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addStretch()

        self.key_input = QLineEdit(self)
        self.key_input.setPlaceholderText("Введите команду (например: 'браузер')")
        self.key_input.returnPressed.connect(self.apply_command)  # Обработка нажатия Enter
        self.key_input.setProperty("helpId", "key_input_app")

        # Label для ошибок
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        self.label_command = QLabel("Команда (уникальное слово):")
        self.label_command.setStyleSheet("background: transparent;")
        self.label_command.setProperty("helpId", "key_input_app")

        self.shortcut_combo = SearchComboBox(self)
        self.load_shortcuts()
        self.shortcut_combo.lineEdit().returnPressed.connect(self.apply_command)  # Обработка нажатия Enter
        self.label_link = QLabel("Выберите ярлык:")
        self.label_link.setStyleSheet("background: transparent;")
        self.label_link.setProperty("helpId", "label_link_app")

        self.apply_button = QPushButton("Добавить команду", self)
        self.apply_button.clicked.connect(self.apply_command)

        layout.addWidget(self.label_command)
        layout.addWidget(self.key_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.label_link)
        layout.addWidget(self.shortcut_combo)
        layout.addWidget(self.apply_button)

    def load_shortcuts(self):
        links_file = get_path('user_settings', 'links.json')
        try:
            with open(links_file, 'r', encoding='utf-8') as file:
                links = json.load(file)
                self.shortcut_combo.updateModel(links)
        except Exception as e:
            debug_logger.error(f"Ошибка загрузки ярлыков: {e}")

    def refresh_shortcuts(self):
        self.load_shortcuts()
        current_selection = self.shortcut_combo.currentText()
        links_file = get_path('user_settings', 'links.json')
        try:
            with open(links_file, 'r', encoding='utf-8') as file:
                links = json.load(file)
                self.shortcut_combo.updateModel(links)
                if current_selection in links:
                    self.shortcut_combo.setCurrentText(current_selection)
        except Exception as e:
            debug_logger.error(f"Ошибка загрузки ярлыков: {e}")

    def apply_command(self):
        key = self.key_input.text().strip().lower()
        selected_name = self.shortcut_combo.currentFileName()

        if not key:
            self.show_error("Команда не может быть пустой!")
            return

        if key in self.assistant.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return

        if not selected_name:
            self.show_error("Пожалуйста, выберите ярлык из списка!")
            return

        self.assistant.commands[key] = selected_name
        commands_signal.commands_updated.emit()
        self.assistant.show_notification_message(message=f"Команда '{key}' добавлена!")
        self.key_input.clear()
        self.error_label_clear()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def error_label_clear(self):
        """Очистка лейбла ошибок"""
        self.error_label.setText("")
        self.error_label.setVisible(False)


class FolderCommandForm(QWidget):
    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addStretch()

        self.key_input = QLineEdit(self)
        self.key_input.setPlaceholderText("Введите команду (например: 'загрузки')")
        self.key_input.returnPressed.connect(self.apply_command)  # Обработка нажатия Enter
        self.key_input.setProperty("helpId", "key_input_app")

        # Label для ошибок
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        self.label_command_folder = QLabel("Команда (уникальное слово):")
        self.label_command_folder.setStyleSheet("background: transparent;")
        self.label_command_folder.setProperty("helpId", "key_input_app")

        choice_layout = QHBoxLayout()
        choice_layout.setSpacing(5)

        self.folder_path = QLineEdit(self)
        self.folder_path.returnPressed.connect(self.apply_command)  # Обработка нажатия Enter
        self.folder_path.setProperty("helpId", "label_folder")
        self.label_folder = QLabel("Путь к папке:")
        self.label_folder.setStyleSheet("background: transparent;")
        self.label_folder.setProperty("helpId", "label_folder")

        select_button = QPushButton("Обзор", self)
        select_button.setStyleSheet("padding-left: 6px; padding-right: 6px;")
        select_button.clicked.connect(self.select_folder)
        

        self.apply_button = QPushButton("Добавить команду", self)
        self.apply_button.clicked.connect(self.apply_command)

        layout.addWidget(self.label_command_folder)
        layout.addWidget(self.key_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.label_folder)
        choice_layout.addWidget(self.folder_path)
        choice_layout.addWidget(select_button)
        layout.addLayout(choice_layout)
        layout.addWidget(self.apply_button)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.folder_path.setText(folder)

    def apply_command(self):
        key = self.key_input.text().strip().lower()
        folder = self.folder_path.text().strip()

        if not key or not folder:
            self.show_error("Заполните все поля!")
            return

        if key in self.assistant.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return

        self.assistant.commands[key] = folder
        commands_signal.commands_updated.emit()
        self.assistant.show_notification_message(message=f"Команда '{key}' добавлена!")
        self.key_input.clear()
        self.folder_path.clear()
        self.error_label_clear()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def error_label_clear(self):
        self.error_label.setText("")
        self.error_label.setVisible(False)


class UrlCommandForm(QWidget):
    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addStretch()

        self.key_input = QLineEdit(self)
        self.key_input.setPlaceholderText("Введите команду (например: 'загрузки')")
        self.key_input.returnPressed.connect(self.apply_command)
        self.key_input.setProperty("helpId", "key_input_app")

        # Label для ошибок
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        self.label_command_folder = QLabel("Команда (уникальное слово):")
        self.label_command_folder.setStyleSheet("background: transparent;")
        self.label_command_folder.setProperty("helpId", "key_input_app")

        self.url_path = QLineEdit(self)
        self.url_path.setPlaceholderText("https://example.com или example.com")
        self.url_path.returnPressed.connect(self.apply_command)
        self.url_path.setProperty("helpId", "url_path")

        self.label_url = QLabel("Укажите ссылку:")
        self.label_url.setStyleSheet("background: transparent;")
        self.label_url.setProperty("helpId", "url_path")

        self.apply_button = QPushButton("Добавить команду", self)
        self.apply_button.clicked.connect(self.apply_command)

        layout.addWidget(self.label_command_folder)
        layout.addWidget(self.key_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.label_url)
        layout.addWidget(self.url_path)
        layout.addWidget(self.apply_button)

    def normalize_url_for_comparison(self, url):
        """
        Нормализует URL для сравнения: убирает www, http, https, приводит к единому формату
        Возвращает кортеж: (нормализованный URL, оригинальный URL)
        """
        if not url:
            return "", url

        original_url = url
        url = url.lower().strip()

        # Убираем протоколы
        if url.startswith('http://'):
            url = url[7:]
        elif url.startswith('https://'):
            url = url[8:]

        # Убираем www.
        if url.startswith('www.'):
            url = url[4:]

        # Убираем слэш в конце
        if url.endswith('/'):
            url = url[:-1]

        return url, original_url

    def apply_command(self):
        key = self.key_input.text().strip().lower()
        url = self.url_path.text().strip()

        if not key or not url:
            self.show_error("Заполните все поля!")
            return

        if key in self.assistant.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return

        # Проверяем, что это валидный URL
        normalized_url, _ = self.normalize_url_for_comparison(url)
        if not self.is_valid_url(normalized_url):
            self.show_error("Некорректный URL!")
            return

        # Сохраняем URL в оригинальном формате
        self.assistant.commands[key] = url
        commands_signal.commands_updated.emit()
        self.assistant.show_notification_message(f"Команда '{key}' добавлена!")
        self.key_input.clear()
        self.url_path.clear()
        self.error_label_clear()

    def is_valid_url(self, url):
        """
        Проверяет, является ли строка валидным URL после нормализации
        """
        # Должна быть хотя бы одна точка и домен верхнего уровня
        if '.' not in url or len(url.split('.')[-1]) < 2:
            return False

        # Проверяем валидные символы в домене
        domain_part = url.split('/')[0]
        if not re.match(r'^[a-zA-Z0-9.-]+$', domain_part):
            return False

        return True

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def error_label_clear(self):
        self.error_label.setText("")
        self.error_label.setVisible(False)


class CommandsWidget(QWidget):
    """Класс для обработки окна 'Добавленные команды'"""

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._help_initialized = False
        self.init_ui()
        self.update_commands_list()
        commands_signal.commands_updated.connect(self.update_commands_list)

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self.title = setup_custom_font_label(text="Добавленные команды", font_style="Comfortaa", weight="Medium")

        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("background: transparent; font-size: 18px;")
        self.title.setProperty("helpId", "commands_list")
        layout.addWidget(self.title)

        self.commands_list = QListWidget(self)
        self.commands_list.setFont(QFont("Tahoma"))
        self.commands_list.setStyleSheet("border: none; font-size: 15px;")
        self.commands_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.commands_list.setProperty("helpId", "commands_list")
        layout.addWidget(self.commands_list)

        # Включаем контекстное меню для списка
        self.commands_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.commands_list.customContextMenuRequested.connect(self.show_context_menu)

        # Создаем контекстное меню
        self.context_menu = QMenu(self)
        self.edit_action = self.context_menu.addAction("Редактировать")
        self.edit_action.triggered.connect(self.edit_command)
        self.delete_action = self.context_menu.addAction("Удалить")
        self.delete_action.triggered.connect(self.delete_command)

    def showEvent(self, event):
        """Переопределяем метод показа виджета"""
        super().showEvent(event)
        self.select_last_item()
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def select_last_item(self):
        """Выбирает последний элемент в списке"""
        if self.commands_list.count() > 0:
            last_index = self.commands_list.count() - 1
            self.commands_list.setCurrentRow(last_index)
            self.commands_list.scrollToBottom()

    def show_context_menu(self, position):
        """Показывает контекстное меню"""
        item = self.commands_list.itemAt(position)
        if item is not None:
            current_text = item.text()
            
            # Извлекаем ключ команды
            if " : " in current_text:
                key = current_text.split(" : ")[0]

                is_script = False
                if key in self.assistant.commands:
                    cmd_data = self.assistant.commands[key]
                    if isinstance(cmd_data, dict) and cmd_data.get('type') == 'script':
                        is_script = True

                context_menu = QMenu(self)

                # Только для скриптов
                if is_script:
                    edit_script_action = context_menu.addAction("Редактировать сценарий")
                    edit_script_action.triggered.connect(lambda: self.edit_script(key))
                
                # Для всех команд
                edit_action = context_menu.addAction("Изменить команду")
                edit_action.triggered.connect(self.edit_command)
                
                delete_action = context_menu.addAction("Удалить")
                delete_action.triggered.connect(self.delete_command)

                context_menu.exec_(self.commands_list.mapToGlobal(position))

    def edit_script(self, script_key):
        """Редактирование скрипта"""
        if script_key not in self.assistant.commands:
            return
        
        script_data = self.assistant.commands[script_key]
        if not isinstance(script_data, dict) or script_data.get('type') != 'script':
            return
        
        # Открываем диалог редактирования скрипта
        dialog = EditScriptDialog(
            script_key=script_key,
            script_data=script_data,
            commands_manager=self.assistant.commands_manager,
            parent=self
        )
        
        if dialog.exec_() == QDialog.DialogCode.Accepted:
            # Обновляем скрипт
            updated_data = dialog.get_updated_script_data()
            self.assistant.commands[script_key] = updated_data

            with open(get_path('user_settings', 'commands.json'), 'w', encoding='utf-8') as file:
                json.dump(self.assistant.commands, file, ensure_ascii=False, indent=4)

            self.update_commands_list()
            self.assistant.show_notification_message(f"Сценарий '{script_key}' обновлен")

    def edit_command(self):
        """Редактирование выбранной команды"""
        selected_items = self.commands_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        current_text = item.text()

        if " : " in current_text:
            current_key, current_value = current_text.split(" : ", 1)

            dialog = EditCommandDialog(
                current_key=current_key,
                current_value=current_value,
                assistant=self.assistant,
                parent=self
            )

            if dialog.exec_() == QDialog.DialogCode.Accepted:
                new_key = dialog.new_key

                if current_key in self.assistant.commands:
                    command_value = self.assistant.commands[current_key]
                    del self.assistant.commands[current_key]
                    self.assistant.commands[new_key] = command_value
                    self.save_commands()
                    self.update_commands_list()
                    self.assistant.show_message(f"Команда успешно переименована в '{new_key}'", "Успех", "info")

    def update_commands_list(self):
        """Обновляет список команд"""
        self.commands_list.clear()

        for key, command_data in self.assistant.commands.items():
            if isinstance(command_data, dict) and 'name' in command_data:
                name = command_data.get('name', '')
                _type = command_data.get('type', '')
                desc = command_data.get('desc', '')

                if _type == "script":
                    item_text = f"{key} : [{_type}], {desc}"
                else:
                    item_text = f"{key} : [{_type}], {name}"
            else:
                item_text = f"{key} : ???"
            
            item = QListWidgetItem(item_text)

            if isinstance(command_data, dict):
                tooltip_text = f"Команда: {key}\n"
                tooltip_text += f"Имя: {command_data.get('name', '')}\n"
                tooltip_text += f"Описание: {command_data.get('desc', '')}\n"
                tooltip_text += f"Тип: {command_data.get('type', 'неизвестно')}"
                
                if command_data.get('type') == "script":
                    actions = command_data.get('actions', [])
                    tooltip_text += "\n\nДействия:"
                    for i, action in enumerate(actions, 1):
                        cmd_key = action.get('command_key', '???')
                        delay = action.get('delay', 0)
                        move = action.get('move', 'open')
                        args = action.get('args', '')
                        
                        tooltip_text += f"\n{i}. {cmd_key}"
                        if move == "open":
                            move_on = "Открыть"
                        elif move =="close":
                            move_on = "Закрыть"
                        else:
                            move_on = ""
                        tooltip_text += f" ({move_on} с задержкой: {delay} сек.)"

                        if args:
                            tooltip_text += f" [{args}]"
                
                item.setToolTip(tooltip_text)
            
            self.commands_list.addItem(item)

        self.select_last_item()

    def delete_command(self):
        """Удаление выбранной команды"""
        selected_items = self.commands_list.selectedItems()
        if not selected_items:
            self.assistant.show_message("Выберите команду для удаления", "Предупреждение", "warning")
            return

        # Удаляем выбранные команды
        for item in selected_items:
            key = item.text().split(" : ")[0]
            if key in self.assistant.commands:
                self.remove_command_from_process_names(self.assistant.commands[key])
                del self.assistant.commands[key]
                self.commands_list.takeItem(self.commands_list.row(item))

        self.save_commands()
        self.select_last_item()

    def remove_command_from_process_names(self, command_value):
        """Удаляет команду из process_names.json"""
        process_names_file = get_path('user_settings', 'process_names.json')
        try:
            with open(process_names_file, 'r', encoding='utf-8') as file:
                process_names = json.load(file)

            updated_names = [entry for entry in process_names if list(entry.keys())[0] != command_value]

            with open(process_names_file, 'w', encoding='utf-8') as file:
                json.dump(updated_names, file, ensure_ascii=False, indent=4)
        except Exception as e:
            debug_logger.error(f"Ошибка при обновлении process_names.json: {e}")

    def save_commands(self):
        """Cохраняет команды"""
        try:
            with open(get_path('user_settings', 'commands.json'), 'w', encoding='utf-8') as file:
                json.dump(self.assistant.commands, file, ensure_ascii=False, indent=4)

        except Exception as e:
            debug_logger.error(f"Ошибка сохранения команд в CommandsWidget: {e}")


class ProcessLinksWidget(QWidget):
    """ Класс для обработки окна "Процессы ярлыков" """

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._help_initialized = False
        self.process_names_path = self.assistant.process_names
        self.process_names = self.load_process_names()
        self.init_ui()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        """ Инициализация пользовательского интерфейса """
        self.setWindowTitle("Процессы ярлыков")

        # Основной вертикальный макет
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Заголовок
        self.title = setup_custom_font_label(text="Процессы ярлыков\n(нужны для закрытия)", font_style="Comfortaa", weight="Medium")

        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("background: transparent; font-size: 18px;")
        self.title.setProperty("helpId", "process_widget_info")
        main_layout.addWidget(self.title)

        # Горизонтальный макет для левой и правой колонок
        content_layout = QHBoxLayout()

        # Левая колонка: список ярлыков
        left_layout = QVBoxLayout()
        self.links_label = setup_custom_font_label(text="Ярлыки", font_style="Comfortaa", weight="Medium")
        self.links_label.setStyleSheet("background: transparent; font-size: 14px")
        left_layout.addWidget(self.links_label)
        self.links_list = QListWidget()
        self.links_list.setStyleSheet("background: transparent;")
        self.links_list.itemClicked.connect(self.on_link_selected)
        self.links_list.setProperty("helpId", "links_list")
        left_layout.addWidget(self.links_list)

        # Правая колонка: список процессов
        right_layout = QVBoxLayout()
        self.processes_label = setup_custom_font_label(text="Список процессов", font_style="Comfortaa", weight="Medium")
        self.processes_label.setStyleSheet("background: transparent; font-size: 14px")
        self.processes_label.setProperty("helpId", "processes_list")
        right_layout.addWidget(self.processes_label)

        self.processes_list = QListWidget()
        self.processes_list.setStyleSheet("background: transparent;")
        self.processes_list.setProperty("helpId", "processes_list")
        right_layout.addWidget(self.processes_list)

        # Кнопки для управления процессами
        self.add_process_button = QPushButton("Добавить процесс")
        self.add_process_button.clicked.connect(self.add_process)
        right_layout.addWidget(self.add_process_button)

        self.remove_process_button = QPushButton("Удалить процесс")
        self.remove_process_button.clicked.connect(self.remove_process)
        right_layout.addWidget(self.remove_process_button)

        # Добавляем левую и правую части в горизонтальный макет
        content_layout.addLayout(left_layout, 2)
        content_layout.addLayout(right_layout, 2)

        # Добавляем горизонтальный макет в основной вертикальный макет
        main_layout.addLayout(content_layout)

        # Устанавливаем основной макет для окна
        self.setLayout(main_layout)

        # Заполняем список ярлыков
        self.update_links_list()

    def load_process_names(self):
        """ Загружает данные о ярлыках и процессах из файла process_names.json """
        if os.path.exists(self.process_names_path):
            with open(self.process_names_path, "r", encoding="utf-8") as file:
                return json.load(file)
        return []

    def save_process_names(self):
        """ Сохраняет данные о ярлыках и процессах в файл process_names.json """
        with open(self.process_names_path, "w", encoding="utf-8") as file:
            json.dump(self.process_names, file, ensure_ascii=False, indent=4)

    def update_links_list(self):
        """ Обновляет список ярлыков """
        self.links_list.clear()
        for item in self.process_names:
            for link_name in item.keys():
                self.links_list.addItem(link_name)

    def update_processes_list(self, link_name):
        """ Обновляет список процессов для выбранного ярлыка """
        self.processes_list.clear()
        for item in self.process_names:
            if link_name in item:
                for process in item[link_name]:
                    self.processes_list.addItem(process)
                break

    def on_link_selected(self, item):
        """ Обработка выбора ярлыка """
        link_name = item.text()
        self.update_processes_list(link_name)

    def add_process(self):
        """ Добавляет процесс к выбранному ярлыку """
        current_link = self.links_list.currentItem()
        if not current_link:
            self.assistant.show_message("Выберите ярлык для добавления процесса.", "Ошибка", "error")
            return

        link_name = current_link.text()
        self.add_custom_process(link_name)

    def remove_process(self):
        """ Удаляет процесс из выбранного ярлыка """
        current_link = self.links_list.currentItem()
        current_process = self.processes_list.currentItem()
        if not current_link or not current_process:
            self.assistant.show_message("Выберите ярлык и процесс для удаления.", "Ошибка", "error")
            return

        link_name = current_link.text()
        process_name = current_process.text()
        for item in self.process_names:
            if link_name in item:
                if process_name in item[link_name]:
                    item[link_name].remove(process_name)
                    self.update_processes_list(link_name)
                    self.save_process_names()
                break

    def add_custom_process(self, link_name):
        """Кастомный диалог для добавления нового процесса"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить процесс")
        dialog.setFixedSize(250, 100)

        layout = QVBoxLayout(dialog)

        # Поле ввода
        label = QLabel("Введите название процесса:")
        layout.addWidget(label)

        process_edit = QLineEdit()
        process_edit.setPlaceholderText("Название процесса...")
        layout.addWidget(process_edit)

        # Создаем кастомные кнопки
        button_box = QDialogButtonBox()

        # Кнопка Ок
        ok_button = QPushButton("Ок")
        ok_button.setStyleSheet("padding: 1px 10px;")
        ok_button.clicked.connect(dialog.accept)

        # Кнопка Закрыть
        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet("padding: 1px 10px;")
        close_button.clicked.connect(dialog.reject)

        button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(close_button, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addStretch()

        layout.addWidget(button_box)

        # Валидация ввода
        def validate_input():
            text = process_edit.text().strip()
            ok_button.setEnabled(bool(text))

        process_edit.textChanged.connect(validate_input)
        validate_input()  # Инициализация состояния кнопки

        # Проверка на дубликаты перед закрытием
        def check_and_accept():
            process_name = process_edit.text().strip()

            # Проверка на существующий процесс
            for item in self.process_names:
                if link_name in item:
                    if process_name in item[link_name]:
                        QMessageBox.warning(
                            self,
                            "Ошибка",
                            "Процесс с таким именем уже существует."
                        )
                        return

                    item[link_name].append(process_name)
                    self.update_processes_list(link_name)
                    self.save_process_names()
                    dialog.accept()
                    return

        ok_button.clicked.disconnect()
        ok_button.clicked.connect(check_and_accept)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            process_edit.setFocus()

    def closeEvent(self, event):
        """ Сохраняет данные при закрытии окна """
        self.save_process_names()
        super().closeEvent(event)


class SearchComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)

        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(self.completer)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self._items_data = {}  # {filename: full_path}

    def updateModel(self, items_data):
        """Обновляет модель с данными {имя_файла: полный_путь}"""
        self._items_data = items_data
        self.clear()
        self.addItems(list(items_data.keys()))

        # Обновляем автодополнение
        model = QStringListModel(list(items_data.keys()))
        self.completer.setModel(model)

    def currentFileName(self):
        """Возвращает выбранное имя файла"""
        return self.currentText()

    def currentFilePath(self):
        """Возвращает полный путь выбранного файла"""
        return self._items_data.get(self.currentText(), "")

class EditCommandDialog(QDialog):
    """Кастомное диалоговое окно ввода с валидацией"""

    def __init__(self, current_key="", current_value="", assistant=None, parent=None):
        super().__init__(parent)
        self.current_key = current_key
        self.current_value = current_value
        self.assistant = assistant
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

        self.title_label = QLabel('Редактирование команды', self.title_bar)
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
        self.input_field.setPlaceholderText('Введите команду:')

        self.input_field.setText(self.current_key)
        self.input_field.selectAll()

        # Label для ошибок
        self.error_label = QLabel(self.content_widget)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

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

    def try_accept(self):
        """Пытается закрыть окно, если ввод корректен."""
        new_key = self.get_text()

        if not new_key:
            self.show_error("Название команды не может быть пустым!")
            return

        # Проверяем, не совпадает ли новое название с текущим
        if new_key == self.current_key:
            self.reject()  # Если не изменилось, просто закрываем
            return

        # Проверяем, не существует ли уже команды с таким названием
        if new_key in self.assistant.commands:
            self.show_error(f"Команда '{new_key}' уже существует!")
            return

        # Сохраняем новое название
        self.new_key = new_key
        self.accept()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_text(self):
        """Возвращает очищенный текст из поля ввода."""
        return self.input_field.text().strip()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()  # Закрываем только это окно
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


class CreateScriptsWidget(QWidget):
    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.commands_manager = self.assistant.commands_manager
        self._help_initialized = False
        self.init_ui()
        
    def showEvent(self, event):
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Заголовок
        title = setup_custom_font_label(text="Создание сценариев запуска", font_style="Comfortaa", weight="Medium")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(title)

        # Контейнер для кнопок выбора типа
        btn_layout = QHBoxLayout()

        # Кнопка для создания команды ярлыка
        self.btn_shortcut = QPushButton("Обычный сценарий")
        self.btn_shortcut.setCheckable(True)
        self.btn_shortcut.setChecked(True)
        self.btn_shortcut.clicked.connect(self.show_script_simple)
        self.btn_shortcut.setProperty("helpId", "btn_script_simple")
        btn_layout.addWidget(self.btn_shortcut)

        # Кнопка для создания команды папки
        self.btn_folder = QPushButton("Автозапуск")
        self.btn_folder.setCheckable(True)
        self.btn_folder.clicked.connect(self.show_script_autostart)
        self.btn_folder.setProperty("helpId", "btn_script_autostart")
        btn_layout.addWidget(self.btn_folder)

        layout.addLayout(btn_layout)

        # Контейнер для динамических форм
        self.form_container = QStackedWidget()
        self.form_container.setObjectName("CreateRunWidgets")
        layout.addWidget(self.form_container)

        # Создаем формы
        self.create_forms()

    def create_forms(self):
        """Создаем все формы заранее"""
        # Форма для простого сценария
        self.simple_form = SimpleScriptForm(commands_manager=self.commands_manager, assistant=self.assistant)
        self.form_container.addWidget(self.simple_form)
        
        # Форма для автозапуска
        # self.autostart_form = QWidget()
        # autostart_layout = QVBoxLayout(self.autostart_form)
        # autostart_layout.addWidget(QLabel("Work in progress..."), alignment=Qt.AlignmentFlag.AlignTop)
        self.autostart_form = TaskSchedulerWidget(commands_manager=self.commands_manager, assistant=self.assistant)
        self.form_container.addWidget(self.autostart_form)

    def show_script_simple(self):
        self.form_container.setCurrentWidget(self.simple_form)
        
    def show_script_autostart(self):
        self.form_container.setCurrentWidget(self.autostart_form)


class ScriptStepWidget(QWidget):
    """Виджет одного шага в сценарии"""
    stepRemoved = Signal(int)
    stepMovedUp = Signal(int)
    stepMovedDown = Signal(int)
    stepChanged = Signal()
    
    def __init__(self, step_number, available_commands, parent=None):
        super().__init__(parent)
        self.style_manager = ApplyColor()
        self.step_number = step_number
        self.available_commands = available_commands
        self.icon_arrowup_path = get_path("bin", "icons", "arrow_up.svg")
        self.icon_arrowdown_path = get_path("bin", "icons", "arrow_down.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        # layout = QHBoxLayout(self)
        # layout.setContentsMargins(5, 5, 5, 5)
        # main_widget = QWidget()
        # layout.addWidget(main_widget)
        # main_widget.setObjectName("ScriptStepFrame")

        main_widget = QWidget()
        main_widget.setObjectName("ScriptStepFrame")
        layout = QHBoxLayout(main_widget)  # Layout внутри frame
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Номер шага
        lbl_number = QLabel(f"{self.step_number}.")
        lbl_number.setStyleSheet("background: transparent;")
        layout.addWidget(lbl_number, alignment=Qt.AlignmentFlag.AlignTop)

        combo_layout = QVBoxLayout()

        # Выбор команды
        self.cmb_command = QComboBox()
        self.cmb_command.setMinimumWidth(250)
        self._populate_commands()
        self.cmb_command.currentIndexChanged.connect(self.stepChanged)
        combo_layout.addWidget(self.cmb_command)
        
        # Задержка
        delay_layout = QHBoxLayout()

        lbl_delay = QLabel("Задержка (сек.):")
        lbl_delay.setStyleSheet("background: transparent;")
        delay_layout.addWidget(lbl_delay)
        
        self.txt_delay = QLineEdit()
        self.txt_delay.setFixedSize(50, 30)
        self.txt_delay.setPlaceholderText("0.5")
        self.txt_delay.setText("0.5")  # значение по умолчанию
        self.txt_delay.textChanged.connect(self.stepChanged)

        # Добавляем валидатор для чисел с плавающей точкой
        regex = QRegularExpression(r'^\d{1,2}([.,]\d{0,2})?$')  # 0-99.99
        validator = QRegularExpressionValidator(regex, self)
        self.txt_delay.setValidator(validator)

        delay_layout.addWidget(self.txt_delay)
        combo_layout.addLayout(delay_layout)

        # Аргументы       
        self.txt_args = QLineEdit()
        self.txt_args.setPlaceholderText("Аргументы (опционально)")
        self.txt_args.textChanged.connect(self.stepChanged)
        combo_layout.addWidget(self.txt_args)
        combo_layout.addStretch()
        layout.addLayout(combo_layout)

        action_layout = QHBoxLayout()
        
        lbl_action = QLabel("Действие:")
        lbl_action.setStyleSheet("background: transparent;")
        action_layout.addWidget(lbl_action)
        
        self.cmb_action = QComboBox()
        self.cmb_action.addItems(["open", "close"])
        self.cmb_action.currentIndexChanged.connect(self.stepChanged)
        action_layout.addWidget(self.cmb_action)
        
        combo_layout.addLayout(action_layout)
        
        # Кнопки управления
        btns_layout = QVBoxLayout()
        self.btn_up = QPushButton("")
        self.btn_up.setFixedSize(30, 30)
        self.btn_up.clicked.connect(lambda: self.stepMovedUp.emit(self.step_number))
        
        self.btn_up_svg = CustomSvgWidget(self.icon_arrowup_path, self.btn_up)
        self.btn_up_svg.setFixedSize(30, 30)
        self.btn_up_svg.setStyleSheet("background: transparent;")
        btns_layout.addWidget(self.btn_up)
        
        self.btn_down = QPushButton("")
        self.btn_down.setFixedSize(30, 30)
        self.btn_down.clicked.connect(lambda: self.stepMovedDown.emit(self.step_number))
        self.btn_down_svg = CustomSvgWidget(self.icon_arrowdown_path, self.btn_down)
        self.btn_down_svg.setFixedSize(30, 30)
        self.btn_down_svg.setStyleSheet("background: transparent;")
        btns_layout.addWidget(self.btn_down)

        btns_layout.addStretch()
        
        self.btn_remove = QPushButton("")
        self.btn_remove.setFixedSize(30, 30)
        self.btn_remove.clicked.connect(lambda: self.stepRemoved.emit(self.step_number))
        self.btn_remove_svg = CustomSvgWidget(self.icon_close_path, self.btn_remove)
        self.btn_remove_svg.setFixedSize(30, 30)
        self.btn_remove_svg.setStyleSheet("background: transparent;")
        btns_layout.addWidget(self.btn_remove)

        layout.addLayout(btns_layout)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_widget)

    def apply_styles(self):
        self.style_manager.apply_color_svg(self.btn_up_svg, strength=0.90)
        self.style_manager.apply_color_svg(self.btn_down_svg, strength=0.90)
        self.style_manager.apply_color_svg(self.btn_remove_svg, strength=0.90)

    def _populate_commands(self, include_scripts=False):
        """Заполняем список доступных команд"""
        self.cmb_command.clear()
        self.cmb_command.addItem("-- Выберите команду --", None)
        
        for key, data in self.available_commands.items():
            # Формируем текст для отображения
            if isinstance(data, dict):
                desc = data.get('desc', '')
                cmd_type = data.get('type', '')
                if not include_scripts and cmd_type == 'script':
                    continue
            else:
                desc = ''
                cmd_type = ''
            
            display_text = f"{key}"
            if desc:
                display_text += f" - {desc}"
            
            self.cmb_command.addItem(display_text, key)
    
    def get_step_data(self):
        """Получить данные шага"""
        command_key = self.cmb_command.currentData()
        if not command_key:
            return None
            
        # Получаем значение задержки
        delay_text = self.txt_delay.text().strip()
        if not delay_text:
            delay = 0.0
        else:
            try:
                delay = float(delay_text.replace(',', '.'))
            except ValueError:
                delay = 0.0

        move = self.cmb_action.currentText()
        
        return {
            'command_key': command_key,
            'delay': delay,
            'move': move,
            'args': self.txt_args.text().strip()
        }
    
    def update_step_number(self, new_number):
        """Обновить номер шага"""
        self.step_number = new_number
        self.findChild(QLabel).setText(f"{new_number}.")

    def set_data(self, action_data):
        """Установить данные шага"""
        command_key = action_data.get('command_key', '')
        delay = action_data.get('delay', 0.5)
        move = action_data.get('move', 'open')
        args = action_data.get('args', '')

        index = self.cmb_command.findData(command_key)
        if index >= 0:
            self.cmb_command.setCurrentIndex(index)

        action_index = self.cmb_action.findText(move)
        if action_index >= 0:
            self.cmb_action.setCurrentIndex(action_index)

        self.txt_delay.setText(str(delay))

        self.txt_args.setText(args)

class SimpleScriptForm(QWidget):
    """Форма создания простого сценария"""
    def __init__(self, script_key=None, commands_manager=None, assistant=None, is_editor=False, parent=None):
        super().__init__(parent)
        self.commands_manager = commands_manager
        self.assistant = assistant
        self.is_editor = is_editor
        self.editing_key = script_key
        self.steps = []  # список виджетов шагов
        self._help_initialized = False
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        if not self.is_editor:
            # Заголовок
            lbl_title = setup_custom_font_label(text="Создание обычного сценария", font_style="Comfortaa", weight="Medium")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("background: transparent; font-size: 17px;")
            layout.addWidget(lbl_title)
        else:
            # Заголовок
            lbl_title = setup_custom_font_label(text="Редактирование сценария", font_style="Comfortaa", weight="Medium")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("background: transparent; font-size: 17px;")
            layout.addWidget(lbl_title)
        
        # Контейнер для шагов
        self.steps_container = QVBoxLayout()
        self.steps_container.setSpacing(5)
        
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setProperty("helpId", "steps_container")
        scroll_widget.setLayout(self.steps_container)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(250)
        layout.addWidget(scroll_area)
        
        # Кнопка добавления шага
        self.btn_add_step = QPushButton("+ Добавить шаг")
        self.btn_add_step.setProperty("helpId", "+step_btn")
        self.btn_add_step.clicked.connect(self.add_step)
        layout.addWidget(self.btn_add_step)

        
        # Имя сценария
        lbl_name = setup_custom_font_label(text="Название сценария:", font_style="Comfortaa", weight="Medium")
        lbl_title.setStyleSheet("background: transparent; font-size: 15px;")
        lbl_name.setProperty("helpId", "name_script")
        layout.addWidget(lbl_name)
        
        self.txt_script_name = QLineEdit()
        self.txt_script_name.setPlaceholderText("")
        self.txt_script_name.setProperty("helpId", "name_script")
        layout.addWidget(self.txt_script_name)
        
        # Описание
        lbl_desc = setup_custom_font_label(text="Описание:", font_style="Comfortaa", weight="Medium")
        lbl_desc.setStyleSheet("background: transparent; font-size: 15px;")
        lbl_desc.setProperty("helpId", "desc_script")
        layout.addWidget(lbl_desc)
        
        self.txt_script_desc = QLineEdit()
        self.txt_script_desc.setPlaceholderText("Описание сценария (необязательно)")
        self.txt_script_desc.setProperty("helpId", "desc_script")
        layout.addWidget(self.txt_script_desc)
        
        if not self.is_editor:
            # Кнопки сохранения/теста
            btn_layout = QHBoxLayout()
            
            self.btn_test = QPushButton("Тестовый запуск")
            self.btn_test.clicked.connect(self.test_script)
            self.btn_test.setProperty("helpId", "test_script")
            btn_layout.addWidget(self.btn_test)
            
            self.btn_save = QPushButton("Сохранить сценарий")
            self.btn_save.clicked.connect(self.save_script)
            self.btn_save.setProperty("helpId", "save_script")
            btn_layout.addWidget(self.btn_save)
            
            layout.addLayout(btn_layout)
        
        # Статус
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("background: transparent; color: #666; font-style: italic;")
        layout.addWidget(self.lbl_status)
        
        if not self.is_editor:
            # Добавляем первый шаг
            self.add_step()
        
    def get_available_commands(self):
        """Получить все доступные команды"""
        all_commands = {**self.commands_manager.default_commands, **self.commands_manager.commands}
        return all_commands
        
    def add_step(self):
        """Добавить новый шаг"""
        if len(self.steps) >= 10:
            self.lbl_status.setText("Максимум 10 шагов")
            return
        
        if self.steps_container.count() > 0:
            # Убираем последний элемент (stretch)
            self.steps_container.takeAt(self.steps_container.count() - 1)
            
        step_widget = ScriptStepWidget(
            len(self.steps) + 1,
            self.get_available_commands(),
            self
        )
        
        # Подключаем сигналы
        step_widget.stepRemoved.connect(self.remove_step)
        step_widget.stepMovedUp.connect(self.move_step_up)
        step_widget.stepMovedDown.connect(self.move_step_down)
        step_widget.stepChanged.connect(self.update_status)
        
        self.steps.append(step_widget)
        self.steps_container.addWidget(step_widget)
        self.update_step_numbers()
        self.update_status()
        self.steps_container.addStretch()
        
    def remove_step(self, step_number, force=False):
        """Удалить шаг"""
        if len(self.steps) <= 1 and not force:
            self.lbl_status.setText("Должен быть хотя бы один шаг")
            return False
            
        widget = self.steps[step_number - 1]
        self.steps_container.removeWidget(widget)
        widget.deleteLater()
        self.steps.pop(step_number - 1)
        self.update_step_numbers()
        self.update_status()
        return True
        
    def move_step_up(self, step_number):
        """Переместить шаг вверх"""
        if step_number <= 1:
            return
            
        # Меняем виджеты местами
        self.steps[step_number - 1], self.steps[step_number - 2] = \
            self.steps[step_number - 2], self.steps[step_number - 1]
        
        self.update_step_numbers()
        self.update_status()
        
    def move_step_down(self, step_number):
        """Переместить шаг вниз"""
        if step_number >= len(self.steps):
            return
            
        # Меняем виджеты местами
        self.steps[step_number - 1], self.steps[step_number] = \
            self.steps[step_number], self.steps[step_number - 1]
        
        self.update_step_numbers()
        self.update_status()
        
    def update_step_numbers(self):
        """Обновить номера всех шагов"""
        for i, step_widget in enumerate(self.steps, 1):
            step_widget.update_step_number(i)
            
    def update_status(self):
        """Обновить статусную строку"""
        total_steps = len(self.steps)
        
        # Суммируем задержки из QLineEdit
        total_delay = 0.0
        for step in self.steps:
            try:
                # Получаем текст из поля и преобразуем в float
                delay_text = step.txt_delay.text().strip()
                if delay_text:
                    # Заменяем запятую на точку для корректного преобразования
                    delay_text = delay_text.replace(',', '.')
                    total_delay += float(delay_text)
            except (ValueError, AttributeError):
                pass  # Игнорируем ошибки преобразования
        
        self.lbl_status.setText(f"Шагов: {total_steps}, Общее время: {total_delay:.1f} сек")
        
    def get_script_data(self):
        """Получить данные сценария из формы"""
        steps_data = []
        for step_widget in self.steps:
            step_data = step_widget.get_step_data()
            if step_data:
                steps_data.append(step_data)
                
        if not steps_data:
            return None
            
        return {
            'name': self.txt_script_name.text().strip(),
            'desc': self.txt_script_desc.text().strip(),
            "type": "script",
            'actions': steps_data
        }
        
    def validate_script(self, script_data):
        """Валидация данных сценария"""
        if not script_data['name']:
            return False, "Введите имя сценария"
            
        if len(script_data['actions']) == 0:
            return False, "Добавьте хотя бы один шаг"
        
        # В режиме редактора пропускаем проверку, если имя не меняется
        if self.is_editor and self.editing_key:
            # Если имя не изменилось - пропускаем проверку
            if script_data['name'] == self.editing_key:
                return True, ""
            
            # Если имя изменилось - проверяем уникальность нового имени
            if script_data['name'] in self.commands_manager.commands:
                return False, f"Команда '{script_data['name']}' уже существует"
        else:
            # Обычная проверка для нового скрипта
            if script_data['name'] in self.commands_manager.commands:
                return False, f"Команда '{script_data['name']}' уже существует"
            
        return True, ""
        
    def test_script(self):
        """Тестовый запуск сценария"""
        script_data = self.get_script_data()
        if not script_data:
            self.lbl_status.setText("Нет данных для теста")
            return
            
        valid, error = self.validate_script(script_data)
        if not valid:
            self.lbl_status.setText(error)
            return
            
        self.lbl_status.setText("Тестовый запуск...")

        temp_script_key = f"__test_{uuid.uuid4().hex[:8]}"
        
        # Вычисляем общую задержку скрипта
        total_delay = 0
        actions = script_data.get('actions', [])
        for action in actions:
            total_delay += action.get('delay', 0)
        
        # Добавляем 5 секунд на выполнение команд
        cleanup_delay_ms = int((total_delay + 5) * 1000)
        debug_logger.info(f"Общая задержка скрипта: {total_delay}с, очистка через {cleanup_delay_ms}мс")
        
        try:
            # Временно сохраняем в commands_manager
            self.commands_manager.commands[temp_script_key] = script_data
            debug_logger.info(f"Тестовый скрипт сохранен как: {temp_script_key}")
            
            # Запоминаем время начала
            self._test_start_time = time.time()
            
            # Выполняем тестовый скрипт
            self.commands_manager.execute_script(temp_script_key)
            
            # Очищаем через вычисленное время
            QTimer.singleShot(cleanup_delay_ms, lambda: self._cleanup_temp_script(temp_script_key))
            
        except Exception as e:
            debug_logger.error(f"Ошибка запуска теста: {e}")
            self._cleanup_temp_script(temp_script_key)
            self.lbl_status.setText(f"Ошибка: {e}")

    def _cleanup_temp_script(self, temp_key):
        """Очистка временного скрипта"""
        if temp_key in self.commands_manager.commands:
            del self.commands_manager.commands[temp_key]
            elapsed = getattr(self, '_test_start_time', None)
            if elapsed:
                elapsed = time.time() - self._test_start_time
                debug_logger.info(f"Тестовый скрипт удален: {temp_key} (выполнялся {elapsed:.1f}с)")
            else:
                debug_logger.info(f"Тестовый скрипт удален: {temp_key}")
        
    def save_script(self):
        """Сохранить сценарий"""
        script_data = self.get_script_data()
        if not script_data:
            self.lbl_status.setText("Нет данных для сохранения")
            return
            
        valid, error = self.validate_script(script_data)
        if not valid:
            self.lbl_status.setText(error)
            return
            
        # Формируем структуру для сохранения
        script_structure = {
            'name': script_data['name'],
            'desc': script_data['desc'],
            'type': 'script',
            'actions': script_data['actions']
        }
        
        # Сохраняем в менеджере команд
        self.commands_manager.commands[script_data['name']] = script_structure
        self.commands_manager.save_commands()
        
        self.assistant.show_notification_message(f"Сценарий '{script_data['name']}' сохранен!")
        commands_signal.commands_updated.emit()
        self.clear_form()
        
    def clear_form(self):
        """Очистить форму"""
        # Оставляем только первый шаг
        while len(self.steps) > 1:
            self.remove_step(len(self.steps))
        
        # Сбрасываем значения первого шага
        if self.steps:
            self.steps[0].cmb_command.setCurrentIndex(0)
            self.steps[0].txt_delay.setText("0.5")  # вместо setValue
            self.steps[0].txt_args.clear()
        
        self.txt_script_name.clear()
        self.txt_script_desc.clear()
        self.update_status()

    def load_script_data(self, script_data):
        """Загрузить данные скрипта в форму"""
        self.txt_script_desc.setText(script_data.get('desc', ''))

        actions = script_data.get('actions', [])

        for i, action in enumerate(actions):
            self.add_step()

            if self.steps:
                last_step = self.steps[-1]
                last_step.set_data(action)


class EditScriptDialog(QDialog):
    """Диалог редактирования скрипта"""
    def __init__(self, script_key, script_data, commands_manager, parent=None):
        super().__init__(parent)
        self.script_key = script_key
        self.original_data = script_data.copy()
        self.commands_manager = commands_manager

        self.form = SimpleScriptForm(script_key=self.script_key, commands_manager=self.commands_manager, is_editor=True)

        self.form.load_script_data(script_data)
        self.form.txt_script_name.setText(script_key)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 650)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)

        self.main_widget = QWidget(self)
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)

        content_layout.addWidget(self.form)

        btn_layout = QHBoxLayout()
        
        btn_test = QPushButton("Тестовый запуск")
        btn_test.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_test.clicked.connect(self.test_script)
        btn_layout.addWidget(btn_test)
        
        btn_layout.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_save.clicked.connect(self.save)
        btn_layout.addWidget(btn_save)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        content_layout.addLayout(btn_layout)
        dialog_layout.addWidget(self.main_widget)

    
    def test_script(self):
        """Тестовый запуск скрипта"""
        self.form.test_script()
    
    def save(self):
        """Сохранить изменения"""
        new_data = self.form.get_script_data()
        if new_data:
            self.original_data.update(new_data)
            self.accept()
    
    def get_updated_script_data(self):
        """Получить обновленные данные скрипта"""
        return self.original_data
    

class TaskSchedulerWidget(QWidget):
    def __init__(self, commands_manager=None, assistant=None, parent=None):
        super().__init__(parent)
        self.commands_manager = commands_manager
        self.assistant = assistant
        self.links_file = get_path("user_settings", "links.json")
        self.links = self.load_links()
        self._help_initialized = False
        self.setObjectName("TaskSchedulerWidget")
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.assistant, 'install_event_filter_recursive'):
            self.assistant.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        
        # Заголовок
        title_label = setup_custom_font_label(text="Создание задачи в планировщике", font_style="Comfortaa", weight="Medium")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("background: transparent; font-size: 17px;")
        layout.addWidget(title_label)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)
        
        # Название задачи
        lbl_name = setup_custom_font_label(text="Название задачи:", font_style="Comfortaa", weight="Medium")
        lbl_name.setStyleSheet("background: transparent; font-size: 14px;")
        lbl_name.setProperty("helpId", "task_field_name")
        content_layout.addWidget(lbl_name)

        self.task_name_edit = QLineEdit()
        self.task_name_edit.setPlaceholderText("Новая задача")
        self.task_name_edit.setProperty("helpId", "task_field_name")
        content_layout.addWidget(self.task_name_edit)
        
        # Выбор ярлыка
        lbl_link = setup_custom_font_label(text="Ярлык:", font_style="Comfortaa", weight="Medium")
        lbl_link.setStyleSheet("background: transparent; font-size: 14px;")
        lbl_link.setProperty("helpId", "task_field_link")
        content_layout.addWidget(lbl_link)

        self.shortcut_combo = QComboBox()
        self.shortcut_combo.setEditable(False)
        self.populate_shortcuts()
        self.shortcut_combo.setProperty("helpId", "task_field_link")
        content_layout.addWidget(self.shortcut_combo)
        
        # Задержка запуска
        lbl_delay = setup_custom_font_label(text="Задержка:", font_style="Comfortaa", weight="Medium")
        lbl_delay.setStyleSheet("background: transparent; font-size: 14px;")
        content_layout.addWidget(lbl_delay)

        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 300)
        self.delay_spinbox.setValue(10)
        self.delay_spinbox.setSuffix(" сек")
        self.delay_spinbox.setProperty("helpId", "task_field_spinbox")
        content_layout.addWidget(self.delay_spinbox)
        
        # Аргументы для запуска
        lbl_args = setup_custom_font_label(text="Аргументы:", font_style="Comfortaa", weight="Medium")
        lbl_args.setStyleSheet("background: transparent; font-size: 14px;")
        lbl_args.setProperty("helpId", "task_field_args")
        content_layout.addWidget(lbl_args)

        self.arguments_edit = QLineEdit()
        self.arguments_edit.setPlaceholderText("Например: --minimized")
        self.arguments_edit.setProperty("helpId", "task_field_args")
        content_layout.addWidget(self.arguments_edit)
        
        # Описание задачи
        lbl_desc = setup_custom_font_label(text="Описание:", font_style="Comfortaa", weight="Medium")
        lbl_desc.setStyleSheet("background: transparent; font-size: 14px;")
        lbl_desc.setProperty("helpId", "task_field_desc")
        content_layout.addWidget(lbl_desc)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Описание задачи (опционально)")
        self.description_edit.setProperty("helpId", "task_field_desc")
        content_layout.addWidget(self.description_edit)

        layout.addLayout(content_layout)

        self.create_btn = QPushButton("Создать задачу")
        self.create_btn.clicked.connect(self.create_task)
        self.create_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.create_btn.setProperty("helpId", "task_btn_create")
        layout.addWidget(self.create_btn)
        # Кнопки
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("Тест запуска")
        self.test_btn.clicked.connect(self.test_shortcut)
        self.test_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.test_btn.setProperty("helpId", "task_btn_test")
        button_layout.addWidget(self.test_btn)
        
        self.refresh_btn = QPushButton("Обновить список")
        self.refresh_btn.clicked.connect(self.refresh_shortcuts)
        self.refresh_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.refresh_btn.setProperty("helpId", "task_btn_refresh")
        button_layout.addWidget(self.refresh_btn)

        self.open_folder = QPushButton("Ярлыки")
        self.open_folder.clicked.connect(self.assistant.open_folder_shortcuts)
        self.open_folder.setProperty("helpId", "task_btn_open_folder")
        button_layout.addWidget(self.open_folder)
        
        # Статус
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("background: transparent; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setProperty("helpId", "task_field_status")
        layout.addWidget(self.status_label)

        layout.addStretch()

        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def show_status(self, message, color="green"):
        """Показывает сообщение об ошибке."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"background: transparent; font-size: 14px; color: {color}")
        self.status_label.setVisible(True)

    def status_label_clear(self):
        """Очистка лейбла ошибок"""
        self.status_label.setText("")
        self.status_label.setVisible(False)

    def load_links(self):
        """Загрузка ярлыков из JSON файла"""
        try:
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Создаем папки, если их нет
                os.makedirs(os.path.dirname(self.links_file), exist_ok=True)
                # Создаем пустой файл
                with open(self.links_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                return {}
        except Exception as e:
            debug_logger.error(f"Ошибка загрузки файла ярлыков: {e}")
            return {}
    
    def populate_shortcuts(self):
        """Заполнение выпадающего списка ярлыками"""
        self.shortcut_combo.clear()
        self.shortcut_combo.addItem("-- Выберите ярлык --", None)
        
        for display_name, file_path in self.links.items():
            if os.path.exists(file_path):
                self.shortcut_combo.addItem(display_name, file_path)
    
    def refresh_shortcuts(self):
        """Обновить список ярлыков"""
        self.commands_manager.search_links()
        self.links = self.load_links()
        self.populate_shortcuts()
        self.show_status("Список ярлыков обновлен")
    
    def get_shortcut_info(self, lnk_path):
        """Получение информации из ярлыка .lnk"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            
            return {
                'target_path': shortcut.TargetPath,
                'working_dir': shortcut.WorkingDirectory,
                'arguments': shortcut.Arguments,
                'description': shortcut.Description
            }
        except Exception as e:
            debug_logger.error(f"Ошибка чтения ярлыка {lnk_path}: {e}")
            return None
    
    def test_shortcut(self):
        """Тестовый запуск выбранного ярлыка"""
        lnk_path = self.shortcut_combo.currentData()
        
        if not lnk_path:
            self.show_status("Выберите ярлык из списка", color="red")
            return
        
        shortcut_info = self.get_shortcut_info(lnk_path)
        if not shortcut_info:
            self.show_status(f"Не удалось прочитать ярлык:\n{lnk_path}", color="red")
            return
        
        try:
            # Формируем команду для запуска
            cmd = f'"{shortcut_info["target_path"]}"'
            if shortcut_info["arguments"]:
                cmd += f' {shortcut_info["arguments"]}'
            if self.arguments_edit.text():
                cmd += f' {self.arguments_edit.text()}'
            
            # Запускаем процесс
            working_dir = shortcut_info["working_dir"] if shortcut_info["working_dir"] else os.path.dirname(shortcut_info["target_path"])
            
            subprocess.Popen(
                cmd,
                cwd=working_dir,
                shell=True
            )
            
            self.show_status(f"Запущено: {os.path.basename(shortcut_info['target_path'])}")
            
        except Exception as e:
            self.show_status(f"Не удалось запустить программу:\n{str(e)}", color="red")
    
    def create_task(self):
        """Создание задачи в планировщике Windows"""
        # Проверка обязательных полей
        task_name = self.task_name_edit.text().strip()
        if not task_name:
            self.show_status("Введите название задачи", color="red")
            return
        
        lnk_path = self.shortcut_combo.currentData()
        if not lnk_path:
            self.show_status("Выберите ярлык из списка", color="red")
            return
        
        # Получаем информацию из ярлыка
        shortcut_info = self.get_shortcut_info(lnk_path)
        if not shortcut_info:
            self.show_status("Не удалось прочитать информацию из ярлыка", color="red")
            return
        
        # Подготавливаем данные
        target_path = shortcut_info["target_path"]
        working_dir = shortcut_info["working_dir"] or os.path.dirname(target_path)
        shortcut_args = shortcut_info["arguments"] or ""
        user_args = self.arguments_edit.text().strip()
        
        # Объединяем аргументы
        all_args = shortcut_args
        if user_args:
            if all_args:
                all_args += " " + user_args
            else:
                all_args = user_args
        
        delay = self.delay_spinbox.value()
        description = self.description_edit.text().strip()

        if self.check_task_exists(task_name):
            debug_logger.info(f"Задача найдена")
            self.show_status(f"Найдена задача с выбранным именем. Измените название задачи.", color="red")
            return
        
        try:
            # Создаем задачу в планировщике
            success = self.create_scheduled_task(
                task_name=task_name,
                target_path=target_path,
                working_dir=working_dir,
                arguments=all_args,
                delay_seconds=delay,
                description=description
            )
            
            if success:
                self.show_status(f"Задача '{task_name}' создана успешно!")
                
                # Очистка полей после успешного создания
                self.task_name_edit.clear()
                self.arguments_edit.clear()
                self.description_edit.clear()
            else:
                self.show_status("Ошибка при создании задачи", color="red")
                
        except Exception as e:
            self.show_status(f"Не удалось создать задачу:\n{str(e)}", color="red")
    
    def create_scheduled_task(self, task_name, target_path, working_dir, 
                            arguments="", delay_seconds=0, description=""):
        """Создание задачи в планировщике Windows с правильными типами"""
        try:
            # Инициализируем COM в этом потоке
            import pythoncom
            pythoncom.CoInitialize()
            
            # Подключаемся к планировщику
            scheduler = win32com.client.Dispatch('Schedule.Service')
            scheduler.Connect()
            
            # Получаем корневую папку
            root_folder = scheduler.GetFolder('\\')
            
            # Создаем новую задачу
            task_def = scheduler.NewTask(0)
            
            # === НАСТРОЙКА ОПИСАНИЯ ===
            reg_info = task_def.RegistrationInfo
            reg_info.Description = description or f"Автозапуск: {task_name}"
            reg_info.Author = "Assistant App"
            
            # === НАСТРОЙКА ТРИГГЕРА (при входе в систему) ===
            triggers = task_def.Triggers
            trigger = triggers.Create(9)  # 9 = TASK_TRIGGER_LOGON
            
            trigger.Id = "LogonTrigger"
            trigger.Delay = f"PT{delay_seconds}S"  # Формат ISO 8601
            
            # === НАСТРОЙКА ДЕЙСТВИЯ (запуск программы) ===
            action = task_def.Actions.Create(0)  # 0 = TASK_ACTION_EXEC
            action.ID = "RunProgram"
            action.Path = target_path
            
            if working_dir and os.path.exists(working_dir):
                action.WorkingDirectory = working_dir
            
            if arguments:
                action.Arguments = arguments
            
            # === НАСТРОЙКА ПРАВ ДОСТУПА ===
            principal = task_def.Principal
            principal.UserId = ""  # Текущий пользователь
            principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN = 3
            principal.RunLevel = 1   # TASK_RUNLEVEL_LUA = 1 (обычные права)
            
            # === НАСТРОЙКА ПАРАМЕТРОВ ===
            settings = task_def.Settings
            settings.Enabled = True
            settings.Hidden = False
            settings.AllowDemandStart = True
            settings.AllowHardTerminate = True
            settings.StartWhenAvailable = False
            settings.RunOnlyIfIdle = False
            settings.StopIfGoingOnBatteries = False
            settings.DisallowStartIfOnBatteries = False
            settings.ExecutionTimeLimit = "PT0H0M0S"  # Без лимита
            settings.RestartCount = 0
            settings.RestartInterval = ""
            settings.MultipleInstances = 0  # TASK_INSTANCES_IGNORE_NEW = 0
            settings.Priority = 7  # Обычный приоритет
            
            # === РЕГИСТРАЦИЯ ЗАДАЧИ ===
            # Важно: использовать правильные константы
            TASK_CREATE_OR_UPDATE = 6
            TASK_LOGON_INTERACTIVE_TOKEN = 3
            
            # Регистрируем задачу
            registered_task = root_folder.RegisterTaskDefinition(
                task_name,                     # Имя задачи
                task_def,                      # Определение задачи
                TASK_CREATE_OR_UPDATE,         # Флаг создания/обновления
                "",                          # Пользователь (None = текущий)
                "",                          # Пароль
                TASK_LOGON_INTERACTIVE_TOKEN   # Тип входа
            )
            
            debug_logger.info(f"Задача '{task_name}' зарегистрирована")
            
            # Проверяем, что задача действительно создана
            try:
                check_task = root_folder.GetTask(task_name)
                if check_task:
                    debug_logger.info(f"Задача '{task_name}' успешно проверена в планировщике")
                    pythoncom.CoUninitialize()
                    return True
                else:
                    debug_logger.error(f"Задача '{task_name}' не найдена после создания")
                    pythoncom.CoUninitialize()
                    return False
                    
            except Exception as verify_error:
                debug_logger.error(f"Ошибка проверки задачи: {verify_error}")
                
                # Пробуем альтернативный способ проверки
                if self.check_task_exists(task_name):
                    debug_logger.info(f"Задача найдена альтернативным способом")
                    pythoncom.CoUninitialize()
                    return True
                
                pythoncom.CoUninitialize()
                return False
                
        except Exception as e:
            debug_logger.error(f"Ошибка создания задачи: {e}")

            try:
                pythoncom.CoUninitialize()
            except:
                pass
            
            # Пробуем создать через PowerShell как запасной вариант
            return self.create_task_via_powershell(task_name, target_path, working_dir, 
                                                arguments, delay_seconds, description)
    
    def create_task_via_powershell(self, task_name, target_path, working_dir,
                                 arguments="", delay_seconds=0, description=""):
        """Создание задачи через PowerShell"""
        # Экранируем специальные символы
        target_path_esc = target_path.replace('"', '`"')
        working_dir_esc = working_dir.replace('"', '`"') if working_dir else ""
        arguments_esc = arguments.replace('"', '`"')
        description_esc = description.replace('"', '`"')
        
        # Формируем команду PowerShell
        ps_command = f"""
        $TaskName = "{task_name}"
        $Action = New-ScheduledTaskAction -Execute "{target_path_esc}"
        """
        
        if working_dir:
            ps_command += f'\n$Action.WorkingDirectory = "{working_dir_esc}"\n'
        
        if arguments:
            ps_command += f'$Action.Argument = "{arguments_esc}"\n'
        
        ps_command += f"""
        $Trigger = New-ScheduledTaskTrigger -AtLogOn
        $Trigger.Delay = "PT{delay_seconds}S"
        
        $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $Settings.ExecutionTimeLimit = "PT0S"
        
        $Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Description "{description_esc}"
        
        Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force
        """
        
        # Выполняем PowerShell команду
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if result.returncode == 0:
            return True
        else:
            raise Exception(f"PowerShell error: {result.stderr}")
        
    def check_task_exists(self, task_name):
        """Проверка через существование файла задачи"""
        try:
            import os
            # Путь к файлу задачи
            task_path = f"C:\\Windows\\System32\\Tasks\\{task_name}"
            
            if os.path.exists(task_path):
                debug_logger.info(f"Файл задачи найден: {task_path}")
                return True
            
            # Альтернативный путь
            alt_path = f"C:\\Windows\\Tasks\\{task_name}"
            if os.path.exists(alt_path):
                debug_logger.info(f"Файл задачи найден: {alt_path}")
                return True
                
            debug_logger.info(f"Файл задачи не найден: {task_name}")
            return False
            
        except Exception as e:
            debug_logger.error(f"Ошибка проверки файла: {e}")
            return False