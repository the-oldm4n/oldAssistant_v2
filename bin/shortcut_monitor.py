from PySide6.QtCore import QObject, Signal, QFileSystemWatcher, QTimer
import os
from log_config import logger

class ShortcutMonitor(QObject):
    folder_changed = Signal()  # Общий сигнал об изменении в папке
    monitoring_changed = Signal(bool)
    
    def __init__(self, watch_folder):
        super().__init__()
        self.watch_folder = watch_folder
        self.current_files = set()
        self.is_monitoring = False
        
        self.watcher = QFileSystemWatcher()
        self.watcher.directoryChanged.connect(self._on_folder_changed)
        
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._check_files_changes)
    
    def start_monitoring(self):
        if not self.is_monitoring:
            self.current_files = self._get_current_files()
            self.watcher.addPath(self.watch_folder)
            self.is_monitoring = True
            self.monitoring_changed.emit(True)
            logger.info(f"[SHORTCUT-MONITOR] Мониторинг включен: {self.watch_folder}")
    
    def stop_monitoring(self):
        if self.is_monitoring:
            self.watcher.removePath(self.watch_folder)
            self.debounce_timer.stop()
            self.is_monitoring = False
            self.monitoring_changed.emit(False)
            logger.info(f"[SHORTCUT-MONITOR] Мониторинг выключен: {self.watch_folder}")
    
    def _get_current_files(self):
        try:
            all_items = os.listdir(self.watch_folder)
            files_only = [f for f in all_items 
                         if os.path.isfile(os.path.join(self.watch_folder, f))]
            return set(files_only)
        except Exception as e:
            logger.error(f"[SHORTCUT-MONITOR] Ошибка чтения папки: {e}")
            return set()
    
    def _on_folder_changed(self, path):
        if self.is_monitoring:
            self.debounce_timer.start(300)
    
    def _check_files_changes(self):
        if not self.is_monitoring:
            return
            
        try:
            new_files = self._get_current_files()
            
            added_files = new_files - self.current_files
            for filename in added_files:
                filepath = os.path.join(self.watch_folder, filename)
                self.folder_changed.emit()
                logger.info(f"[SHORTCUT-MONITOR] Добавлен файл: {filepath}")
            
            removed_files = self.current_files - new_files
            for filename in removed_files:
                filepath = os.path.join(self.watch_folder, filename)
                self.folder_changed.emit()
                logger.info(f"[SHORTCUT-MONITOR] Удален файл: {filepath}")
            
            if added_files or removed_files:
                self.current_files = new_files
                
        except Exception as e:
            logger.error(f"[SHORTCUT-MONITOR] Ошибка проверки файлов: {e}")
    
    def get_current_files(self):
        return [os.path.join(self.watch_folder, f) for f in self.current_files]