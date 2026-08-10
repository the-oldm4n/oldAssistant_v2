import json
import os
import re
from urllib.parse import urlparse
import uuid
import time
import subprocess
from bin.base_modules.stacked_widget import SlidingStackedWidget
from widgets.commands_widgets.simple_script_form import SimpleScriptForm
import win32com.client
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QMessageBox, QLineEdit, QStackedWidget, QFileDialog, QListWidget, QListWidgetItem,\
    QDialogButtonBox, QComboBox, QCompleter, QScrollArea, QSpinBox, QTabBar, QTabWidget
from PySide6.QtCore import Signal, QTimer, Qt, QStringListModel, QRegularExpression
from bin.commands_manager import main_commands_manager
from mygui import CustomSvgWidget, main_apply_colors, color_signal
from bin.utils import setup_custom_font_label
from bin.shortcut_monitor import ShortcutMonitor
from bin.signals import commands_signal
from log_config import debuglog
from path_builder import get_path, get_app_data_dir
from config import dev_mode


class CreateScriptsWidget(QWidget):
    def __init__(self, main, links_file, parent=None):
        super().__init__(parent)
        self.main = main
        self.links_file = links_file
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.commands_manager = main_commands_manager #self.main.commands_manager
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
        self.simple_form = SimpleScriptForm(commands_manager=self.commands_manager, main=self.main)
        self.form_container.addWidget(self.simple_form)

        self.autostart_form = TaskSchedulerWidget(commands_manager=self.commands_manager, main=self.main, links_file=self.links_file)
        self.form_container.addWidget(self.autostart_form)

    def show_script_simple(self):
        self.form_container.setCurrentWidget(self.simple_form)
        
    def show_script_autostart(self):
        self.form_container.setCurrentWidget(self.autostart_form)
   

class TaskSchedulerWidget(QWidget):
    def __init__(self, commands_manager=None, main=None, links_file=None, parent=None):
        super().__init__(parent)
        self.commands_manager = commands_manager
        self.main = main
        self.links_file = links_file
        self.links = self.load_links()
        self._help_initialized = False
        self.setObjectName("TaskSchedulerWidget")
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def refresh_data(self):
        self.links = self.load_links()
        self.populate_shortcuts()

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
        self.open_folder.clicked.connect(self.main.open_folder_shortcuts)
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
            debuglog.error(f"Ошибка загрузки файла ярлыков: {e}")
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
            debuglog.error(f"Ошибка чтения ярлыка {lnk_path}: {e}")
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
            debuglog.info(f"Задача найдена")
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
            reg_info.Author = "main App"
            
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
            
            debuglog.info(f"Задача '{task_name}' зарегистрирована")
            
            # Проверяем, что задача действительно создана
            try:
                check_task = root_folder.GetTask(task_name)
                if check_task:
                    debuglog.info(f"Задача '{task_name}' успешно проверена в планировщике")
                    pythoncom.CoUninitialize()
                    return True
                else:
                    debuglog.error(f"Задача '{task_name}' не найдена после создания")
                    pythoncom.CoUninitialize()
                    return False
                    
            except Exception as verify_error:
                debuglog.error(f"Ошибка проверки задачи: {verify_error}")
                
                # Пробуем альтернативный способ проверки
                if self.check_task_exists(task_name):
                    debuglog.info(f"Задача найдена альтернативным способом")
                    pythoncom.CoUninitialize()
                    return True
                
                pythoncom.CoUninitialize()
                return False
                
        except Exception as e:
            debuglog.error(f"Ошибка создания задачи: {e}")

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
                debuglog.info(f"Файл задачи найден: {task_path}")
                return True
            
            # Альтернативный путь
            alt_path = f"C:\\Windows\\Tasks\\{task_name}"
            if os.path.exists(alt_path):
                debuglog.info(f"Файл задачи найден: {alt_path}")
                return True
                
            debuglog.info(f"Файл задачи не найден: {task_name}")
            return False
            
        except Exception as e:
            debuglog.error(f"Ошибка проверки файла: {e}")
            return False