import json
import os
from bin.lists import default_keywords_data, setup_custom_font_label
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QMessageBox, QLineEdit, QComboBox, QListWidget, QScrollArea, QFrame, QListWidgetItem
from PySide6.QtCore import Qt
from path_builder import get_path


class SpeechHookManagerWidget(QWidget):
    def __init__(self, main_window=None, user_keywords=None, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.default_path = get_path("bin", "default_keywords.json")
        self.user_path = user_keywords
        self.default_keywords = {}
        self.user_keywords = {}
        self.current_list = None
        self._help_initialized = False
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_data()
        self.init_ui()
        self.load_data()

    def refresh_data(self):
        self.init_data()
        self.load_data()
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True
    
    def init_ui(self):
        """Инициализация интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        content_widget.setObjectName("CustomPageContent")
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.title = setup_custom_font_label("Менеджер управления хук-словами")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        list_selection_layout = QHBoxLayout()
        
        self.list_selector = QComboBox()
        self.list_selector.currentIndexChanged.connect(self.on_list_changed)
        self.list_selector.setProperty("helpId", "list_selector")
        list_selection_layout.addWidget(self.list_selector)
        
        layout.addLayout(list_selection_layout)

        self.words_list = QListWidget()
        self.words_list.setStyleSheet("font-size: 15px;")
        self.words_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.words_list.customContextMenuRequested.connect(self.show_context_menu)
        self.words_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.words_list.setProperty("helpId", "words_list")
        layout.addWidget(self.words_list)

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

        self.reset_button = QPushButton("Сбросить к значениям по умолчанию")
        self.reset_button.clicked.connect(self.reset_to_default)
        self.reset_button.setProperty("helpId", "reset_words_list")
        layout.addWidget(self.reset_button)

        main_layout.addWidget(scroll_area)


    def load_data(self):
        sorted_keys = sorted(self.user_keywords.keys(), key=lambda k: self.get_display_name(k))
        for key in sorted_keys:
            self.list_selector.addItem(self.get_display_name(key), key)

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
        self.main.apply_keywords_for_values()
    
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
        reply = self.main.show_message(
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
            self.main.show_toast("Такое слово уже есть в списке!")
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
        reply = self.main.show_message(
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
            
            self.main.show_toast("Команды сброшены к значениям по умолчанию!")


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