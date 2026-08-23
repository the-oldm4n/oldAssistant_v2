import threading
import subprocess
from bin.function_list_main import get_current_speaker
from bin.lists import get_audio_paths
from bin.speak_functions import thread_react
from log_config import logger


class BluetoothController:
    def __init__(self):
        self.is_enabled = False
        self._lock = threading.Lock()
        self._operation_in_progress = False
    
    def _run_ps_in_thread(self, command, callback=None):
        """Запустить PowerShell команду в отдельном потоке"""
        def worker():
            try:
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True,
                    text=True,
                    encoding='cp866',
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                if callback:
                    callback(result)
            except subprocess.TimeoutExpired:
                logger.error("[BLUETOOTH] Bluetooth command timeout")
            except Exception as e:
                logger.error(f"[BLUETOOTH] Bluetooth error: {e}")
            finally:
                with self._lock:
                    self._operation_in_progress = False
        
        with self._lock:
            if self._operation_in_progress:
                return  # Не запускаем новую операцию пока выполняется предыдущая
            self._operation_in_progress = True
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def enable(self, react=True):
        """Включить Bluetooth"""
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('approve_folder'))
        
        def on_complete(result):
            if result and result.returncode == 0:
                with self._lock:
                    self.is_enabled = True
                logger.info("[BLUETOOTH] Enabled")
        
        # Меняем состояние СРАЗУ, а не после выполнения
        with self._lock:
            self.is_enabled = True
        
        cmd = '''
        $bt = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | 
              Where-Object {$_.FriendlyName -like "*bluetooth*"}
        if ($bt) {
            Enable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
        }
        '''
        
        self._run_ps_in_thread(cmd, on_complete)
        return True
    
    def disable(self, react=True):
        """Выключить Bluetooth"""
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('approve_folder'))
        
        def on_complete(result):
            if result and result.returncode == 0:
                with self._lock:
                    self.is_enabled = False
                logger.info("[BLUETOOTH] Disabled")
        
        # Меняем состояние СРАЗУ
        with self._lock:
            self.is_enabled = False
        
        cmd = '''
        $bt = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | 
              Where-Object {$_.FriendlyName -like "*bluetooth*"}
        if ($bt) {
            Disable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
        }
        '''
        
        self._run_ps_in_thread(cmd, on_complete)
        return True
    
    def toggle(self, react=True):
        """Переключить состояние"""
        with self._lock:
            current_state = self.is_enabled
        
        if current_state:
            return self.disable(react)
        else:
            return self.enable(react)
    
    def get_status(self):
        """Получить текущее состояние (для UI)"""
        with self._lock:
            return self.is_enabled


bluetooth_controller = BluetoothController()
