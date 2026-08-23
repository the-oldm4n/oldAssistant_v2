from mygui import ModernProgressBar, ProgressType
import psutil
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Signal, QTimer, Qt, QObject
import os
from log_config import logger


class AppRAMMonitor(QObject):
    ram_usage_changed = Signal(float, float)
    
    def __init__(self, limit_mb=1024, parent=None):
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ram_usage)
        
        self.pid = os.getpid()
        self.process = psutil.Process(self.pid)
        self.limit_mb = limit_mb
        
        self.current_usage_mb = 0
        self.current_usage_percent = 0
        
    def start_monitoring(self, interval_ms=1000):
        self.timer.start(interval_ms)
        
    def stop_monitoring(self):
        self.timer.stop()
        
    def update_ram_usage(self):
        try:
            self.current_usage_mb = self.process.memory_info().rss / (1024 ** 2)
            self.current_usage_percent = (self.current_usage_mb / self.limit_mb) * 100
            self.ram_usage_changed.emit(self.current_usage_percent, self.current_usage_mb)
        except Exception as e:
            print(f"Ошибка получения RAM: {e}")
    
    def get_usage_mb(self):
        return self.current_usage_mb
    
    def get_usage_percent(self):
        return self.current_usage_percent
    
    def get_limit_mb(self):
        return self.limit_mb
    

class SystemRAMMonitor(QObject):
    system_ram_changed = Signal(float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_system_ram)
        
    def start_monitoring(self, interval_ms=1000):
        self.timer.start(interval_ms)
        
    def update_system_ram(self):
        memory = psutil.virtual_memory()
        percent = memory.percent
        used_gb = memory.used / (1024 ** 3)
        self.system_ram_changed.emit(percent, used_gb)


class DualRAMProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatsWidget")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        app_label = QLabel("Потребление приложения")
        app_label.setStyleSheet("background: transparent")
        app_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(app_label)
        
        self.app_ram_bar = ModernProgressBar(progress_type=ProgressType.CIRCLE)
        self.app_ram_bar.set_circle_dimensions(diameter=120, line_width=12)
        self.app_ram_bar.set_progress_color("#00FF00")
        self.app_ram_bar.setTextFormat("{value:.1f}%")
        
        self.app_label_mb = QLabel("0 MB / 1024 MB")
        self.app_label_mb.setStyleSheet("background: transparent")
        self.app_label_mb.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.app_label_mb)
        layout.addWidget(self.app_ram_bar, alignment=Qt.AlignCenter)
        
        system_label = QLabel("Общая загрузка RAM")
        system_label.setStyleSheet("background: transparent")
        system_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(system_label)
        
        self.system_ram_bar = ModernProgressBar(progress_type=ProgressType.CIRCLE)
        self.system_ram_bar.set_circle_dimensions(diameter=120, line_width=12)
        self.system_ram_bar.set_progress_color("#00B0FF")
        self.system_ram_bar.setTextFormat("{value:.1f}%")
        
        self.system_label_gb = QLabel("0 GB / 0 GB")
        self.system_label_gb.setStyleSheet("background: transparent")
        self.system_label_gb.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.system_label_gb)
        layout.addWidget(self.system_ram_bar, alignment=Qt.AlignCenter)
        
        layout.addStretch()
        
        # --- Мониторы ---
        self.app_monitor = AppRAMMonitor(limit_mb=1024)
        self.app_monitor.ram_usage_changed.connect(self.update_app_ram)
        self.app_monitor.start_monitoring(1000)
        
        self.system_monitor = SystemRAMMonitor()
        self.system_monitor.system_ram_changed.connect(self.update_system_ram)
        self.system_monitor.start_monitoring(1000)
        
    def update_app_ram(self, percent, mb_used):
        display_percent = min(percent, 100)
        
        self.app_ram_bar.animate_to(display_percent, 500)
        self.app_label_mb.setText(f"{mb_used:.1f} MB / {self.app_monitor.get_limit_mb()} MB")
        
        if display_percent < 50:
            self.app_ram_bar.set_progress_color("#00FF00")
        elif display_percent < 80:
            self.app_ram_bar.set_progress_color("#FFA500")
        else:
            self.app_ram_bar.set_progress_color("#FF0000")
            logger.warning("[MAIN] Превышен лимит памяти")
            self.show_toast(f"Прозошла утечка памяти. Превышен лимит (1024Мб).")
    
    def update_system_ram(self, percent, used_gb):
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        
        self.system_ram_bar.animate_to(percent, 500)
        self.system_label_gb.setText(f"{used_gb:.1f} GB / {total_gb:.1f} GB")
        
        if percent < 50:
            self.system_ram_bar.set_progress_color("#00B0FF")
        elif percent < 80:
            self.system_ram_bar.set_progress_color("#FFA500")
        else:
            self.system_ram_bar.set_progress_color("#FF0000")
