import json
import os
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMessageBox, QLineEdit, QListWidget, QDialogButtonBox
from PySide6.QtCore import Qt
from bin.utils import setup_custom_font_label


class ProcessLinksWidget(QWidget):
    """ Класс для обработки окна "Процессы ярлыков" """

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._help_initialized = False
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.process_names_path = self.main.process_names
        self.process_names = self.load_process_names()
        self.init_ui()

    def refresh_data(self):
        self.update_links_list()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
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
            self.main.show_message("Выберите ярлык для добавления процесса.", "Ошибка", "error")
            return

        link_name = current_link.text()
        self.add_custom_process(link_name)

    def remove_process(self):
        """ Удаляет процесс из выбранного ярлыка """
        current_link = self.links_list.currentItem()
        current_process = self.processes_list.currentItem()
        if not current_link or not current_process:
            self.main.show_message("Выберите ярлык и процесс для удаления.", "Ошибка", "error")
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