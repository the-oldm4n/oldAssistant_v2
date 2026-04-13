from collections import deque
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextEdit
import os
from log_config import logger


class MonitorLogWidget(QTextEdit):
    """Виджет для мониторинга логов с двумя режимами."""
    
    def __init__(self, log_file_path=None, parent=None, visible_lines=500, max_lines=300, keep_lines=50, clear_logs=True):
        super().__init__(parent)
        self.log_file_path = log_file_path
        self.last_file_size = 0
        self.last_read_position = 0
        self.max_lines = max_lines
        self.keep_lines = keep_lines
        self.is_clear_logs = clear_logs
        self.visible_lines = visible_lines

        self._display_buffer = deque(maxlen=self.visible_lines)

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_log)
        self.active_interval = 500
        self.background_interval = 30000  # 30 секунд в фоне
        self.is_active_mode = False

        self._update_file_size()
        self._load_last_lines()

    def _update_file_size(self):
        """Обновить информацию о размере файла."""
        if os.path.exists(self.log_file_path):
            try:
                self.last_file_size = os.path.getsize(self.log_file_path)
            except:
                self.last_file_size = 0
    
    def _load_last_lines(self):
        """Загружает последние visible_lines строк из файла при запуске."""
        if not os.path.exists(self.log_file_path):
            return
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                # Эффективно читаем последние visible_lines строк
                lines = []
                buffer_size = 8192
                file_size = os.path.getsize(self.log_file_path)
                
                if file_size <= buffer_size * 10:
                    # Небольшой файл — читаем целиком
                    all_lines = f.readlines()
                    lines = all_lines[-self.visible_lines:]
                else:
                    # Большой файл — читаем с конца
                    blocks = []
                    remaining = file_size
                    
                    while remaining > 0 and len(lines) < self.visible_lines:
                        read_size = min(buffer_size, remaining)
                        f.seek(remaining - read_size)
                        block = f.read(read_size)
                        blocks.append(block)
                        remaining -= read_size
                    
                    all_text = ''.join(reversed(blocks))
                    lines = all_text.splitlines()[-self.visible_lines:]
                
                # Заполняем буфер
                self._display_buffer.clear()
                for line in lines:
                    self._display_buffer.append(line.rstrip('\n\r'))
                
                self._update_display()
                
                # Устанавливаем позицию чтения в конец файла
                self.last_read_position = file_size
                self.last_file_size = file_size
                
        except Exception as e:
            logger.error(f"Ошибка загрузки последних строк: {e}")
    
    def _update_display(self):
        """Обновляет отображение на основе буфера."""
        self.clear()
        self.append('\n'.join(self._display_buffer))
        
        # Прокручиваем вниз
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
            with open(self.log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                if self.last_read_position > self.last_file_size:
                    self.last_read_position = 0
                
                f.seek(self.last_read_position)
                new_lines = f.readlines()
                
                if new_lines:
                    # Добавляем новые строки в буфер
                    for line in new_lines:
                        self._display_buffer.append(line.rstrip('\n\r'))
                    
                    # Обновляем отображение
                    self._update_display()
                    
                    # Обновляем позицию чтения
                    self.last_read_position = f.tell()
        
        except Exception as e:
            logger.error(f"Ошибка чтения лог-файла: {e}")
    
    def clear_display(self):
        """Очищает только отображение (не трогает файл)."""
        self._display_buffer.clear()
        self.clear()

    def _check_and_trim_log_file(self):
        """Проверка и полная очистка лог-файла при превышении лимита."""
        try:
            if self.is_clear_logs:
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
            # Очищаем файл
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            
            # Очищаем память
            self._display_buffer.clear()
            self.clear()
            
            # Сбрасываем позиции
            self.last_read_position = 0
            self.last_file_size = 0
            
            logger.info("Лог-файл очищен")
        except Exception as e:
            logger.error(f"Ошибка при очистке логов: {e}")
    
    def start_active_mode(self):
        """Запустить активный режим (окно видно)."""
        self.is_active_mode = True
        self.check_timer.start(self.active_interval)
        logger.info("Активный режим мониторинга логов запущен")
    
    def start_background_mode(self):
        """Запустить фоновый режим (окно скрыто)."""
        self.is_active_mode = False
        self.check_timer.start(self.background_interval)
        logger.info("Фоновый режим мониторинга логов запущен")
    
    def stop_monitoring(self):
        """Остановить мониторинг."""
        self.check_timer.stop()
        logger.info("Мониторинг логов остановлен")