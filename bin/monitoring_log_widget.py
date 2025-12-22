from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextEdit
import os
from logging_config import logger, debug_logger


class MonitorLogWidget(QTextEdit):
    """Виджет для мониторинга логов с двумя режимами."""
    
    def __init__(self, log_file_path, parent=None, max_lines=100, keep_lines=10):
        super().__init__(parent)
        self.log_file_path = log_file_path
        self.last_file_size = 0
        self.last_read_position = 0
        self.max_lines = max_lines
        self.keep_lines = keep_lines

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_log)
        self.active_interval = 500
        self.background_interval = 30000  # 30 секунд в фоне
        self.is_active_mode = False

        self._update_file_size()
    
    def _update_file_size(self):
        """Обновить информацию о размере файла."""
        if os.path.exists(self.log_file_path):
            try:
                self.last_file_size = os.path.getsize(self.log_file_path)
            except:
                self.last_file_size = 0

    def text_append(self, text):
        self.append(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
    
    def _check_log(self):
        """Проверка лог-файла."""
        try:
            if not os.path.exists(self.log_file_path):
                return
            
            current_size = os.path.getsize(self.log_file_path)
            
            if current_size != self.last_file_size:
                self.last_file_size = current_size
                
                if self.is_active_mode:
                    self._read_and_display_new_data()
        
        except Exception as e:
            logger.error(f"Ошибка проверки лог-файла: {e}")
    
    def _read_and_display_new_data(self):
        """Чтение и отображение новых данных."""
        try:
            self._check_and_trim_log_file()

            with open(self.log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                if self.last_read_position > self.last_file_size:
                    self.last_read_position = 0
                
                f.seek(self.last_read_position)
                
                new_lines = f.readlines()
                if new_lines:
                    self.append(''.join(new_lines))
                    
                    self.verticalScrollBar().setValue(
                        self.verticalScrollBar().maximum()
                    )
                    
                    self.last_read_position = f.tell()
        
        except Exception as e:
            logger.error(f"Ошибка чтения лог-файла: {e}")

    def _check_and_trim_log_file(self):
        """Проверка и полная очистка лог-файла при превышении лимита."""
        try:
            if not os.path.exists(self.log_file_path):
                return

            with open(self.log_file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                lines = f.readlines()
            
            if len(lines) > self.max_lines:
                self.clear_logs()
                logger.info("Автоочистка логов...")
        
        except Exception as e:
            logger.error(f"Ошибка очистки лог-файла: {e}")

    def clear_logs(self):
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            if self.is_active_mode:
                self.clear()

            self.last_read_position = 0
            self.last_file_size = 0
        except Exception as e:
            logger.error(f"Ошибка при очистке логов: {e}")
    
    def start_active_mode(self):
        """Запустить активный режим (окно видно)."""
        self.is_active_mode = True
        self.check_timer.start(self.active_interval)
        debug_logger.info("Активный режим мониторинга логов запущен")
    
    def start_background_mode(self):
        """Запустить фоновый режим (окно скрыто)."""
        self.is_active_mode = False
        self.check_timer.start(self.background_interval)
        debug_logger.info("Фоновый режим мониторинга логов запущен")
    
    def stop_monitoring(self):
        """Остановить мониторинг."""
        self.check_timer.stop()
        debug_logger.info("Мониторинг логов остановлен")