import uuid
import time
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QLineEdit, QComboBox, QScrollArea
from PySide6.QtCore import Signal, QTimer, Qt, QRegularExpression
from bin.commands_manager import main_commands_manager
from mygui import CustomSvgWidget, main_apply_colors
from bin.utils import setup_custom_font_label
from bin.signals import commands_signal
from log_config import logger
from path_builder import get_path


class ScriptStepWidget(QWidget):
    """Виджет одного шага в сценарии"""
    stepRemoved = Signal(int)
    stepMovedUp = Signal(int)
    stepMovedDown = Signal(int)
    stepChanged = Signal()
    
    def __init__(self, step_number, parent=None):
        super().__init__(parent)
        self.style_manager = main_apply_colors
        self.step_number = step_number
        self.commands_manager = main_commands_manager
        self.available_commands = []
        self.icon_arrowup_path = get_path("bin", "icons", "arrow_up.svg")
        self.icon_arrowdown_path = get_path("bin", "icons", "arrow_down.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        commands_signal.commands_reloaded.connect(self._populate_commands)
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("ScriptStepFrame")
        layout = QHBoxLayout(main_widget)
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

    def get_available_commands(self):
        """Получить все доступные команды"""
        all_commands = {**self.commands_manager.default_commands, **self.commands_manager.commands}
        return all_commands

    def _populate_commands(self, include_scripts=False):
        """Заполняем список доступных команд"""
        self.cmb_command.clear()
        self.cmb_command.addItem("-- Выберите команду --", None)

        self.available_commands = self.get_available_commands()
        
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
    def __init__(self, script_key=None, commands_manager=None, main=None, is_editor=False, parent=None):
        super().__init__(parent)
        self.commands_manager = commands_manager
        self.main = main
        self.is_editor = is_editor
        self.editing_key = script_key
        self.steps = []  # список виджетов шагов
        self._help_initialized = False
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
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
        scroll_widget.setObjectName("CustomPageContent")
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
        lbl_name.setStyleSheet("background: transparent; font-size: 15px;")
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
            
        step_widget = ScriptStepWidget(len(self.steps) + 1, self)
        
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
        logger.info(f"Общая задержка скрипта: {total_delay}с, очистка через {cleanup_delay_ms}мс")
        
        try:
            # Временно сохраняем в commands_manager
            self.commands_manager.commands[temp_script_key] = script_data
            logger.info(f"Тестовый скрипт сохранен как: {temp_script_key}")
            
            # Запоминаем время начала
            self._test_start_time = time.time()
            
            # Выполняем тестовый скрипт
            self.commands_manager.execute_script(temp_script_key)
            
            # Очищаем через вычисленное время
            QTimer.singleShot(cleanup_delay_ms, lambda: self._cleanup_temp_script(temp_script_key))
            
        except Exception as e:
            logger.error(f"Ошибка запуска теста: {e}")
            self._cleanup_temp_script(temp_script_key)
            self.lbl_status.setText(f"Ошибка: {e}")

    def _cleanup_temp_script(self, temp_key):
        """Очистка временного скрипта"""
        if temp_key in self.commands_manager.commands:
            del self.commands_manager.commands[temp_key]
            elapsed = getattr(self, '_test_start_time', None)
            if elapsed:
                elapsed = time.time() - self._test_start_time
                logger.info(f"Тестовый скрипт удален: {temp_key} (выполнялся {elapsed:.1f}с)")
            else:
                logger.info(f"Тестовый скрипт удален: {temp_key}")
        
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
        
        self.main.show_toast(f"Сценарий '{script_data['name']}' сохранен!")
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