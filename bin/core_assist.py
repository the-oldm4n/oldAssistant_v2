
import json
import os
import csv
import time
import traceback
import jellyfish
import threading
import sounddevice as sd
import numpy as np
from vosk import Model, KaldiRecognizer
from PySide6.QtGui import QCursor, QIcon, QFont, QAction, QFontDatabase
from PySide6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QWidget,\
    QDialog, QSizePolicy, QSystemTrayIcon, QMenu, QMessageBox, QSpacerItem
from PySide6.QtCore import Signal, QTimer, Qt, QEvent, QObject
from bin.base_modules.toast_notification import ToastNotif
from bin.bluetooth_controller import bluetooth_controller
from bin.base_modules.config_manager import get_config_value, set_config_value, update_version
from bin.function_list_main import close_volume_mixer, greeting, open_volume_mixer, open_calc, close_calc, open_paint, close_paint, \
    open_taskmgr, close_taskmgr, open_path, open_recycle_bin, close_recycle_bin, open_appdata, close_appdata, restart_windows, search_yandex, shutdown_windows
from bin.toggle_mute_discord import ToggleMuteDiscord
from path_builder import get_app_data_dir, get_path
from bin.audio_control import controller
from bin.speak_functions import thread_play_sound, thread_react_detail, thread_react, react
from bin.lists import get_audio_paths, commands_list, default_keywords_data
from bin.speak_functions import react, thread_react, thread_react_detail
from bin.signals import censor_signal, gui_signals
from log_config import assist_log, logger


class AssistManager(QObject):
    supply_notice_signal = Signal(str, bool)
    def __init__(self, main_window=None, user_keywords=None, vosk_model_ru_path=None, parent=None):
        super().__init__(parent)
        self.supply_notice_signal.connect(self._handle_supply_notice)
        self.main = main_window
        self.user_keywords = user_keywords
        self.is_running = False
        self.vosk_model_ru = vosk_model_ru_path
        self.assistant_thread = None
        self.audio_paths = get_audio_paths(self.main.speaker)
        self.audio_stream = None
        self.last_audio_time = None  # Время последнего НЕтихого пакета
        self.microphone_available = True
        
        self.silence_timer = QTimer()  # Таймер для проверки тишины
        self.silence_timer.timeout.connect(self.check_silence_timeout)
        self.silence_timer.start(5000)
        self.bluetooth = bluetooth_controller

    def show_supply_notice(self, message, is_confirm=False):
        """Вызывается из фонового потока - emits signal"""
        try:
            self.supply_notice_signal.emit(message, is_confirm)
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при отправке сигнала уведомления: {e}")

    def _handle_supply_notice(self, message, is_confirm=False):
        """Выполняется в главном потоке Qt (обработчик сигнала)"""
        try:
            if is_confirm:
                default_text = ""
            else:
                default_text = "Распознано: "
            toast = ToastNotif(
                parent=None,
                message=f"{default_text}{message}",
                timeout=5000
            )
            toast.show_toast()

        except Exception as e:
            logger.error(f"[MAIN] Ошибка при показе всплывающего уведомления: {e}")

    def update_audio_path(self, speaker):
        self.audio_paths = get_audio_paths(speaker)

    def start_assist_toggle(self):
        """Обработка нажатия кнопки 'Старт ассистента' или 'Остановить работу'"""
        if self.is_running:
            self.stopped()
        else:
            self.run_assist()

    def run_assist(self):
        """Запуск ассистента"""
        result, message = self.apply_keywords_for_values()
        if not result:
            self.main.show_message(title="Ошибка", text=message, message_type="warning")
            return
        
        self.is_running = True
        self.main.animated_sidebar.update_element_text("toggle_worker", "Остановить работу")
        assist_log.debug("Ассистент запущен...")

        # Запуск ассистента в отдельном потоке
        self.assistant_thread = threading.Thread(target=self.voice_handler)
        self.assistant_thread.start()

    def stopped(self, reaction=True):
        """Остановка ассистента"""
        self.is_running = False
        self.main.animated_sidebar.update_element_text("toggle_worker", "Старт ассистента")
        logger.info("[ASSIST MANAGER][Ассистент остановлен]")
        if reaction:
            logger.info("[ASSIST MANAGER] Реакция на выключение ассистента...")
            self.get_reaction(threading=True, name="close_assist_folder", trace="stopped in ASSIST MANAGER")

        # Безопасная остановка потока
        if hasattr(self, 'assistant_thread') and self.assistant_thread is not None:
            try:
                if self.assistant_thread.is_alive() and self.assistant_thread != threading.current_thread():
                    self.assistant_thread.join(timeout=1.0)
                    if self.assistant_thread.is_alive():
                        logger.warning("[ASSIST MANAGER] Поток ассистента не завершился в течение таймаута")
            except Exception as e:
                logger.error(f"[ASSIST MANAGER] Ошибка при остановке потока: {e}")
            finally:
                self.assistant_thread = None

        # Очистка аудиоресурсов
        self.cleanup_audio_resources()

    def get_reaction(self, threading=True, detail=False, name="", trace=""):
        try:
            path = self.audio_paths.get(f'{name}')
            if not path:
                assist_log.error(f"[ASSIST MANAGER][assistant.get_reaction] Путь не найден")
                logger.error(f"[ASSIST MANAGER][assistant.get_reaction] Путь не найден")
                return

            if threading:
                if detail:
                    thread_react_detail(path, trace)
                else:
                    thread_react(path, trace)
            else:
                react(path, trace)

        except Exception as e:
            logger.error(f"[ASSIST MANAGER][assistant.get_reaction] Ошибка: {e}")
            
    def check_keywords_file(self):
        """
        Проверяет наличие файла keywords.json и создает его со стандартными значениями из default_keywords.json если нет
        """
        keywords_path = self.user_keywords
        default_keywords_path = get_path("bin", "default_keywords.json")

        if not os.path.exists(keywords_path):
            logger.info(f"[ASSIST MANAGER] Файл keywords.json не найден, создаю...")
            if os.path.exists(default_keywords_path):
                with open(default_keywords_path, 'r', encoding='utf-8') as f:
                    default_keywords = json.load(f)
            else:
                default_keywords = default_keywords_data
            os.makedirs(os.path.dirname(keywords_path), exist_ok=True)
            with open(keywords_path, 'w', encoding='utf-8') as f:
                json.dump(default_keywords, f, ensure_ascii=False, indent=2)

            return True
        else:
            logger.info(f"[ASSIST MANAGER] Файл keywords.json уже существует")
        
    def apply_keywords_for_values(self):
        try:
            keywords_path = self.user_keywords
            if os.path.exists(keywords_path):
                with open(keywords_path, 'r', encoding='utf-8') as f:
                    keywords_data = json.load(f)
            
            self.keywords_shutdown = keywords_data["keywords_shutdown"]
            self.keywords_restart = keywords_data["keywords_restart"]
            self.keywords_search = keywords_data["keywords_search"]
            self.keywords_no = keywords_data['keywords_no']
            self.keywords_yes = keywords_data['keywords_yes']
            self.keywords_reject = keywords_data['keywords_reject']
            self.screen_list = keywords_data["screen_list"]
            self.fullscreen_list = keywords_data["fullscreen_list"]
            self.action_up = keywords_data['action_up']
            self.action_down = keywords_data['action_down']
            self.all_actions = self.action_up + self.action_down
            self.keywords_player = keywords_data["keywords_player"]
            self.keywords_playpause = keywords_data['keywords_playpause']
            self.keywords_next = keywords_data["keywords_next"]
            self.keywords_prev = keywords_data["keywords_prev"]
            self.censored_list = keywords_data["censored_list"]
            return True, "Списки успешно применены"
        except Exception as e:
            logger.error(f"Ошибка во время применения списков: {e}")
            return False, f"Ошибка во время применения списков: {e}"

    def voice_handler(self):
        """Основной цикл ассистента"""
        greeting()
        default_commands = {
            'микшер': (open_volume_mixer, close_volume_mixer),
            'калькулятор': (open_calc, close_calc),
            'пейнт': (open_paint, close_paint),
            'переменные': (open_path, None),
            'диспетчер': (open_taskmgr, close_taskmgr),
            'корзина': (open_recycle_bin, close_recycle_bin),
            'ап дата': (open_appdata, close_appdata),
            'панель': (self._open_widget_signal, self._close_widget_signal),
            'виджет': (self._open_widget_signal, self._close_widget_signal),
            "микрофон": (self.toggle_mute_discord, self.toggle_mute_discord),
            "микро": (self.toggle_mute_discord, self.toggle_mute_discord),
            "ютуб": (lambda: self.main.start_default_command("ютуб", "open", "url"), None),
            "блютуз": (self.bluetooth.enable, self.bluetooth.disable)
        }
        default_commands_keys = list(default_commands.keys())

        self.last_unrecognized_command = None  # Хранит контекст неудачной команды
        last_activity_time = time.time()  # Время последней активности
        name_mentioned_time = None  # Время последнего упоминания имени ассистента
        name_mentioned = False  # Флаг, что имя было упомянуто
        has_action_words = True
        if not self.initialize_audio():
            return

        try:
            for text in self.get_audio():
                if not self.is_running:
                    break
                self.command_handled = False
                logger.info(f"[last_unrecognized_command]---> {self.last_unrecognized_command}")
                current_time = time.time()
                
                words = text.split()

                all_commands = self.get_command_names()
                all_names = [self.main.assistant_name, self.main.assist_name2, self.main.assist_name3]

                # Список фраз действие-команда, ["action command", ...]
                action_command = self.handle_text_smart(text, self.all_actions, threshold=60)

                # Чистая команда без действия, "command"
                clean_target = self._extract_clean_target(text, self.all_actions)

                if self.find_action(text, self.action_up, self.action_down, self.all_actions)[0] is not None:
                    has_action_words = True
                else:
                    has_action_words = False
                
                # Проверка на наличие команд для управления    
                self.is_keyword_player = any(self.find_closest_command(word, self.keywords_player, threshold=80) for word in words)

                logger.info(f"[ASSIST MANAGER][FIRST_HANDLER][has_action_words] {has_action_words}")

                logger.info(f"[ASSIST MANAGER][FIRST_HANDLER][Raw Text] {text}")
                logger.info(f"[ASSIST MANAGER][FIRST_HANDLER][Action] {action_command}")
                logger.info(f"[ASSIST MANAGER][FIRST_HANDLER][Clean Command] {clean_target}")

                # Сбрасываем контекст, если прошло более 10 секунд без активности
                if self.last_unrecognized_command and (current_time - last_activity_time) > 10:
                    self.last_unrecognized_command = None
                    assist_log.info("Сброс контекста из-за неактивности")
                    logger.info("[ASSIST MANAGER] Сброс контекста из-за неактивности")

                # Обновляем время последней активности при получении текста
                last_activity_time = current_time

                # Сбрасываем флаг упоминания имени, если прошло более n секунд
                if name_mentioned and (current_time - name_mentioned_time) > 20:
                    name_mentioned = False
                    name_mentioned_time = None
                    assist_log.info("Сброс флага упоминания имени")
                    logger.info("[ASSIST MANAGER] Сброс флага упоминания имени")

                # Проверка цензуры
                detected_censor = False
                censored_words = self.find_censored_words(list(words), threshold=80)
                if censored_words:
                    detected_censor = True
                    for word in censored_words:
                        censor_signal.update_count.emit(word)

                if detected_censor:
                    if self.main.is_censored:
                        self.get_reaction(name="censored_folder")
                        detected_censor = False
                

                # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
                # ОБРАБОТКА ПОДТВЕРЖДЕНИЯ КОМАНДЫ ("ДА"/"НЕТ")
                # Если мы ожидаем подтверждение — игнорируем всё, кроме "да" или "нет"
                if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'confirm':
                    if self.last_unrecognized_command.get('is_shutdown'):
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            assist_log.info("Таймаут подтверждения — сброс")
                            logger.info("[ASSIST MANAGER] Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            logger.info("[ASSIST MANAGER] Пользователь подтвердил команду(ы).")

                            turnoff_value = self.last_unrecognized_command.get('is_shutdown')
                            self.set_shutdown(is_shutdown=turnoff_value)

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            logger.info("[ASSIST MANAGER] Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            logger.info("[ASSIST MANAGER] Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue
                    else:
                        text_lower = text.lower().strip()

                        # Проверка таймаута
                        if (current_time - last_activity_time) > 10:
                            assist_log.info("Таймаут подтверждения — сброс")
                            logger.info("Таймаут подтверждения — сброс")
                            self.last_unrecognized_command = None
                            message = "Время ожидания истекло."
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue

                        # Подтверждение — "да"
                        if any(word in text_lower for word in self.keywords_yes):
                            logger.info("[ASSIST MANAGER] Пользователь подтвердил команду(ы).")

                            pending_commands = self.last_unrecognized_command.get('pending_commands')

                            any_executed = False

                            for cmd_info in pending_commands:
                                action_type = cmd_info['action_type']
                                suggested_cmd = cmd_info['suggested_command']

                                logger.info(f"[ASSIST MANAGER] Выполняем: {action_type} {suggested_cmd}")

                                # Пробуем стандартные команды
                                default_list = self.find_closest_command(suggested_cmd, default_commands_keys)
                                if default_list:
                                    if action_type == 'open' and default_commands[default_list][0]:
                                        default_commands[default_list][0]()
                                        any_executed = True
                                    elif action_type == 'close' and default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                                        any_executed = True
                                else:
                                    # Пробуем кастомные команды
                                    type_processed = self.main.commands_manager.get_type_command(suggested_cmd)
                                    if type_processed == "shortcut" or type_processed == "url":
                                        self.main.handle_app_command(suggested_cmd, action_type)
                                    elif type_processed == "folder":
                                        self.main.handle_folder_command(suggested_cmd, action_type)
                                    elif type_processed == "script":
                                        self.main.handle_script_command(suggested_cmd, action_type)

                                    if type_processed != "":
                                        any_executed = True

                            if any_executed:
                                pass
                            else:
                                self.get_reaction(detail=True, name="error_file")
                                message = "Не удалось выполнить команду(ы)."
                                self.show_supply_notice(message, is_confirm=True)
                                logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = None
                            continue

                        # Отмена — "нет"
                        elif any(word in text_lower for word in self.keywords_no):
                            logger.info("[ASSIST MANAGER] Пользователь отменил команду(ы).")
                            self.get_reaction(name="confirm_folder")
                            self.last_unrecognized_command = None
                            message = "Хорошо, отменяю."
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue

                        else:
                            # Не распознан ответ — переспрашиваем
                            logger.info("[ASSIST MANAGER] Не удалось распознать ответ на подтверждение.")
                            self.get_reaction(name="what_folder")
                            message = "Скажите 'да' или 'нет'"
                            self.show_supply_notice(message, is_confirm=True)
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                            continue

                # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                # Условие. Проверка на упоминание имени ассистента

                words = text.split()
                has_name = any(
                    self.find_closest_command(word, all_names, threshold=70) is not None
                    for word in words
                )

                if len(words) <= 4 and has_name:
                    name_mentioned = True
                    name_mentioned_time = current_time

                # Проверка на наличие имени ассистента в тексте или флаг упоминания
                has_assistant_name = (self.main.assistant_name in text or
                                      self.main.assist_name2 in text or
                                      self.main.assist_name3 in text or
                                      name_mentioned)

                # Режим уточнения команды (если предыдущая попытка не удалась)
                if self.main.is_corrected_command:
                    logger.info(f"[ASSIST MANAGER][RETRY][Start Mode Correction]")
                    if self.last_unrecognized_command and self.last_unrecognized_command.get('mode') == 'correction':
                        if text:
                            # Обновляем время последней активности при обработке команды
                            last_activity_time = current_time

                            _, new_action_type = self.find_action(text, self.action_up, self.action_down, self.all_actions)

                            current_action_type = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                            # Если действие изменилось — обновляем контекст
                            if new_action_type and new_action_type != current_action_type:
                                self.last_unrecognized_command['pending_commands'][0]['action_type'] = new_action_type
                                logger.info(f"[ASSIST MANAGER][RETRY] Действие обновлено на: {new_action_type}")

                            # Блок А. Для поиска совпадений и запуска методов в соответствии с действием
                            default_list = self.find_closest_command(clean_target, default_commands_keys)

                            if default_list:
                                action_to_use = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                                if action_to_use == 'open':
                                    default_commands[default_list][0]()
                                elif action_to_use == 'close':
                                    if default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                                self.last_unrecognized_command = None
                                continue
                            # Конец блока А.

                            # Блок В. Для поиска совпадений из кастомного списка команд и их активация
                            file_commands = list(self.main.commands.keys()) if hasattr(self.main, 'commands') and isinstance(
                                self.main.commands, dict) else []
                            custom_list = self.find_closest_command(clean_target, file_commands)

                            if custom_list:
                                action_type = self.last_unrecognized_command['pending_commands'][0].get('action_type')

                                # Восстанавливаем полную команду
                                restored_command = f"{action_type} {custom_list}"
                                logger.info(f"[ASSIST MANAGER][RETRY] Восстановленная команда: {restored_command}")

                                type_processed = self.main.commands_manager.get_type_command(custom_list)
                                logger.info(f"[ASSIST MANAGER][RETRY] Команда: {custom_list}, тип: {type_processed}")
                                if type_processed == "shortcut" or type_processed == "url":
                                    self.main.handle_app_command(custom_list, action_type)
                                elif type_processed == "folder":
                                    self.main.handle_folder_command(custom_list, action_type)
                                elif type_processed == "script":
                                    self.main.handle_script_command(custom_list, action_type)
                                else:
                                    assist_log.warning(f"Команда не обработана: {restored_command}")
                                    logger.warning(f"[ASSIST MANAGER][RETRY] Команда не обработана: {restored_command}")
                                    self.get_reaction(name="what_folder",
                                                    trace="Реакция в блоке, где режим корректировки команды")

                                    self.last_unrecognized_command['pending_commands'][0][
                                        'suggested_command'] = clean_target

                                    logger.info(f"[ASSIST MANAGER][RETRY] Обновлена цель для уточнения: {clean_target}")
                                    self.show_supply_notice(text)
                                    logger.info(f"[ASSIST MANAGER][RETRY] Отправлено уведомление ---> {text}")
                                    self.last_unrecognized_command = None
                                    continue
                            # Конец блока В.

                            if any(word in text for word in self.keywords_reject):
                                logger.info("[ASSIST MANAGER] Пользователь отменил команду(ы).")
                                self.get_reaction(name="confirm_folder")
                                self.last_unrecognized_command = None
                                message = "Хорошо, отменяю."
                                self.show_supply_notice(message, is_confirm=True)
                                logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")
                                continue

                            if not default_list and not custom_list:
                                self.get_reaction(name="what_folder",
                                                trace="Реакция в блоке, где режим корректировки команды")
                                self.show_supply_notice(text)
                                logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {text}")

                if has_assistant_name:
                    logger.info("[ASSIST MANAGER] <<< Условие, где есть Имя ассистента >>>")
                    trigger_react = False
                    _, action_type = self.find_action(text, self.action_up, self.action_down, self.all_actions)
                    if self.find_any_command_in_text(clean_target, self.keywords_search, threshold=80):
                        search_yandex(text, self.main.assistant_name, self.main.assist_name2, self.main.assist_name3)
                        self.get_reaction(name="approve_folder")
                        continue
                    elif self.find_closest_command(clean_target, self.fullscreen_list, threshold=70):
                        self.main.capture_fullscreen()
                        continue
                    elif self.find_closest_command(clean_target, self.screen_list, threshold=70):
                        self.main.capture_area()
                        continue
                    elif self.find_closest_command(clean_target, self.keywords_shutdown):
                        self.get_confirm_shutdown(clean_target, text, action_type)
                        continue
                    elif self.find_closest_command(clean_target, self.keywords_restart, threshold=90):
                        self.get_confirm_shutdown(clean_target, text, action_type, is_shutdown=False)
                        continue

                    if len(words) <= 4 and has_name:
                        if not has_action_words:
                            if not self.is_keyword_player:
                                # Если нет слов-действий и в тексте нет команд для управления плеером — воспроизводим эхо
                                self.get_reaction(name="echo_folder")

                    final_commands = self.handle_text_smart(text, self.all_actions, threshold=60)
                    logger.info(f"[ASSIST MANAGER][HAS_NAME][handle_text_smart] {final_commands}")

                    for command in final_commands:
                        command = command.strip()
                        logger.info(f"[ASSIST MANAGER][Команда в цикле из списка выше] {command}")

                        _, action_type = self.find_action(command, self.action_up, self.action_down, self.all_actions)

                        if action_type:
                            clean_target = self._extract_clean_target(command, self.all_actions)
                            # Ищем совпадение со специальными командами

                            default_list = self.find_closest_command(clean_target, default_commands_keys)
                            logger.info(f"[ASSIST MANAGER][HAS_NAME][list] {default_list}")
                            logger.info(f"[ASSIST MANAGER][HAS_NAME][action_type] {action_type}")
                            logger.info(f"[ASSIST MANAGER][HAS_NAME][clean_target] {clean_target}")

                            if default_list:
                                self.command_handled = True
                                if action_type == 'open':
                                    default_commands[default_list][0]()
                                elif action_type == 'close':
                                    if default_commands[default_list][1]:
                                        default_commands[default_list][1]()
                            else:
                                # Пытаемся обработать команду
                                type_processed = self.main.commands_manager.get_type_command(clean_target)
                                logger.info(f"[ASSIST MANAGER][HAS_NAME] Команда: {clean_target}, тип: {type_processed}")
                                self.command_handled = True
                                if type_processed == "shortcut" or type_processed == "url":
                                    self.main.handle_app_command(clean_target, action_type)
                                elif type_processed == "folder":
                                    self.main.handle_folder_command(clean_target, action_type)
                                elif type_processed == "script":
                                    self.main.handle_script_command(clean_target, action_type)
                                else:
                                    if clean_target:
                                        # Ищем похожие команды
                                        closest_cmd = self.find_closest_command(clean_target, all_commands)
                                        logger.info(f"[ASSIST MANAGER][closest_cmd] {closest_cmd}")

                                        if closest_cmd:
                                            message = f"Вы имели в виду: '{closest_cmd}'?\nСкажите: Да/Нет"
                                            self.show_supply_notice(message, is_confirm=True)
                                            thread_play_sound(type_sound="what")
                                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")

                                            # Сохраняем контекст с предложенной командой + флаг ожидания подтверждения
                                            self.last_unrecognized_command = {
                                                'mode': 'confirm',
                                                'original_text': text,
                                                'pending_commands': [{
                                                    'action_type': action_type,
                                                    'suggested_command': closest_cmd
                                                }]
                                            }
                                        else:
                                            self.last_unrecognized_command = {
                                                'mode': 'correction',
                                                'original_text': text,
                                                'pending_commands': [{
                                                    'action_type': action_type,
                                                    'suggested_command': clean_target
                                                }]
                                            }
                                            trigger_react = True
                                            break
                                        
                                if type_processed != "":
                                    self.command_handled = True

                    if trigger_react:
                        self.command_handled = True
                        self.show_supply_notice(text)
                        self.get_reaction(name="what_folder", trace="Реакт из триггера")
                        logger.info(f"[ASSIST MANAGER] Сработал триггер реакции. Отправлено уведомление ---> {text}")
                        continue

                # Флаг для контроля над обработкой команд без имени ассистента (не относится к плееру)
                if self.main.is_keep_watch:
                    if has_action_words and not has_assistant_name:
                        logger.info("[ASSIST MANAGER] <<< Условие без имени ассистента, только действие и команда >>>")

                        if self.find_closest_command(clean_target, self.screen_list):
                            self.main.capture_area()

                        final_commands = self.handle_text_smart(text, self.all_actions, threshold=60)
                        logger.info(f"[ASSIST MANAGER] [final_commands] {final_commands}")

                        pending_commands = []

                        for command in final_commands:
                            command = command.strip()
                            clean_target = self._extract_clean_target(command, self.all_actions)
                            if not clean_target:
                                continue

                            _, action_type = self.find_action(command, self.action_up, self.action_down, self.all_actions)
                            if not action_type:
                                continue

                            closest_cmd = self.find_closest_command(clean_target, all_commands)
                            if not closest_cmd:
                                continue

                            logger.info(f"[ASSIST MANAGER][command] {command}")
                            logger.info(f"[ASSIST MANAGER][clean_target] {clean_target}")
                            logger.info(f"[ASSIST MANAGER][closest_cmd] {closest_cmd}")

                            pending_commands.append({
                                'action_type': action_type,
                                'suggested_command': closest_cmd,
                                'original_command': command
                            })

                        if pending_commands:
                            # Формируем сообщение
                            action_groups = {'open': [], 'close': []}
                            for cmd in pending_commands:
                                action_groups[cmd['action_type']].append(cmd['suggested_command'])

                            parts = []
                            if action_groups['open']:
                                parts.append(f"Включить: {', '.join(action_groups['open'])}")
                            if action_groups['close']:
                                parts.append(f"Выключить: {', '.join(action_groups['close'])}")

                            message = ";\n".join(parts) + "\n\nСкажите: Да/Нет"
                            self.show_supply_notice(message, is_confirm=True)
                            thread_play_sound(type_sound="what")
                            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")

                            self.last_unrecognized_command = {
                                'mode': 'confirm',
                                'original_text': text,
                                'pending_commands': pending_commands
                            }
                            continue

                # Обработка плеера
                if not self.command_handled and (self.is_keyword_player or has_assistant_name):
                    logger.info("[ASSIST MANAGER] Успешное условие для управления плеером")
                    # Ищем первое подходящее действие (в порядке приоритета: пауза, след, пред)
                    for word in words:
                        if self.find_closest_command(word, self.keywords_playpause, threshold=80):
                            controller.play_pause()
                            self.get_reaction(name="player_folder")
                            continue
                        elif self.find_closest_command(word, self.keywords_next, threshold=80):
                            controller.next_track()
                            self.get_reaction(name="player_folder")
                            continue
                        elif self.find_closest_command(word, self.keywords_prev, threshold=80):
                            controller.previous_track()
                            self.get_reaction(name="player_folder")
                            continue

        except Exception as e:
            assist_log.error(f"Ошибка в основном цикле ассистента: {e}")
            logger.error(f"[ASSIST MANAGER] Ошибка в основном цикле ассистента: {e}")
            logger.error(traceback.format_exc())
            self.main.show_toast(f"[ASSIST MANAGER] Ошибка в основном цикле ассистента: {e}")

    def get_confirm_shutdown(self, closest_cmd, text, action_type, is_shutdown=True):
        try:
            if is_shutdown:
                action_pc = "Выключить"
            else:
                action_pc = "Перезагрузить"
            message = f"{action_pc} ПК?\n\nСкажите: Да/Нет"
            self.show_supply_notice(message, is_confirm=True)
            thread_play_sound(type_sound="what")
            logger.info(f"[ASSIST MANAGER] Отправлено уведомление ---> {message}")

            # Сохраняем контекст
            self.last_unrecognized_command = {
                'mode': 'confirm',
                'original_text': text,
                'is_shutdown': action_pc,
            }
        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка в методе get_confirm_shutdown: {e}")

    def set_shutdown(self, is_shutdown):
        try:
            if is_shutdown == "Выключить":
                shutdown_windows()
                logger.info("[ASSIST MANAGER] Выполняется обработка запроса: shutdown windows")
            elif is_shutdown == "Перезагрузить":
                restart_windows()
                logger.info("[ASSIST MANAGER] Выполняется обработка запроса: restart windows")

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка в методе set_shutdown: {e}")

    def _extract_clean_target(self, text, all_actions):
        """
        Извлекает чистую цель из текста: удаляет имя ассистента, слова-действия (нечётко!), артикли, союзы.
        Возвращает строку с предполагаемой целью.
        """
        if not text:
            return ""

        # Приводим к нижнему регистру
        clean_text = text.lower()

        # Разбиваем на слова
        words = clean_text.split()

        # Удаляем слова, содержащие имя ассистента (даже частично)
        names = [name.lower() for name in [self.main.assistant_name, self.main.assist_name2, self.main.assist_name3] if name]
        filtered_words = [
            word for word in words
            if not any(name in word for name in names)
        ]

        # Собираем обратно
        clean_text = " ".join(filtered_words)

        # Разбиваем снова для обработки действий
        words = clean_text.split()
        filtered_words = []

        # НЕЧЁТКОЕ УДАЛЕНИЕ слов-действий
        for word in words:
            # Ищем ближайшее действие для этого слова
            closest_action = self.find_closest_command(word, all_actions)
            # Если слово похоже на действие — пропускаем (удаляем)
            if not closest_action:
                filtered_words.append(word)

        clean_text = " ".join(filtered_words).strip()

        # Удаляем мусорные слова (союзы, предлоги)
        garbage_words = {"и", "а", "но", "или", "с", "на", "в", "по", "для", "это", "то", "там", "здесь", "же", "бы",
                         "что", "как"}
        words = clean_text.split()
        final_words = [word for word in words if word not in garbage_words]

        return " ".join(final_words).strip()

    def find_action(self, text, action_up, action_down, all_actions, threshold=50):
        """
        Ищет в тексте слово, наиболее похожее на любое из all_actions.
        Возвращает кортеж: (найденное_действие, тип_действия) или (None, None)
        """
        if not text:
            return None, None

        words = text.lower().split()
        best_action = None
        best_score = 0
        best_word = None

        for word in words:
            # Для каждого слова ищем ближайшее действие
            closest_action = self.find_closest_command(word, all_actions)
            if closest_action:
                # Получаем score (можно модифицировать find_closest_command, чтобы возвращал score)
                score = self._get_similarity_score(word, closest_action)
                if score > best_score:
                    best_score = score
                    best_action = closest_action
                    best_word = word

        if best_score >= threshold:
            if best_action in action_up:
                return best_action, 'open'
            elif best_action in action_down:
                return best_action, 'close'

        return None, None

    def _get_similarity_score(self, input_text, command):
        """
        Возвращает процент схожести между input_text и command (0-100)
        """
        if not input_text or not command:
            return 0
        distance = jellyfish.levenshtein_distance(input_text, command)
        max_len = max(len(input_text), len(command))
        if max_len == 0:
            return 100
        score = (1 - distance / max_len) * 100
        return score
    
    def find_any_command_in_text(self, input_text, command_list, threshold=50):
        """
        Ищет любую команду из списка в тексте (проверяет каждое слово текста)
        """
        if not input_text or not command_list:
            return None
        
        # Разбиваем текст на слова
        words = input_text.split()
        
        for word in words:
            # Для каждого слова ищем похожую команду
            best_match = self.find_closest_command(word, command_list, threshold)
            if best_match:
                return best_match
        
        return None

    def find_closest_command(self, input_text, command_list, threshold=50):
        """
        Возвращает наиболее похожую команду из списка, если схожесть >= threshold.
        """
        best_match = None
        best_score = 0

        for command in command_list:
            score = self._get_similarity_score(input_text, command)
            if score > best_score:
                best_score = score
                best_match = command

        # print("[best_match, best_score]", best_match, best_score)

        return best_match if best_score >= threshold else None

    def handle_text_smart(self, text, all_actions, threshold=50):
        """
        Умная обработка текста: берёт слова ПОСЛЕ каждого действия как цели.
        ФИКС: сначала ищет цель ЦЕЛИКОМ, только потом по частям.
        """
        if not text:
            return []

        text_lower = text.lower()
        words = text_lower.split()

        # 1. Находим все действия с позициями
        actions_in_text = []  # [(index, raw_word, normalized_action), ...]
        for i, word in enumerate(words):
            closest_action = self.find_closest_command(word, all_actions, threshold=50)
            if closest_action:
                actions_in_text.append((i, word, closest_action))

        if not actions_in_text:
            return []

        # 2. Для каждого действия — определяем "область целей"
        command_blocks = []  # [(action, start_idx, end_idx), ...]

        for i, (action_index, raw_action, norm_action) in enumerate(actions_in_text):
            start_idx = action_index + 1  # первое слово ПОСЛЕ действия
            if i + 1 < len(actions_in_text):
                end_idx = actions_in_text[i + 1][0]  # до следующего действия
            else:
                end_idx = len(words)  # до конца строки

            if start_idx < end_idx:  # есть хотя бы одно слово после действия
                command_blocks.append((norm_action, start_idx, end_idx))

        # 3. Извлекаем цели из каждой области
        final_commands = []
        all_targets = self.get_command_names()
        
        # Слова, которые всегда разделяют команды (не являются частью названия)
        SEPARATORS = {"и", "или", "а", "но", "затем", "потом", "а также"}
        # Мусорные слова для удаления
        GARBAGE_WORDS = {"с", "на", "в", "по", "для", "это", "то", "там", "здесь", "же", "бы", "что", "как"}

        for action, start, end in command_blocks:
            # Берем подмассив слов в области
            target_words = words[start:end]
            
            if not target_words:
                continue
            
            # 3.1. УДАЛЯЕМ МУСОРНЫЕ СЛОВА из target_words
            clean_target_words = [w for w in target_words if w not in GARBAGE_WORDS]
            if not clean_target_words:
                continue
                
            # 3.2. РАЗБИВАЕМ НА ПОДКОМАНДЫ по разделителям
            sub_commands = []  # список подкоманд (каждая = список слов)
            current_sub = []
            
            for word in clean_target_words:
                if word in SEPARATORS:
                    # Встретили разделитель → завершаем текущую подкоманду
                    if current_sub:
                        sub_commands.append(current_sub)
                        current_sub = []
                else:
                    # Обычное слово → добавляем в текущую подкоманду
                    current_sub.append(word)
            
            # Добавляем последнюю подкоманду, если есть
            if current_sub:
                sub_commands.append(current_sub)
            
            # Если разделителей не было → одна подкоманда со всеми словами
            if not sub_commands:
                sub_commands = [clean_target_words]
            
            # 3.3. ОБРАБАТЫВАЕМ КАЖДУЮ ПОДКОМАНДУ
            for sub_words in sub_commands:
                if not sub_words:
                    continue
                    
                # Вариант А: Пробуем найти цель ЦЕЛИКОМ
                full_target = " ".join(sub_words)
                closest_target = self.find_closest_command(full_target, all_targets, threshold=threshold)
                
                if closest_target:
                    # Нашли целиком → добавляем одну команду
                    cmd = f"{action} {closest_target}"
                    if cmd not in final_commands:  # избегаем дубликатов
                        final_commands.append(cmd)
                    continue
                
                # Вариант Б: Не нашли целиком → ищем по частям
                # Но только если подкоманда из 2+ слов
                if len(sub_words) >= 2:
                    # Пробуем все возможные n-граммы (от самых длинных к коротким)
                    found_any = False
                    for n in range(len(sub_words), 0, -1):
                        # Проверяем все n-граммы такой длины
                        for i in range(len(sub_words) - n + 1):
                            ngram = " ".join(sub_words[i:i+n])
                            closest = self.find_closest_command(ngram, all_targets, threshold=threshold)
                            if closest:
                                cmd = f"{action} {closest}"
                                if cmd not in final_commands:
                                    final_commands.append(cmd)
                                found_any = True
                                # Пропускаем слова, которые вошли в найденную n-грамму
                                    # (можно реализовать, но сложнее)
                    
                    if found_any:
                        continue
                
                # Вариант В: Не нашли даже частей → добавляем как есть (только не мусор)
                # Но проверяем, что это не разделитель
                if full_target not in SEPARATORS and full_target not in GARBAGE_WORDS:
                    cmd = f"{action} {full_target}"
                    if cmd not in final_commands:
                        final_commands.append(cmd)

        # 4. Убираем дубликаты команд
        seen_commands = set()
        unique_commands = []
        for cmd in final_commands:
            if cmd not in seen_commands:
                seen_commands.add(cmd)
                unique_commands.append(cmd)

        return unique_commands

    def get_command_names(self):
        """Возвращает объединённый список всех имён команд"""

        standard_commands = getattr(self, 'standard_commands', [
            "калькулятор",
            "диспетчер",
            "пейнт",
            "пэйнт",
            "панель",
            "корзина",
            "микшер",
            "переменные",
            "ап дата",
            "микрофон",
            "микро",
            "ютуб"
        ])

        file_commands = list(self.main.commands.keys()) if hasattr(self.main, 'commands') and isinstance(self.main.commands,
                                                                                               dict) else []

        standard_commands = [cmd.lower() for cmd in standard_commands]
        file_commands = [cmd.lower() for cmd in file_commands]

        # Убираем дубликаты с сохранением порядка
        seen = set()
        combined = []
        for cmd in standard_commands + file_commands:
            if cmd not in seen:
                seen.add(cmd)
                combined.append(cmd)

        return combined
    
    def find_censored_words(self, words, threshold=80):
        """
        Находит ВСЕ матерные слова в списке слов
        """
        if not words or not self.censored_list:
            return []
        
        phrase = " ".join(words).lower()
        found_words = []

        for censored in self.censored_list:
            censored_lower = censored.lower()
 
            if " " in censored_lower:
                if censored_lower in phrase:
                    import re
                    pattern = r'(?<![а-яё])' + re.escape(censored_lower) + r'(?![а-яё])'
                    if re.search(pattern, phrase):
                        found_words.append(censored)
                continue

            for word in words:
                word_lower = word.lower()

                if word_lower == censored_lower:
                    if censored not in found_words:
                        found_words.append(censored)
                    break

                elif censored_lower in word_lower:
                    import re
                    pattern = r'(?<![а-яё])' + re.escape(censored_lower) + r'(?![а-яё])'
                    if re.search(pattern, word_lower):
                        if censored not in found_words:
                            found_words.append(censored)
                        break
  
                else:
                    score = self._get_similarity_score(word_lower, censored_lower)
                    if score >= threshold:
                        if censored not in found_words:
                            found_words.append(censored)
                        break

        unique_words = list(dict.fromkeys(found_words))

        filtered_words = []
        for word in unique_words:
            is_substring = False
            for other in unique_words:
                if word != other and word.lower() in other.lower():
                    is_substring = True
                    break
            if not is_substring:
                filtered_words.append(word)
        
        if filtered_words:
            logger.debug(f"[CENSOR] Найдены матерные слова: {filtered_words}")
        
        return filtered_words

    def restart_bot(self):
        self.stopped(reaction=False)
        QTimer.singleShot(3000, lambda: self.run_assist())

    def initialize_audio(self):
        """Инициализация моделей и аудиопотока через sounddevice."""
        self.cleanup_audio_resources()
        assist_log.info("Загрузка моделей для распознавания...")
        logger.debug("[ASSIST MANAGER] Загрузка моделей для распознавания...")

        model_path_ru = self.vosk_model_ru
        logger.debug(f"[ASSIST MANAGER] Загружена модель RU - {model_path_ru}")

        try:
            self.model_ru = Model(model_path_ru)
            assist_log.info("Модели успешно загружены.")
            logger.info("[ASSIST MANAGER] Модели успешно загружены.")
        except Exception as e:
            assist_log.error(f"Ошибка при загрузке модели: {e}. Возможно путь содержит кириллицу.")
            logger.error(f"[ASSIST MANAGER] Ошибка при загрузке модели: {e}", exc_info=True)
            return False

        try:
            self.rec_ru = KaldiRecognizer(self.model_ru, 16000)

            target_id = self.get_microphone_id(self.main.input_device_name)
            if target_id is None:
                assist_log.warning("Не удалось определить микрофон. Используем устройство по умолчанию.")
                target_id = sd.default.device[0] if sd.default.device[0] < len(sd.query_devices()) else None

            if target_id is None:
                raise RuntimeError("Нет доступных входных устройств")

            try:
                self.audio_stream = sd.InputStream(
                    samplerate=16000,
                    channels=1,
                    dtype='int16',
                    blocksize=512,
                    device=target_id,
                    callback=self.audio_callback
                )
                self.audio_stream.start()
                self.main.input_device_id = target_id
                device_name = sd.query_devices(target_id)['name']
                self.main.input_device_name = device_name
                logger.info(f"[ASSIST MANAGER] Аудиопоток запущен: '{device_name}' (ID={target_id})")
            except Exception as e:
                logger.error(f"[ASSIST MANAGER] Не удалось открыть выбранное устройство (ID={target_id}): {e}")
                try:
                    self.audio_stream = sd.InputStream(
                        samplerate=16000,
                        channels=1,
                        dtype='int16',
                        blocksize=512,
                        callback=self.audio_callback
                    )
                    self.audio_stream.start()
                    fallback_id = sd.default.device[0]
                    fallback_name = sd.query_devices(fallback_id)['name']
                    self.main.input_device_id = fallback_id
                    self.main.input_device_name = fallback_name
                    logger.warning(f"[ASSIST MANAGER] Используется устройство по умолчанию: '{fallback_name}'")
                except Exception as e2:
                    logger.error("[ASSIST MANAGER] Не удалось запустить ни одно устройство.", exc_info=True)
                    raise e2

            self.microphone_available = True
            self.last_audio_time = time.time()
            return True

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Критическая ошибка при инициализации аудио: {e}", exc_info=True)
            return False

    def get_microphone_id(self, preferred_name=None):
        """Возвращает ID микрофона по имени"""
        try:
            devices = sd.query_devices()
            default_in = sd.default.device[0]
            candidates = []
            seen = set()

            for dev in devices:
                idx, name, ch = dev['index'], dev.get('name', ''), dev.get('max_input_channels', 0)
                if ch <= 0 or not name:
                    continue

                # Фильтр: системные, дубли, нежелательные
                clean = name.split('(')[0].strip()
                lower_name = name.lower()
                if (clean in seen or
                        any(kw in lower_name for kw in ['mapper', 'primary', 'wave', 'default', 'communications'])):
                    continue
                seen.add(clean)

                # Приоритет API: WASAPI > ASIO > остальные
                api_name = sd.query_hostapis(dev['hostapi'])['name'].lower()
                priority = {'wasapi': 3, 'asio': 2}.get(api_name, 1)

                try:
                    with sd.InputStream(device=idx, channels=1, samplerate=16000, blocksize=512):
                        candidates.append((idx, priority, preferred_name and preferred_name.lower() in lower_name))
                except Exception:
                    continue

            if candidates:
                best = max(candidates, key=lambda x: (x[2], x[1], -x[0]))
                return best[0]

            return default_in

        except Exception as e:
            logger.warning(f"[ASSIST MANAGER] Ошибка выбора микрофона: {e}")
            return sd.default.device[0]

    def audio_callback(self, indata, frames, time_info, status):
        """
        :param time_info: Временные метки от PortAudio
        """
        if status:
            logger.warning(f"Статус аудио: {status}")
            if any(keyword in str(status).lower() for keyword in ['overrun', 'underrun']):
                pass
            else:
                return

        if len(indata) == 0:
            return

        # === АНАЛИЗ ГРОМКОСТИ ===
        try:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            is_silent = rms < 20

            if not is_silent:
                self.last_audio_time = time.time()

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка при анализе громкости: {e}")

        data = indata.tobytes()
        ru_text = ""
        en_text = ""

        try:
            if self.rec_ru.AcceptWaveform(data):
                result = json.loads(self.rec_ru.Result())
                ru_text = result.get("text", "").strip().lower()

            final_text = ru_text or en_text
            if final_text:
                self.on_final_result(final_text)

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка в обработке распознавания: {e}")

    def on_final_result(self, text):
        """Вызывается при распознавании фразы. Логирует и отправляет дальше."""
        assist_log.info(f"[Распознано] {text}")
        logger.info(f"[ASSIST MANAGER] [Распознано] {text}")

        if hasattr(self, '_current_queue') and self._current_queue is not None:
            try:
                self._current_queue.put(text)
            except Exception as e:
                assist_log.error(f"Не удалось положить текст в очередь: {e}")

    def get_audio(self):
        """
        Возвращает генератор текста. Работает через callback + очередь.
        """
        from queue import Queue
        q = Queue()

        self.text_queue = q
        self._current_queue = q

        try:
            while self.is_running:
                try:
                    text = q.get(timeout=1)
                    yield text
                except:
                    continue
        except Exception as e:
            assist_log.error(f"Ошибка в get_audio: {e}")
        finally:
            if hasattr(self, '_current_queue'):
                del self._current_queue

    # === ПРОВЕРКА МИКРОФОНА ===
    def check_microphone(self):
        """Проверка доступности микрофона через sounddevice"""
        logger.info("[ASSIST MANAGER] Проверка микрофона через sounddevice...")
        try:
            devices = sd.query_devices()
            active_mics = []

            for device in devices:
                if device['max_input_channels'] <= 0:
                    continue

                device_id = device['index']
                name = device['name']

                # Фильтруем системные
                if any(kw in name.lower() for kw in ['mapper', 'primary', 'wave', 'default']):
                    continue

                try:
                    with sd.InputStream(
                            device=device_id,
                            channels=1,
                            samplerate=44100,
                            blocksize=1024
                    ):
                        active_mics.append(device)
                except Exception:
                    continue

            if active_mics:
                logger.info(f"[ASSIST MANAGER] Найдено рабочих микрофонов: {len(active_mics)}")
                self.microphone_available = True
                return True
            else:
                assist_log.info("[ASSIST MANAGER] Нет доступных микрофонов.")
                self.microphone_available = False
                return False

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка проверки микрофона: {e}")
            self.microphone_available = False
            return False

    def _check_microphone_wrapper(self):
        try:
            self.check_microphone()
            if self.microphone_available:
                if not self.is_running:
                    self.main.show_toast(message="Микрофон обнаружен!")
                    self.run_assist()
                else:
                    self.main.show_toast(message="Микрофон подключен!")
            else:
                self.main.show_toast(message="Микрофон не найден!")
        except Exception as e:
            assist_log.error(f"Ошибка в _check_microphone_wrapper: {e}")

    def cleanup_audio_resources(self):
        """Безопасное освобождение аудиоресурсов"""
        try:
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    if self.audio_stream.active:
                        self.audio_stream.stop()
                    self.audio_stream.close()
                    logger.info("[ASSIST MANAGER] Аудиопоток закрыт.")
                except Exception as e:
                    logger.error(f"[ASSIST MANAGER] Ошибка при закрытии аудиопотока: {e}")
                finally:
                    self.audio_stream = None
        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Критическая ошибка аудиопотока: {e}", exc_info=True)
        
        try:
            if hasattr(self, 'rec_ru') and self.rec_ru is not None:
                self.rec_ru = None
            if hasattr(self, 'model_ru') and self.model_ru is not None:
                self.model_ru = None
        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Ошибка при очистке моделей: {e}")

        import gc
        gc.collect()

    def check_silence_timeout(self):
        """Проверяет, сколько времени прошло с последнего звука"""
        if not self.is_running or not self.microphone_available:
            return

        if self.last_audio_time is None:
            return  # Ещё не было данных

        silent_duration = time.time() - self.last_audio_time

        if silent_duration > 10.0:  # 10 секунд тишины
            logger.warning(f"[ASSIST MANAGER] Нет звука более 10 сек ({silent_duration:.1f}s) — перезапуск аудиопотока")
            self.restart_audio_stream()

    def restart_audio_stream(self):
        """Перезапускает только InputStream, не трогая модели и ассистента"""
        logger.info("[ASSIST MANAGER] Перезапуск аудиопотока...")

        try:
            # Останавливаем старый поток
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                if self.audio_stream.active:
                    self.audio_stream.abort()
                self.audio_stream = None
                logger.info("[ASSIST MANAGER] Старый аудиопоток остановлен")

            # Создаём новый — без указания устройства → по умолчанию
            self.audio_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                blocksize=512,
                callback=self.audio_callback
            )
            self.audio_stream.start()

            # Обновляем время активности
            self.last_audio_time = time.time()

            logger.info("[ASSIST MANAGER] Аудиопоток успешно перезапущен (по умолчанию)")

        except Exception as e:
            logger.error(f"[ASSIST MANAGER] Не удалось перезапустить поток: {e}")
            # Можно попробовать повторно через 10 сек
            QTimer.singleShot(10000, self.restart_audio_stream)

    def _open_widget_signal(self):
        try:
            gui_signals.open_widget_signal.emit()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске сигнала виджета: {e}")

    def _close_widget_signal(self):
        try:
            gui_signals.close_widget_signal.emit()
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске сигнала виджета (на закрытие): {e}")

    def toggle_mute_discord(self):
        toggle = ToggleMuteDiscord()
        toggle.main()
