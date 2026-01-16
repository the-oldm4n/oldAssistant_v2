from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, QThread, Signal, Slot
from PySide6.QtGui import Qt
import wmi
import pythoncom
import subprocess
import os
from bin.custom_svg_widget import CustomSvgWidget
from bin.apply_color_methods import main_apply_colors
from bin.signals import color_signal
from logging_config import debug_logger

class SensorWorker(QThread):
    """Поток для получения данных сенсоров"""
    data_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, ohm_namespace):
        super().__init__()
        self.ohm_namespace = ohm_namespace
        self._running = True
        
    def run(self):
        """Основной цикл потока"""
        pythoncom.CoInitialize()
        
        try:
            while self._running:
                data = self._fetch_sensor_data()
                if data:
                    self.data_ready.emit(data)
                self.msleep(1000)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            pythoncom.CoUninitialize()
    
    def _fetch_sensor_data(self):
        """Получение данных с датчиков"""
        try:
            wmi_conn = wmi.WMI(namespace=self.ohm_namespace)
            sensors = wmi_conn.Sensor()
            
            if not sensors:
                return None

            temp_by_name = {}
            load_by_name = {}
            power_by_name = {}
            clock_by_name = {}
            data_by_name = {}
            
            for s in sensors:
                if hasattr(s, 'Value') and s.Value is not None:
                    try:
                        value = float(s.Value)
                        name = str(s.Name).lower()
                        
                        if s.SensorType == 'Temperature':
                            temp_by_name[name] = round(value)
                        elif s.SensorType == 'Load':
                            load_by_name[name] = round(value)
                        elif s.SensorType == 'Power':
                            power_by_name[name] = round(value)
                        elif s.SensorType == 'Clock':
                            clock_by_name[name] = round(value)
                        elif s.SensorType == 'Data':
                            data_by_name[name] = round(value, 2)
                    except (ValueError, TypeError):
                        continue

            data = {
                'cpu': self._get_cpu_data(temp_by_name, load_by_name, power_by_name, clock_by_name),
                'gpu': self._get_gpu_data(temp_by_name, load_by_name, power_by_name, clock_by_name),
                'ram': self._get_ram_data(data_by_name)
            }
            
            return data
            
        except Exception as e:
            debug_logger.error(f"[SENSOR] Fetch error: {e}")
            return None
    
    def _get_cpu_data(self, temp, load, power, clock):
        """Получить данные CPU"""
        return {
            'temp': next((v for k, v in temp.items() 
                         if 'cpu' in k and ('core' in k or 'package' in k)), '--'),
            'load': next((v for k, v in load.items() 
                         if 'cpu' in k and 'total' in k), '--'),
            'power': next((v for k, v in power.items() 
                          if 'cpu' in k and 'package' in k), '--'),
            'clock': next((v for k, v in clock.items() 
                          if 'cpu' in k and 'core' in k), '--')
        }
    
    def _get_gpu_data(self, temp, load, power, clock):
        """Получить данные GPU"""
        return {
            'temp': next((v for k, v in temp.items() 
                         if 'gpu' in k and 'core' in k), '--'),
            'load': next((v for k, v in load.items() 
                         if 'gpu' in k and 'core' in k), '--'),
            'power': next((v for k, v in power.items() 
                          if 'gpu' in k), '--'),
            'clock': next((v for k, v in clock.items() 
                          if 'gpu' in k and 'core' in k), '--')
        }
    
    def _get_ram_data(self, data_dict):
        """Получить данные RAM"""
        usage = next((v for k, v in data_dict.items() 
                     if 'used' in k and 'memory' in k), '--')
        free = next((v for k, v in data_dict.items() 
                    if 'available' in k and 'memory' in k), '--')
        
        if usage != '--' and free != '--':
            total = round(usage + free, 2)
        else:
            total = '--'
            
        return {'usage': usage, 'total': total}
    
    def stop(self):
        """Остановка потока"""
        self._running = False
        if self.isRunning():  # ← ДОБАВЬТЕ ЭТУ ПРОВЕРКУ
            self.quit()  # ← ВЫЗОВИТЕ quit()
            self.wait(1000)


class SensorTab(QWidget):
    """Вкладка мониторинга оборудования"""
    
    def __init__(self, icon_paths, ohm_path, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_monitor_colors)
        self.icon_paths = icon_paths
        self.ohm_path = ohm_path
        self.ohm_namespace = "root\\OpenHardwareMonitor"
        self.hardware_monitor_svg = []
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        self.cpu_labels = {}
        self.gpu_labels = {}
        self.ram_labels = {}
        self.sensor_worker = None
        self.style_manager = main_apply_colors
        self.styles = self.style_manager.load_styles()
        
        self._init_ui()
        # self._init_ohm()
        self.update_monitor_colors()

    def update_monitor_colors(self):
        self.styles = self.style_manager.load_styles()

        for svg in self.hardware_monitor_svg:
            self.style_manager.apply_color_svg(svg, strength=0.95)

    def start_monitoring(self):
        """Запустить мониторинг (вызывать когда зашли на вкладку)"""
        debug_logger.info(f"[SENSOR_OHM] Запущен мониторинг")
        if not hasattr(self, '_ohm_started') or not self._ohm_started:
            self._init_ohm()
            self._ohm_started = True
    
    def stop_monitoring(self):
        """Остановить мониторинг (БЛОКИРУЮЩИЙ метод)"""
        debug_logger.info(f"[SENSOR_OHM] Останавливаем мониторинг...")

        self._cleaning_up = True

        if self.sensor_worker:
            debug_logger.debug("[SENSOR] Останавливаем worker thread...")
            self.sensor_worker.stop()
            
            if self.sensor_worker.isRunning():
                self.sensor_worker.wait(2000)
                if self.sensor_worker.isRunning():
                    debug_logger.warning("[SENSOR] Принудительное завершение потока")
                    self.sensor_worker.terminate()
                    self.sensor_worker.wait(500)
            
            self.sensor_worker = None
            debug_logger.debug("[SENSOR] Worker thread остановлен")

        if hasattr(self, '_ohm_started') and self._ohm_started:
            self._close_ohm()
            self._ohm_started = False
        
        debug_logger.info(f"[SENSOR_OHM] Мониторинг остановлен")
    
    def _close_ohm(self):
        """Закрыть OHM"""
        try:
            subprocess.run(
                ['taskkill', '/IM', "OpenHardwareMonitor.exe", '/F'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=2  # Таймаут 2 секунды
            )
        except subprocess.TimeoutExpired:
            debug_logger.warning("[SENSOR] OHM не закрылся вовремя")
        except:
            pass
    
    def cleanup(self):
        """Очистка ресурсов - вызывается перед удалением"""
        self.stop_monitoring()

    def safe_delete(self):
        """Безопасное удаление виджета"""
        self.cleanup()
        self.deleteLater()
        
    def _init_ui(self):
        """Инициализация интерфейса"""
        self.setObjectName("SensorsTab")
        self.setStyleSheet("""
            #SensorsTab {
                background: transparent;
            }
            QLabel {
                background: transparent;
                color: white;
                font-size: 14px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 15, 5, 5)
        layout.setSpacing(5)
        
        layout.addLayout(self._create_cpu_section())
        layout.addLayout(self._create_gpu_section())
        layout.addLayout(self._create_ram_section())
        
        layout.addStretch()
    
    def _create_cpu_section(self):
        """Создать секцию CPU"""
        layout = QHBoxLayout()
        layout.setSpacing(0)
        
        cpu_icon = CustomSvgWidget(self.icon_paths['cpu'])
        cpu_icon.setFixedSize(30, 30)
        layout.addWidget(cpu_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(cpu_icon)
        
        temp_icon = CustomSvgWidget(self.icon_paths['thermo'])
        temp_icon.setFixedSize(20, 20)
        layout.addWidget(temp_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(temp_icon)
        
        self.cpu_labels['temp'] = QLabel("--°C")
        layout.addWidget(self.cpu_labels['temp'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        load_icon = CustomSvgWidget(self.icon_paths['percent'])
        load_icon.setFixedSize(20, 20)
        layout.addWidget(load_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(load_icon)
        
        self.cpu_labels['load'] = QLabel("--%")
        layout.addWidget(self.cpu_labels['load'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        power_icon = CustomSvgWidget(self.icon_paths['power'])
        power_icon.setFixedSize(20, 20)
        layout.addWidget(power_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(power_icon)
        
        self.cpu_labels['power'] = QLabel("--W")
        layout.addWidget(self.cpu_labels['power'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        clock_icon = CustomSvgWidget(self.icon_paths['clock'])
        clock_icon.setFixedSize(20, 20)
        layout.addWidget(clock_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(clock_icon)
        
        self.cpu_labels['clock'] = QLabel("--МГц")
        layout.addWidget(self.cpu_labels['clock'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        layout.addStretch()
        return layout
    
    def _create_gpu_section(self):
        """Создать секцию GPU"""
        layout = QHBoxLayout()
        layout.setSpacing(0)
        
        gpu_icon = CustomSvgWidget(self.icon_paths['gpu'])
        gpu_icon.setFixedSize(30, 30)
        layout.addWidget(gpu_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(gpu_icon)
        
        temp_icon = CustomSvgWidget(self.icon_paths['thermo'])
        temp_icon.setFixedSize(20, 20)
        layout.addWidget(temp_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(temp_icon)
        
        self.gpu_labels['temp'] = QLabel("--°C")
        layout.addWidget(self.gpu_labels['temp'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        load_icon = CustomSvgWidget(self.icon_paths['percent'])
        load_icon.setFixedSize(20, 20)
        layout.addWidget(load_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(load_icon)
        
        self.gpu_labels['load'] = QLabel("--%")
        layout.addWidget(self.gpu_labels['load'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        power_icon = CustomSvgWidget(self.icon_paths['power'])
        power_icon.setFixedSize(20, 20)
        layout.addWidget(power_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(power_icon)
        
        self.gpu_labels['power'] = QLabel("--W")
        layout.addWidget(self.gpu_labels['power'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        clock_icon = CustomSvgWidget(self.icon_paths['clock'])
        clock_icon.setFixedSize(20, 20)
        layout.addWidget(clock_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(clock_icon)
        
        self.gpu_labels['clock'] = QLabel("--МГц")
        layout.addWidget(self.gpu_labels['clock'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        layout.addStretch()
        return layout
    
    def _create_ram_section(self):
        """Создать секцию RAM"""
        layout = QHBoxLayout()
        layout.setSpacing(0)
        
        ram_icon = CustomSvgWidget(self.icon_paths['ram'])
        ram_icon.setFixedSize(30, 30)
        layout.addWidget(ram_icon, alignment=Qt.AlignmentFlag.AlignTop)
        self.hardware_monitor_svg.append(ram_icon)
        
        self.ram_labels['usage'] = QLabel("-- GB")
        layout.addWidget(self.ram_labels['usage'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        slash_label = QLabel("/")
        layout.addWidget(slash_label, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.ram_labels['total'] = QLabel("-- GB")
        layout.addWidget(self.ram_labels['total'], alignment=Qt.AlignmentFlag.AlignBottom)
        
        layout.addStretch()
        return layout
    
    def _init_ohm(self):
        """Инициализация OpenHardwareMonitor"""
        try:
            if not os.path.exists(self.ohm_path):
                debug_logger.error(f"[SENSOR] OHM not found: {self.ohm_path}")
                return
            
            tasks = subprocess.check_output('tasklist', shell=True).decode('cp866', errors='ignore')
            if "OpenHardwareMonitor.exe" not in tasks:
                # Запускаем
                result = subprocess.run([
                    "powershell",
                    "-Command",
                    f'Start-Process "{self.ohm_path}" -WindowStyle Hidden -Verb runAs'
                ],
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                if result.returncode != 0:
                    debug_logger.error(f"[SENSOR] Failed to start OHM: {result.stderr}")
                    return
            
            QTimer.singleShot(3000, self._start_sensor_worker)
            
        except Exception as e:
            debug_logger.error(f"[SENSOR] OHM init error: {e}")
    
    def _start_sensor_worker(self):
        """Запуск потока сбора данных"""
        try:
            self.sensor_worker = SensorWorker(self.ohm_namespace)
            self.sensor_worker.data_ready.connect(self._update_ui_from_data)
            self.sensor_worker.error_occurred.connect(self._handle_sensor_error)
            self.sensor_worker.finished.connect(self._on_worker_finished)
            self.sensor_worker.start()
            
        except Exception as e:
            debug_logger.error(f"[SENSOR] Failed to start worker: {e}")

    @Slot()
    def _on_worker_finished(self):
        """Поток завершился"""
        debug_logger.debug("[SENSOR] Worker thread finished")
        self.sensor_worker = None
    
    @Slot(dict)
    def _update_ui_from_data(self, data):
        """Обновление UI из данных"""
        try:
            cpu = data.get('cpu', {})
            if cpu:
                self.cpu_labels['temp'].setText(f"{cpu.get('temp', '--')}°C")
                self.cpu_labels['load'].setText(f"{cpu.get('load', '--')}%")
                self.cpu_labels['power'].setText(f"{cpu.get('power', '--')}W")
                self.cpu_labels['clock'].setText(f"{cpu.get('clock', '--')}МГц")
            
            gpu = data.get('gpu', {})
            if gpu:
                self.gpu_labels['temp'].setText(f"{gpu.get('temp', '--')}°C")
                self.gpu_labels['load'].setText(f"{gpu.get('load', '--')}%")
                self.gpu_labels['power'].setText(f"{gpu.get('power', '--')}W")
                self.gpu_labels['clock'].setText(f"{gpu.get('clock', '--')}МГц")
            
            ram = data.get('ram', {})
            if ram:
                usage = ram.get('usage', '--')
                total = ram.get('total', '--')
                self.ram_labels['usage'].setText(f"{usage} GB")
                self.ram_labels['total'].setText(f"{total} GB" if total != '--' else "-- GB")
                
        except Exception as e:
            debug_logger.error(f"[SENSOR] UI update error: {e}")
    
    @Slot(str)
    def _handle_sensor_error(self, error_msg):
        """Обработка ошибок сенсоров"""
        debug_logger.error(f"[SENSOR] Error: {error_msg}")
        self._set_default_values()
    
    def _set_default_values(self):
        """Установить значения по умолчанию"""
        self.cpu_labels['temp'].setText("--°C")
        self.cpu_labels['load'].setText("--%")
        self.cpu_labels['power'].setText("--W")
        self.cpu_labels['clock'].setText("--МГц")
        
        self.gpu_labels['temp'].setText("--°C")
        self.gpu_labels['load'].setText("--%")
        self.gpu_labels['power'].setText("--W")
        self.gpu_labels['clock'].setText("--МГц")
        
        self.ram_labels['usage'].setText("-- GB")
        self.ram_labels['total'].setText("-- GB")
