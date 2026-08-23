import json
import os
import re
from urllib.parse import urlparse
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QLineEdit, QStackedWidget, QFileDialog, QComboBox, QCompleter
from PySide6.QtCore import Qt, QStringListModel
from bin.commands_manager import main_commands_manager
from bin.utils import setup_custom_font_label
from bin.shortcut_monitor import ShortcutMonitor
from bin.signals import commands_signal
from log_config import logger


class CreateCommandsWidget(QWidget):
    """
    Виджет создания команд с динамическим отображением форм
    """

    def __init__(self, main, folder_links, links_file,  parent=None):
        super().__init__(parent)
        self.main = main
        self.links_file = links_file
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.current_form = None
        self._help_initialized = False
        self.folder_path = folder_links
        self.monitor = ShortcutMonitor(self.folder_path)
        self.monitor.folder_changed.connect(self.on_folder_changed)
        self.init_ui()

    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        self.monitor.start_monitoring()
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = setup_custom_font_label(text="Для чего создаем команду?", font_style="Comfortaa", weight="Medium")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(title)

        btn_layout = QHBoxLayout()

        self.btn_shortcut = QPushButton("Для ярлыка")
        self.btn_shortcut.setCheckable(True)
        self.btn_shortcut.clicked.connect(self.show_shortcut_form)
        self.btn_shortcut.setProperty("helpId", "btn_shortcut")
        btn_layout.addWidget(self.btn_shortcut)

        self.btn_folder = QPushButton("Для папки")
        self.btn_folder.setCheckable(True)
        self.btn_folder.clicked.connect(self.show_folder_form)
        self.btn_folder.setProperty("helpId", "btn_folder")
        btn_layout.addWidget(self.btn_folder)

        self.btn_url = QPushButton("Для сайта")
        self.btn_url.setCheckable(True)
        self.btn_url.clicked.connect(self.show_url_form)
        self.btn_url.setProperty("helpId", "btn_url")
        btn_layout.addWidget(self.btn_url)

        layout.addLayout(btn_layout)

        self.form_container = QStackedWidget()
        self.form_container.setObjectName("CreateCommandsWidgets")
        self.form_container.hide()
        layout.addWidget(self.form_container)

        self.create_forms()

        layout.addStretch()
        
        self.open_folder_lnk = QPushButton("Открыть папку с ярлыками")
        self.open_folder_lnk.clicked.connect(self.main.open_folder_shortcuts)
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
        self.main.commands_manager.scan_and_copy_shortcuts()
        self.main.commands_manager.search_links()
        self.main.show_toast(f"Поиск завершен!")

        if hasattr(self.shortcut_form, 'refresh_shortcuts'):
            self.shortcut_form.refresh_shortcuts()

    def create_forms(self):
        """Создаем все формы заранее"""
        self.shortcut_form = AppCommandForm(self.main, self.links_file)
        self.form_container.addWidget(self.shortcut_form)

        self.folder_form = FolderCommandForm(self.main)
        self.form_container.addWidget(self.folder_form)

        self.url_form = UrlCommandForm(self.main)
        self.form_container.addWidget(self.url_form)

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
        logger.info("Обнаружены изменения в папке")
        self.refresh_file_list()
    
    def refresh_file_list(self):
        """Обновить список файлов в GUI"""
        self.main.commands_manager.search_links()

        if hasattr(self.shortcut_form, 'refresh_shortcuts'):
            self.shortcut_form.refresh_shortcuts()
            self.main.show_toast(f"Список ярлыков обновлен!")

        

class AppCommandForm(QWidget):
    def __init__(self, main, links_file, parent=None):
        super().__init__(parent)
        self.main = main
        self.links_file = links_file
        self.main.commands_manager.search_links()
        self.commands_manager = main_commands_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addStretch()

        self.key_input = QLineEdit(self)
        self.key_input.setPlaceholderText("Введите команду (например: 'браузер')")
        self.key_input.returnPressed.connect(self.apply_command)
        self.key_input.setProperty("helpId", "key_input_app")

        # Label для ошибок
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        self.label_command = QLabel("Команда (уникальное слово):")
        self.label_command.setStyleSheet("background: transparent;")
        self.label_command.setProperty("helpId", "key_input_app")

        self.shortcut_combo = SearchComboBox(self)
        self.load_shortcuts()
        self.shortcut_combo.lineEdit().returnPressed.connect(self.apply_command)
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
        try:
            with open(self.links_file, 'r', encoding='utf-8') as file:
                links = json.load(file)
                self.shortcut_combo.updateModel(links)
        except Exception as e:
            logger.error(f"Ошибка загрузки ярлыков: {e}")

    def refresh_shortcuts(self):
        self.load_shortcuts()
        current_selection = self.shortcut_combo.currentText()
        try:
            with open(self.links_file, 'r', encoding='utf-8') as file:
                links = json.load(file)
                self.shortcut_combo.updateModel(links)
                if current_selection in links:
                    self.shortcut_combo.setCurrentText(current_selection)
        except Exception as e:
            logger.error(f"Ошибка загрузки ярлыков: {e}")

    def apply_command(self):
        key = self.key_input.text().strip().lower()
        selected_name = self.shortcut_combo.currentFileName()

        if not key:
            self.show_error("Команда не может быть пустой!")
            return

        if key in self.commands_manager.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return

        if not selected_name:
            self.show_error("Пожалуйста, выберите ярлык из списка!")
            return
        
        new_command = {
            "name": selected_name,
            "desc": f"Ярлык {selected_name}",
            "type": "shortcut"
        }

        self.commands_manager.commands[key] = new_command
        commands_signal.commands_updated.emit()
        self.main.show_toast(message=f"Команда '{key}' добавлена!")
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
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.commands_manager = main_commands_manager
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

        choice_layout = QHBoxLayout()
        choice_layout.setSpacing(5)

        self.folder_path = QLineEdit(self)
        self.folder_path.returnPressed.connect(self.apply_command)
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

        if key in self.commands_manager.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return
        
        folder_desc = os.path.basename(os.path.dirname(folder.rstrip('/\\')))
        new_command = {
            "name": folder,
            "desc": f"Папка {folder_desc}",
            "type": "folder"
        }

        self.commands_manager.commands[key] = new_command
        commands_signal.commands_updated.emit()
        self.main.show_toast(message=f"Команда '{key}' добавлена!")
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
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.commands_manager = main_commands_manager
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

        if key in self.commands_manager.commands:
            self.show_error(f"Команда '{key}' уже существует!")
            return

        # Проверяем, что это валидный URL
        normalized_url, _ = self.normalize_url_for_comparison(url)
        if not self.is_valid_url(normalized_url):
            self.show_error("Некорректный URL!")
            return
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        if ':' in domain:
            domain = domain.split(':')[0]

        new_command = {
            "name": url,
            "desc": f"Папка {domain}",
            "type": "url"
        }

        self.commands_manager.commands[key] = new_command
        commands_signal.commands_updated.emit()
        self.main.show_toast(f"Команда '{key}' добавлена!")
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