import json
from widgets.commands_widgets.edit_script_dialog import EditScriptDialog
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QLineEdit, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from bin.commands_manager import main_commands_manager
from bin.utils import setup_custom_font_label
from bin.signals import commands_signal


class CommandsWidget(QWidget):
    """Класс для обработки окна 'Добавленные команды'"""

    def __init__(self, main, commands_file, parent=None):
        super().__init__(parent)
        self.main = main
        self.commands_file = commands_file
        self._help_initialized = False
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.commands_manager = main_commands_manager
        self.init_ui()
        self.update_commands_list()
        commands_signal.commands_reloaded.connect(self.update_commands_list)

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
        self.commands_list.setObjectName("CustomPageContent")
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
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
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
                if key in self.main.commands:
                    cmd_data = self.main.commands[key]
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
        if script_key not in self.main.commands:
            return
        
        script_data = self.main.commands[script_key]
        if not isinstance(script_data, dict) or script_data.get('type') != 'script':
            return
        
        # Открываем диалог редактирования скрипта
        dialog = EditScriptDialog(
            script_key=script_key,
            script_data=script_data,
            commands_manager=self.main.commands_manager,
            parent=self
        )
        
        if dialog.exec_() == QDialog.DialogCode.Accepted:
            # Обновляем скрипт
            updated_data = dialog.get_updated_script_data()
            self.main.commands[script_key] = updated_data

            with open(self.commands_file, 'w', encoding='utf-8') as file:
                json.dump(self.main.commands, file, ensure_ascii=False, indent=4)

            self.update_commands_list()
            self.main.show_toast(f"Сценарий '{script_key}' обновлен")

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
                main=self.main,
                parent=self
            )

            if dialog.exec_() == QDialog.DialogCode.Accepted:
                new_key = dialog.new_key

                if current_key in self.commands_manager.commands:
                    command_value = self.commands_manager.commands[current_key]
                    del self.commands_manager.commands[current_key]
                    self.commands_manager.commands[new_key] = command_value
                    commands_signal.commands_updated.emit()
                    self.main.show_message(f"Команда успешно переименована в '{new_key}'", "Успех", "info")

    def update_commands_list(self):
        """Обновляет список команд"""
        self.commands_list.clear()

        for key, command_data in self.commands_manager.commands.items():
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
            self.main.show_message("Выберите команду для удаления", "Предупреждение", "warning")
            return

        # Удаляем выбранные команды
        for item in selected_items:
            key = item.text().split(" : ")[0]
            if key in self.commands_manager.commands:
                del self.commands_manager.commands[key]
                self.commands_list.takeItem(self.commands_list.row(item))

        commands_signal.commands_updated.emit()
        self.select_last_item()


class EditCommandDialog(QDialog):
    """Кастомное диалоговое окно ввода с валидацией"""

    def __init__(self, current_key="", current_value="", main=None, parent=None):
        super().__init__(parent)
        self.current_key = current_key
        self.current_value = current_value
        self.main = main
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
        if new_key in self.main.commands:
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