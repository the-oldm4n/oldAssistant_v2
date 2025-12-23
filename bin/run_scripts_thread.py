from PySide6.QtCore import QThread, Signal
import time
from logging_config import debug_logger


class ScriptExecutionThread(QThread):
    """Поток для выполнения скриптов"""
    
    # Сигналы для обновления UI
    step_started = Signal(int, int)
    step_completed = Signal(int, int, bool)
    script_finished = Signal(bool)
    script_error = Signal(str)
    execute_command = Signal(str, str, str, str, str)
    
    def __init__(self, commands_manager, script_key, action="open"):
        super().__init__()
        self.commands_manager = commands_manager
        self.script_key = script_key
        self.action = action
        self._stop_requested = False
        self._pause_requested = False
        
        # Подключаем сигнал execute_command к менеджеру
        self.execute_command.connect(self.commands_manager._handle_script_command)
        
    def run(self):
        """Основной метод потока"""
        try:
            debug_logger.info(f"[SCRIPT THREAD] Начало выполнения скрипта: {self.script_key}")
            
            if self.script_key not in self.commands_manager.commands:
                self.script_error.emit(f"Скрипт '{self.script_key}' не найден")
                return
                
            script_data = self.commands_manager.commands[self.script_key]
            
            if not isinstance(script_data, dict) or script_data.get('type') != 'script':
                self.script_error.emit(f"'{self.script_key}' не является скриптом")
                return
                
            actions = script_data.get('actions', [])
            total_steps = len(actions)
            
            debug_logger.info(f"[SCRIPT THREAD] Загружено {total_steps} шагов")
            
            for step_idx, action_item in enumerate(actions, 1):
                # Проверяем запрос на остановку
                if self._stop_requested:
                    debug_logger.info(f"[SCRIPT THREAD] Остановка запрошена на шаге {step_idx}")
                    break
                    
                # Обрабатываем паузу
                while self._pause_requested and not self._stop_requested:
                    time.sleep(0.1)
                    
                # Сигнализируем о начале шага
                self.step_started.emit(step_idx, total_steps)
                debug_logger.info(f"[SCRIPT THREAD] Шаг {step_idx}/{total_steps}: {action_item}")
                
                # Задержка перед выполнением шага
                delay = action_item.get('delay', 0)
                if delay > 0:
                    debug_logger.info(f"[SCRIPT THREAD] Задержка {delay} секунд")
                    
                    # Разбиваем задержку для возможности прерывания
                    elapsed = 0
                    while elapsed < delay and not self._stop_requested and not self._pause_requested:
                        time.sleep(0.1)  # Спим по 100 мс
                        elapsed += 0.1
                        
                    if self._stop_requested:
                        break
                        
                    # Если была пауза, ждем пока снимут
                    while self._pause_requested and not self._stop_requested:
                        time.sleep(0.1)
                
                if self._stop_requested:
                    break
                
                # Выполняем шаг
                success = self._execute_action_step(action_item, step_idx)
                self.step_completed.emit(step_idx, total_steps, success)
                
                if not success:
                    debug_logger.error(f"[SCRIPT THREAD] Шаг {step_idx} завершился с ошибкой")
            
            # Сигнализируем о завершении
            completed = not self._stop_requested
            debug_logger.info(f"[SCRIPT THREAD] Сценарий завершен. Успешно: {completed}")
            self.script_finished.emit(completed)
            
        except Exception as e:
            error_msg = f"Ошибка выполнения скрипта: {str(e)}"
            debug_logger.error(f"[SCRIPT THREAD] {error_msg}")
            self.script_error.emit(error_msg)
            self.script_finished.emit(False)
    
    def _execute_action_step(self, action_item, step_idx):
        """Выполнить один шаг действия"""
        try:
            command_key = action_item.get('command_key')
            args = action_item.get('args', '')
            
            if not command_key:
                debug_logger.info(f"[SCRIPT THREAD] Шаг {step_idx}: нет ключа команды")
                return False
            
            all_commands = {**self.commands_manager.default_commands, **self.commands_manager.commands}
                
            if command_key not in all_commands:
                debug_logger.info(f"[SCRIPT THREAD] Шаг {step_idx}: команда '{command_key}' не найдена")
                return False
                
            command_data = all_commands[command_key]
            
            # Получаем значение для выполнения
            if isinstance(command_data, dict):
                value = command_data.get('name', '')
                cmd_type = command_data.get('type', '')
                move = action_item.get('move', 'open')
            else:
                value = command_data
                cmd_type = self.commands_manager._detect_type(value)

            debug_logger.info(f"[SCRIPT THREAD] Выполняю: {cmd_type} -> {value}")
            
            # ВЫПОЛНЯЕМ КОМАНДУ ЧЕРЕЗ СИГНАЛ (в основном потоке)
            self.execute_command.emit(cmd_type, value, self.action, move, args)
            
            return True
            
        except Exception as e:
            debug_logger.error(f"[SCRIPT THREAD] Ошибка выполнения шага {step_idx}: {e}")
            return False
    
    def stop(self):
        """Остановить выполнение"""
        self._stop_requested = True
        
    def pause(self):
        """Поставить на паузу"""
        self._pause_requested = True
        
    def resume(self):
        """Продолжить выполнение"""
        self._pause_requested = False