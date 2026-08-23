"""
Функции для запуска и закрытия программ и игр
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import webbrowser
from urllib.parse import urlparse
import psutil
import pygetwindow as gw
from win32com.client import Dispatch
from bin.lists import get_audio_paths, commands_list
from bin.default_commands_data import system_commands_data
from bin.run_scripts_thread import ScriptExecutionThread
from log_config import assist_log, logger
from bin.speak_functions import thread_react, thread_react_detail
from path_builder import get_path, get_app_data_dir
from PySide6.QtCore import QObject
from bin.signals import commands_signal
from config import dev_mode

if dev_mode:
    commands_file = get_path("user_data", "commands.json")
    process_names = get_path('user_data', 'process_names.json')
    settings_file = get_path('user_data', 'settings.json')
    folder_links = get_path('user_data', 'links')
    links_file = get_path('user_data', 'links.json')
else:
    commands_file = os.path.join(get_app_data_dir(), "user_data", "commands.json")
    process_names =  os.path.join(get_app_data_dir(), 'user_data', 'process_names.json')
    settings_file =  os.path.join(get_app_data_dir(), 'user_data', 'settings.json')
    folder_links = os.path.join(get_app_data_dir(), 'user_data', 'links')
    links_file = os.path.join(get_app_data_dir(), 'user_data', 'links.json')


class CommandsManager(QObject):
    def __init__(self):
        super().__init__()
        self.settings_file_path = settings_file
        self.settings = self.load_settings()
        self.speaker = None
        self.audio_paths = None
        self.steam_path = None
        self._script_threads = {}
        self.update_vaults()
        self.default_commands = commands_list
        self.commands_file_path = commands_file
        self.process_names_path = process_names
        self.commands = self.load_commands()
        converted = self.reduction_commands()
        logger.info(f"Преобразование в новый формат команд: {converted}")
        commands_signal.commands_updated.connect(self.reload_commands)

    def load_commands(self):
        """Загрузка команд из файла"""
        if not os.path.exists(self.commands_file_path):
            return {}
        try:
            with open(self.commands_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        
    def reload_commands(self):
        """Полная перезагрузка команд при сигнале"""
        self.save_commands()
        old_count = len(self.commands) if hasattr(self, 'commands') else 0
        self.commands = self.load_commands()  # Обновляем self.commands
        new_count = len(self.commands)
        
        logger.info(f"Команды обновлены: было {old_count}, стало {new_count}")
        self.save_commands()

        commands_signal.commands_reloaded.emit()

    def save_commands(self):
        """Сохранение команд в файл"""
        with open(self.commands_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.commands, f, ensure_ascii=False, indent=4)

    def get_type_command(self, command_key):
        """
        Получить тип команды по ключу
        """
        if command_key not in self.commands:
            return ""
        
        command_data = self.commands[command_key]
        
        # Если это словарь и есть поле type
        if isinstance(command_data, dict):
            return command_data.get('type', '')
        
        # Если строка или другой формат - тип неизвестен
        return ""
    
    def execute_script(self, script_key, action="open", callback=None):
        """Запуск скрипта"""
        logger.info(f"[SCRIPT] Запуск: {script_key}")
        
        # Останавливаем предыдущий если есть
        if script_key in self._script_threads:
            self.stop_script(script_key)
        
        # Создаем поток
        thread = ScriptExecutionThread(self, script_key, action)
        
        # Подключаем сигналы для callback если нужно
        if callback:
            thread.step_started.connect(
                lambda step, total: callback(step, total, "started")
            )
            thread.step_completed.connect(
                lambda step, total, success: callback(step, total, "completed" if success else "failed")
            )
            thread.script_finished.connect(
                lambda success: callback(0, 0, "finished" if success else "stopped")
            )
        
        thread.script_error.connect(
            lambda msg: logger.info(f"[SCRIPT ERROR] {msg}")
        )
        
        # Сохраняем
        self._script_threads[script_key] = thread
        
        # Запускаем
        thread.start()
        if action == "open":
            thread_react(self.audio_paths['start_script'])
        else:
            thread_react(self.audio_paths['close_folder'])
        return True
        
    def _handle_script_command(self, cmd_type, value, action, move, args):
        """Обработчик команды из скрипта (выполняется в основном потоке!)"""
        logger.info(f"[MAIN] Выполняю команду из скрипта: {cmd_type} -> {value}")
        
        if cmd_type == 'folder':
            self.handler_folder(value, move, react=False)
        elif cmd_type == 'links' or cmd_type == 'url' or cmd_type == 'shortcut':
            self.handler_links(value, move, added_args=args, react=False)
        elif cmd_type == 'system':
            self.handler_system_commands(value, move, react=False)
        else:
            logger.info(f"[MAIN] Неверный тип команды: {cmd_type}")
            
    def stop_script(self, script_key):
        """Остановить скрипт"""
        if script_key in self._script_threads:
            thread = self._script_threads[script_key]
            thread.stop()
            thread.wait()
            del self._script_threads[script_key]
            return True
        return False

    def reduction_commands(self):
        """
        Преобразование команд в новую структуру.
        Возвращает количество преобразованных команд.
        """
        if not self.commands:
            return 0
        
        converted_count = 0
        new_commands = {}
        
        for key, value in self.commands.items():
            # Если уже в новом формате, пропускаем
            if isinstance(value, dict) and 'name' in value and 'desc' in value:
                new_commands[key] = value
                continue
            
            # Преобразуем старый формат в новый
            converted_item = self._convert_item(key, value)
            new_commands[key] = converted_item
            converted_count += 1
        
        self.commands = new_commands
        self.save_commands()
        return converted_count
    
    def _convert_item(self, key, value):
        """Преобразование одного элемента"""
        if not isinstance(value, str):
            value = str(value)
        
        item_type = self._detect_type(value)
        
        if item_type == "url":
            description = self._get_link_description(value)
        elif item_type == "shortcut":
            description = self._get_shortcut_description(value)
        elif item_type == "folder":
            description = self._get_folder_description(value)
        else:
            description = "unknown"
        
        return {
            "name": value,
            "desc": description,
            "type": item_type
        }
    
    def _detect_type(self, value):
        """Определение типа элемента"""
        value_lower = value.lower().strip()

        if value_lower.startswith(('http://', 'https://', 'ftp://', 'ftps://')):
            return "url"

        shortcut_extensions = ['.lnk', '.url']

        ext = os.path.splitext(value_lower)[1]
        if ext in shortcut_extensions:
            return "shortcut"

        if self._is_folder_path(value):
            return "folder"
        
        return "unknown"
    
    def _is_file_path(self, value):
        """Проверка, является ли значение путем к файлу"""
        # Проверяем наличие расширения файла
        if '.' in os.path.basename(value) and len(os.path.splitext(value)[1]) <= 5:
            # Проверяем наличие диска или абсолютный путь
            if ((':' in value and '\\' in value) or 
                ('/' in value and len(value) > 1 and value[1] != ':') or
                value.startswith('\\\\')):  # UNC путь
                return True
        return False
    
    def _is_folder_path(self, value):
        """Проверка, является ли значение путем к папке"""
        # Проверяем наличие разделителей пути
        if '\\' in value or '/' in value:
            # Исключаем файлы с расширениями
            if '.' in os.path.basename(value) and len(os.path.splitext(value)[1]) <= 5:
                return False
            return True
        
        # Проверяем наличие диска (C:, D: и т.д.)
        if len(value) >= 2 and value[1] == ':' and value.endswith('/'):
            return True
            
        return False
    
    def _is_executable_path(self, value):
        """Проверка, является ли путь исполняемым файлом"""
        executable_extensions = [
            '.exe', '.com', '.msi', '.msp', '.msu', '.app', '.jar',
            '.py', '.rb', '.pl', '.php', '.run', '.out', '.elf'
        ]
        ext = os.path.splitext(value.lower())[1]
        return ext in executable_extensions
    
    def _get_link_description(self, url):
        """Получение описания для ссылки"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            # Если порт указан, убираем его
            if ':' in domain:
                domain = domain.split(':')[0]
            return f"Ссылка {domain}"
        except:
            return "Ссылка"
    
    def _get_shortcut_description(self, shortcut_path):
        """Получение описания для ярлыка"""
        name = os.path.basename(shortcut_path)

        return f"Ярлык {name}"
    
    def _get_folder_description(self, folder_path):
        """Получение описания для папки"""
        folder_name = os.path.basename(folder_path.rstrip('/\\'))
        if not folder_name:
            folder_name = os.path.basename(os.path.dirname(folder_path.rstrip('/\\')))
        return f"Папка {folder_name}"
    
    def _get_file_description(self, file_path):
        """Получение описания для файла"""
        file_name = os.path.basename(file_path)
        return f"Файл {file_name}"

    def add_command(self, key, value, description=None, type_override=None):
        """Добавление новой команды"""
        if type_override:
            item_type = type_override
        else:
            item_type = self._detect_type(value)
        
        if not description:
            if item_type == "ссылка":
                description = self._get_link_description(value)
            elif item_type == "ярлык":
                description = self._get_shortcut_description(value)
            elif item_type == "папка":
                description = self._get_folder_description(value)
            elif item_type == "файл":
                description = self._get_file_description(value)
            else:
                description = ""
        
        self.commands[key] = {
            "name": value,
            "desc": description,
            "type": item_type
        }
        self.save_commands()

    def load_settings(self):
        """Загрузка настроек из файла"""

        if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    return settings  # Возвращаем все настройки
            except json.JSONDecodeError:
                assist_log.error(f"Ошибка: файл {self.settings_file_path} содержит некорректный JSON.")
                logger.error(f"Ошибка: файл {self.settings_file_path} содержит некорректный JSON.")
        else:
            assist_log.error(f"Файл настроек {self.settings_file_path} не найден.")
            logger.error(f"Файл настроек {self.settings_file_path} не найден.")

        return {}  # Возвращаем пустой словарь, если файл не найден или ошибка

    def update_vaults(self):
        self.settings = self.load_settings()
        self.speaker = self.settings.get("voice", "johnny")
        self.audio_paths = get_audio_paths(self.speaker)
        self.steam_path = self.settings.get('steam_path', '')

    def get_target_path(self, shortcut_path):
        """Извлекает путь к исполняемому файлу и аргументы из ярлыка."""
        try:
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            return shortcut.Targetpath, shortcut.Arguments, shortcut.WorkingDirectory
        except Exception as e:
            assist_log.error(f"Ошибка при извлечении данных из ярлыка {shortcut_path}: {e}")
            logger.error(f"Ошибка при извлечении данных из ярлыка {shortcut_path}: {e}")
            return None, None, None

    def fix_path(self, path):
        """Заменяет обратные слэши на прямые в пути."""
        return path.replace("\\", "/")

    def get_process_name(self, target_path):
        """Извлекает имя процесса из пути к исполняемому файлу."""
        if target_path is None:
            return None
        return os.path.basename(target_path)

    def read_url_shortcut(self, url_path):
        """Читает .url файл и извлекает game_id или URL."""
        try:
            with open(url_path, 'r', encoding='utf-8') as file:
                content = file.read()

            for line in content.splitlines():
                if line.startswith('URL='):
                    url = line[4:]  # Извлекаем значение после "URL="
                    # Если это Steam-ссылка, извлекаем game_id
                    if url.startswith("steam://rungameid/"):
                        return url[18:]  # Возвращаем game_id
                    # Если это Epic Games-ссылка, возвращаем полный URL
                    elif url.startswith("com.epicgames.launcher://"):
                        return url
                    # Иначе возвращаем как есть (на случай других типов ссылок)
                    return url
            return None
        except Exception as e:
            raise Exception(f"Ошибка при чтении файла .url: {e}")


    def get_all_processes(self):
        """Возвращает список всех текущих процессов."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            processes.append(proc.info['name'])
        return processes

    def save_process_names(self, shortcut_name, process_names):
        """Сохраняет имена процессов в файл, обновляя данные, если они уже существуют."""
        try:
            new_data = {shortcut_name: process_names}

            if os.path.exists(self.process_names_path):
                with open(self.process_names_path, 'r', encoding='utf-8') as file:
                    try:
                        existing_data = json.load(file)  # Читаем весь JSON
                    except json.JSONDecodeError:
                        existing_data = []
            else:
                existing_data = []

            found = False
            for entry in existing_data:
                if shortcut_name in entry:
                    entry[shortcut_name] = process_names
                    found = True
                    break

            if not found:
                existing_data.append(new_data)

            with open(self.process_names_path, 'w', encoding='utf-8') as file:
                json.dump(existing_data, file, indent=4, ensure_ascii=False)
                file.write('\n')

            assist_log.info(f"Имена процессов для ярлыка '{shortcut_name}' сохранены в файл.")
            logger.info(f"Имена процессов для ярлыка '{shortcut_name}' сохранены в файл.")
        except Exception as e:
            assist_log.error(f"Ошибка при сохранении имен процессов: {e}")
            logger.error(f"Ошибка при сохранении имен процессов: {e}")

    def remove_process_names(self, shortcut_name):
        """
        Удаляет запись о процессах для удаленного ярлыка.
        
        :param shortcut_name: Имя файла ярлыка (например, 'chrome.lnk')
        """
        try:
            if not os.path.exists(self.process_names_path):
                assist_log.debug(f"Файл процессов не найден: {self.process_names_path}")
                return False
            
            # Читаем текущие данные
            with open(self.process_names_path, 'r', encoding='utf-8') as file:
                try:
                    existing_data = json.load(file)
                except json.JSONDecodeError:
                    existing_data = []
            
            # Ищем и удаляем запись
            initial_length = len(existing_data)
            existing_data = [entry for entry in existing_data if shortcut_name not in entry]
            
            # Если что-то удалили - сохраняем
            if len(existing_data) < initial_length:
                with open(self.process_names_path, 'w', encoding='utf-8') as file:
                    json.dump(existing_data, file, indent=4, ensure_ascii=False)
                    file.write('\n')
                
                assist_log.info(f"Процессы для удаленного ярлыка '{shortcut_name}' удалены из файла.")
                logger.info(f"Процессы для удаленного ярлыка '{shortcut_name}' удалены.")
                return True
            else:
                assist_log.debug(f"Запись для ярлыка '{shortcut_name}' не найдена в файле процессов.")
                return False
                
        except Exception as e:
            assist_log.error(f"Ошибка при удалении процессов для ярлыка '{shortcut_name}': {e}")
            logger.error(f"Ошибка при удалении процессов: {e}")
            return False

    def get_process_names_from_file(self, shortcut_name):
        """Возвращает список имен процессов для указанного ярлыка из файла."""
        try:
            process_names = []
            if os.path.exists(self.process_names_path):
                with open(self.process_names_path, 'r', encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                        for entry in data:
                            if shortcut_name in entry:
                                process_names = entry[shortcut_name]
                                break
                    except json.JSONDecodeError:
                        assist_log.error("Ошибка: файл содержит некорректный JSON.")
                        logger.error("Ошибка: файл содержит некорректный JSON.")
            return process_names
        except Exception as e:
            assist_log.error(f"Ошибка при чтении имен процессов: {e}")
            logger.error(f"Ошибка при чтении имен процессов: {e}")
            return []

    def close_program(self, process_name):
        """Завершает все процессы с указанным именем."""
        try:
            result = subprocess.run(
                ['taskkill', '/IM', process_name, '/F'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp866'
            )
            logger.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
            # subprocess.run(['taskkill', '/IM', process_name, '/F'], check=True)
            logger.info(f"Процесс {process_name} успешно завершен.")
        except subprocess.CalledProcessError:
            assist_log.error(f"Не удалось завершить процесс {process_name}.")
            logger.error(f"Не удалось завершить процесс {process_name}.")
        except Exception as e:
            assist_log.error(f"Ошибка: {e}")
            logger.error(f"Ошибка: {e}")

    def search_links(self):
        """
        Поиск ярлыков по ключевой папке
        Получение и сохранение имени ярлыков в json
        """
        old_shortcuts = {}
        if os.path.exists(links_file):
            try:
                with open(links_file, 'r', encoding='utf-8') as file:
                    old_shortcuts = json.load(file)
            except:
                old_shortcuts = {}
        
        with open(links_file, 'w', encoding='utf-8') as file:
            file.write('{}')  # Записываем пустой JSON объект

        current_shortcuts = {}
        for filename in os.listdir(folder_links):
            if filename.endswith(".lnk") or filename.endswith(".url"):
                shortcut_path = os.path.join(folder_links, filename)
                current_shortcuts[filename] = shortcut_path

        removed_shortcuts = set(old_shortcuts.keys()) - set(current_shortcuts.keys())
        
        if removed_shortcuts:
            for shortcut_name in removed_shortcuts:
                self.remove_process_names(shortcut_name)
                logger.info(f"Ярлык '{shortcut_name}' удален, очистка процессов.")

        with open(links_file, 'w', encoding='utf-8') as file:
            json.dump(current_shortcuts, file, ensure_ascii=False, indent=4)
        
        logger.info(f"Ярлыки обновлены. Найдено: {len(current_shortcuts)}, удалено: {len(removed_shortcuts)}")


    def handler_links(self, filename, action, added_args=None, react=True):
        """
        Обработчик ярлыков в зависимости от их расширения.
        filename = путь к файлу;
        action = действие (open/close);
        react = флаг для регулировки реакции ассистента и запуска отслеживания новых процессов.
        """
        global game_id, target_path, process_name, game_id_or_url, workdir
        # Получаем путь к ярлыку
        shortcut_path = os.path.join(folder_links, filename)

        added_args_list = []
        if added_args:
            added_args_list = [arg.strip() for arg in added_args.split(',') if arg.strip()]
        
        # Локальная переменная для всех аргументов
        all_args = []

        # Обработка .lnk файлов
        if filename.endswith(".lnk"):
            try:
                target_path, arguments, workdir = self.get_target_path(shortcut_path)
                target_path = self.fix_path(target_path)

                # Правильное разбиение аргументов (учитывает кавычки)
                link_args = shlex.split(arguments) if arguments else []
                all_args = link_args + added_args_list

                process_name = self.get_process_name(target_path)
                if action == 'open':
                    self.open_link(filename, target_path, all_args, workdir, react)
                elif action == 'close':
                    self.close_link(filename, react)
            except Exception as e:
                assist_log.info(f"Ошибка при извлечении пути из ярлыка {filename}: {e}")
                logger.info(f"Ошибка при извлечении пути из ярлыка {filename}: {e}")

        # Обработка .url файлов (Steam и Epic Games)

        elif filename.endswith(".url"):
            try:
                game_id_or_url = self.read_url_shortcut(shortcut_path)
                if not game_id_or_url:
                    assist_log.info(f"Не удалось извлечь game_id или URL из файла {filename}")
                    logger.info(f"Не удалось извлечь game_id или URL из файла {filename}")
                    return  # Прекращаем выполнение, если не удалось извлечь URL

                if action == 'open':
                    self.open_url_link(game_id_or_url, filename, react)
                elif action == 'close':
                    self.close_link(filename, react)

            except Exception as e:
                assist_log.info(f"Ошибка при чтении .url файла {filename}: {e}")
                logger.info(f"Ошибка при чтении .url файла {filename}: {e}")

        elif self.is_url_string(filename):
            try:
                if action == 'open':
                    self.open_browser_link(filename, react)

            except Exception as e:
                assist_log.info(f"Ошибка при обработке ссылки: {filename}: {e}")
                logger.info(f"Ошибка при обработке ссылки: {filename}: {e}")
            return

    def handler_folder(self, folder_path, action, react=True):
        """
        Обработчик команд для открытия и закрытия папок
        :param folder_path: путь к папке
        :param action: действие(open or close)
        :return: True если успешно, False если не удалось
        """
        if action == 'open':
            try:
                os.startfile(folder_path)
                if react:
                    thread_react(self.audio_paths['start_folder'])
                return True
            except Exception as e:
                assist_log.error(f"Не удалось открыть папку {folder_path}: {e}")
                logger.error(f"Не удалось открыть папку {folder_path}: {e}")
                return False

        if action == 'close':
            windows = gw.getAllTitles()
            folder_title = os.path.basename(folder_path)

            try:
                for title in windows:
                    if folder_title in title:
                        window_list = gw.getWindowsWithTitle(title)
                        if window_list:
                            window = window_list[0]
                            window.close()
                            if react:
                                thread_react(self.audio_paths.get('close_folder'))
                            assist_log.info(f"Окно '{title}' закрыто.")
                            return True
                        else:
                            logger.warning(f"Окно с заголовком '{title}' найдено,"
                                                 f"но не удалось получить объект.")
                logger.warning(f"Окно с названием '{folder_title}' не найдено среди открытых.")
                return False

            except Exception as e:
                error_file = self.audio_paths.get('error_file')
                if error_file:
                    thread_react_detail(error_file)
                assist_log.error(f"Ошибка при попытке закрыть окно: {e}")
                logger.error(f"Ошибка при попытке закрыть окно: {e}")
                return False

    def open_url_link(self, game_id_or_url, filename, react):
        existing_processes = self.get_process_names_from_file(filename)
        try:
            if existing_processes:
                logger.info(f"Используем сохраненные процессы для '{filename}'")

                if game_id_or_url.startswith("com.epicgames.launcher://"):
                    subprocess.Popen(["start", game_id_or_url], shell=True)
                else:
                    subprocess.Popen([self.steam_path, '-applaunch', game_id_or_url], shell=True)

                if react:
                    thread_react(self.audio_paths['start_folder'])
                return

            # Запускаем игру
            if game_id_or_url.startswith("com.epicgames.launcher://"):
                subprocess.Popen(["start", game_id_or_url], shell=True)
            else:
                subprocess.Popen([self.steam_path, '-applaunch', game_id_or_url], shell=True)

            # Запускаем мониторинг в фоне
            if react:
                self.monitor_processes(filename, lambda procs, fname: self.on_monitoring_done(procs, fname, self.audio_paths))

                thread_react_detail(self.audio_paths['wait_load_file'])

        except Exception as e:
            assist_log.error(f"Ошибка при открытии игры: {e}")
            logger.error(f"Ошибка при открытии игры: {e}")
            thread_react_detail(self.audio_paths['error_file'])

    def on_monitoring_done(self, processes, filename, audio_paths):
        """Обработчик завершения мониторинга"""
        if processes:
            self.save_process_names(filename, processes)
            thread_react_detail(audio_paths['done_load_file'])
        else:
            assist_log.info("Новые процессы не обнаружены")
            logger.info("Новые процессы не обнаружены")
            thread_react_detail(audio_paths['error_file'])

    def open_link(self, filename, target_path, arguments, workdir, react):
        """
        Улучшенная функция для открытия ярлыков (.lnk) с фоновым мониторингом
        """
        try:
            # Проверки файла
            if not os.path.exists(target_path):
                assist_log.error(f"Целевой файл не существует: {target_path}")
                logger.error(f"Целевой файл не существует: {target_path}")
                thread_react_detail(self.audio_paths['error_file'])
                return False

            if not os.access(target_path, os.R_OK | os.X_OK):
                assist_log.error(f"Нет доступа к файлу: {target_path}")
                logger.error(f"Нет доступа к файлу: {target_path}")
                thread_react_detail(self.audio_paths['error_file'])
                return False

            if not workdir:
                workdir = os.path.dirname(target_path)

            # Проверяем сохраненные процессы
            existing_processes = self.get_process_names_from_file(filename)

            # Формируем команду
            command = [target_path] + arguments

            # Запускаем процесс
            process = subprocess.Popen(
                command,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ,
                shell=False
            )

            # Логирование в фоне
            threading.Thread(
                target=self.log_stream,
                args=(process.stdout, logger),
                daemon=True
            ).start()

            threading.Thread(
                target=self.log_stream,
                args=(process.stderr, logger),
                daemon=True
            ).start()

            # Если процессы известны - просто запускаем
            if existing_processes:
                logger.info(f"Используем сохраненные процессы для '{filename}'")
                if react:
                    thread_react(self.audio_paths['start_folder'])
                return True

            # Если процессов нет - запускаем мониторинг
            if react:
                thread_react_detail(self.audio_paths['wait_load_file'])
                self.monitor_processes(filename,
                                    lambda procs, fname: self.on_monitoring_done(procs, fname, self.audio_paths))

            return True

        except FileNotFoundError as e:
            assist_log.error(f"Файл не найден: {e}")
            logger.error(f"Файл не найден: {e}")
            thread_react_detail(self.audio_paths['error_file'])
            return False

        except PermissionError as e:
            assist_log.error(f"Ошибка доступа: {e}")
            logger.error(f"Ошибка доступа: {e}")
            thread_react_detail(self.audio_paths['error_file'])
            return False

        except Exception as e:
            assist_log.error(f"Неожиданная ошибка: {e}", exc_info=True)
            logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
            thread_react_detail(self.audio_paths['error_file'])
            return False

    def close_link(self, filename, react):
        """
        Функция для закрытия программы
        :param filename: Имя файла
        """
        process_names = self.get_process_names_from_file(filename)  # Читаем имена процессов из файла
        if process_names:
            for process_name in process_names:
                self.close_program(process_name)  # Завершаем каждый процесс по имени
        else:
            assist_log.error("Имена процессов не найдены.")
            logger.error("Имена процессов не найдены.")
            error_file = self.audio_paths['error_file']
            thread_react_detail(error_file)
        if react:
            thread_react(self.audio_paths['close_folder'])
        assist_log.info("Все процессы завершены.")
        logger.info("Все процессы завершены.")

    def create_shortcut(self, target_path, shortcut_path, description=""):
        """Создаёт ярлык для target_path и сохраняет его в shortcut_path."""
        try:
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = target_path
            shortcut.Description = description
            shortcut.WorkingDirectory = os.path.dirname(target_path)
            shortcut.save()
            return True
        except Exception as e:
            logger.error(f"Ошибка создания ярлыка {shortcut_path}: {str(e)}")
            return False

    def should_skip_file(self, filename):
        """Проверяет, нужно ли пропускать файл"""
        # Список исключаемых файлов
        EXCLUDED_FILES = {
            "immersive control panel.lnk",
            "uninstall.lnk",
            "control panel.lnk",
            "корзина.lnk",
            "этот компьютер.lnk",
            "панель управления.lnk",
            "сеть.lnk",
            "документы.lnk"
        }
        return filename.lower() in EXCLUDED_FILES

    def scan_programs_folder(self, target_dir):
        """
        Сканирует только папку Programs верхнего уровня (без подпапок)
        и копирует ярлыки/создаёт ярлыки для exe
        """
        programs_folder = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')

        if not os.path.exists(programs_folder):
            logger.warning(f"Папка Programs не найдена: {programs_folder}")
            return False

        logger.info(f"Сканирую папку Programs: {programs_folder}")

        try:
            items = os.listdir(programs_folder)
        except PermissionError:
            logger.error(f"Нет доступа к папке: {programs_folder}")
            return False

        for item in items:
            item_path = os.path.join(programs_folder, item)

            # Пропускаем подпапки
            if os.path.isdir(item_path):
                continue

            file_ext = os.path.splitext(item)[1].lower()

            if self.should_skip_file(item):
                logger.info(f"Пропускаем системный файл: {item}")
                continue

            try:
                # Обрабатываем только .lnk и .exe
                if file_ext == '.lnk' or file_ext == ".url":
                    # Копируем ярлык
                    dest_path = os.path.join(target_dir, item)
                    shutil.copy2(item_path, dest_path)
                    logger.info(f"Скопирован ярлык из Programs: {item}")
                elif file_ext == '.exe':
                    # Создаём ярлык для exe
                    shortcut_name = f"{os.path.splitext(item)[0]}.lnk"
                    shortcut_path = os.path.join(target_dir, shortcut_name)

                    if not os.path.exists(shortcut_path):
                        self.create_shortcut(item_path, shortcut_path)
                        logger.info(f"Создан ярлык для exe из Programs: {item}")
            except Exception as e:
                logger.error(f"Ошибка обработки {item}: {str(e)}")
                continue

        return True

    def scan_desktop_folders(self, target_dir):
        """
        Сканирует рабочие столы (основной и OneDrive) с подпапками
        и копирует ярлыки/создаёт ярлыки для exe
        """
        desktop_paths = [
            os.path.join(os.environ["USERPROFILE"], "Desktop"),
            os.path.join(os.environ["USERPROFILE"], "OneDrive", "Desktop")
        ]

        for desktop_path in desktop_paths:
            if not os.path.exists(desktop_path):
                logger.warning(f"Папка рабочего стола не найдена: {desktop_path}")
                continue

            logger.info(f"Сканирую рабочий стол: {desktop_path}")

            for root, _, files in os.walk(desktop_path):
                for file in files:
                    file_path = os.path.join(root, file)

                    if self.should_skip_file(file):
                        logger.info(f"Пропускаем системный файл: {file}")
                        continue

                    file_ext = os.path.splitext(file)[1].lower()

                    try:
                        if file_ext == ".lnk" or file_ext == ".url":
                            dest_path = os.path.join(target_dir, file)
                            shutil.copy2(file_path, dest_path)
                            logger.info(f"Скопирован ярлык с рабочего стола: {file}")
                        elif file_ext == ".exe":
                            shortcut_name = f"{os.path.splitext(file)[0]}.lnk"
                            shortcut_path = os.path.join(target_dir, shortcut_name)

                            if not os.path.exists(shortcut_path):
                                self.create_shortcut(file_path, shortcut_path)
                                logger.info(f"Создан ярлык для exe с рабочего стола: {file}")
                    except Exception as e:
                        logger.error(f"Ошибка обработки {file}: {str(e)}")
                        continue

        return True

    def scan_and_copy_shortcuts(self):
        """Основная функция сканирования (оба метода)"""
        if not os.path.exists(folder_links):
            try:
                os.makedirs(folder_links)
            except PermissionError:
                logger.error(f"Нет прав на создание папки: {folder_links}")
                return False

        # Сканируем папку Programs без подпапок
        self.scan_programs_folder(folder_links)

        # Сканируем рабочие столы с подпапками
        self.scan_desktop_folders(folder_links)

        logger.info(f"Готово! Ярлыки сохранены в: {folder_links}")
        return True

    def log_stream(self, stream, assist_log):
        for line in stream:
            assist_log.info(line.decode('cp866', errors='replace').strip())

    def monitor_processes(self, filename, callback):
        """Мониторинг процессов в отдельном потоке"""

        def _monitor():
            before = set(self.get_all_processes())
            found = []
            start_time = time.time()

            while time.time() - start_time < 40:
                time.sleep(1)
                current = set(self.get_all_processes())
                new = current - before

                for proc in new:
                    if proc not in found:
                        found.append(proc)
                        assist_log.info(f"Найден новый процесс: {proc}")

                if new:
                    before = current

            callback(found, filename)

        threading.Thread(target=_monitor, daemon=True).start()

    def open_browser_link(self, url, react):
        """
        Открывает ссылку в браузере с обработкой различных форматов
        """
        try:
            # Очищаем URL от лишних пробелов
            url = url.strip()

            # Если URL пустой
            if not url:
                return False

            # Проверяем, есть ли протокол в URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                # Добавляем http:// если протокола нет
                url = 'http://' + url

            # Открываем в браузере
            webbrowser.open(url)
            if react:
                thread_react(self.audio_paths['start_folder'])
            return True

        except Exception as e:
            assist_log.error(f"Ошибка при открытии ссылки '{url}': {e}")
            logger.error(f"Ошибка при открытии ссылки '{url}': {e}")
            return False

    def is_url_string(self, text):
        """
        Проверяет, является ли строка URL, а не путем к файлу
        """
        if not text or not isinstance(text, str):
            return False

        text = text.strip()
        logger.info(f"Проверка сайта: {text}")
        # Проверка на признаки URL
        url_indicators = [
            # Протоколы
            r'^https?://',
            r'^ftp://',
            r'^file://',
            r'^mailto:',
            # Доменные имена
            r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',  # domain.tld
            r'^www\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',  # www.domain.tld
            # localhost и IP-адреса
            r'^localhost',
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP address
        ]

        for pattern in url_indicators:
            if re.match(pattern, text, re.IGNORECASE):
                return True

        return False
    
    def handler_system_commands(self, command, action, react=True):
        for keyword, command_data in system_commands_data.items():
            if keyword in command:
                method = command_data.get(action)
                if method:
                    method(react)
                    return True
        return False


main_commands_manager = CommandsManager()

