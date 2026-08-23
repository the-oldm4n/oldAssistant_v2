from PySide6.QtCore import QThread, Signal
import time
import os
from datetime import datetime
import win32clipboard
from PIL import Image, ImageGrab
import io
import ctypes
from log_config import assist_log, logger
from path_builder import get_path
from bin.speak_functions import thread_play_sound

class ScreenshotThread(QThread):
    finished_signal = Signal(bool)
    error_signal = Signal(str)
    
    def __init__(self, save_dir, capture_type="area"):
        super().__init__()
        self.save_dir = save_dir
        self.capture_type = capture_type
        self._is_running = True

    def stop(self):
        """Остановка потока"""
        self._is_running = False
        self.quit()
        if not self.wait(1000):  # Ждем до 1 секунды
            self.terminate()  # Принудительно завершаем если не остановился
            self.wait()

    def run(self):
        """Основной метод потока"""
        try:
            if self.capture_type == "area":
                result = self._wait_and_save_screenshot()
            else:
                result = self._wait_and_save_screenshot()
                
            self.finished_signal.emit(bool(result))
        except Exception as e:
            self.error_signal.emit(str(e))

    def _wait_and_save_screenshot(self, timeout=10):
        """Логика ожидания скриншота"""
        start_time = time.time()
        last_sequence = -1
        last_change_time = time.time()
        snipping_started = False
        max_wait_after_cancel = 1.5

        while time.time() - start_time < timeout and self._is_running:
            try:
                current_sequence = self._get_clipboard_sequence()

                if current_sequence != last_sequence:
                    image = self._get_image_from_clipboard()
                    if image:
                        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        filepath = os.path.join(self.save_dir, filename)
                        image.save(filepath, "PNG")
                        return True

                    last_sequence = current_sequence
                    last_change_time = time.time()
                    snipping_started = True
                else:
                    if snipping_started and (time.time() - last_change_time > max_wait_after_cancel):
                        logger.info("Захват отменен пользователем")
                        return False
                        
                    if not snipping_started and (time.time() - start_time > 3.0):
                        logger.info("Инструмент захвата не был активирован")
                        return False

            except Exception as e:
                logger.error(f"Ошибка проверки буфера: {e}")

            time.sleep(0.1)

        logger.warning("Таймаут ожидания скриншота")
        return False

    def _move_latest_screenshot(self):
        """Перенос скриншота для fullscreen"""
        try:
            pics_dir = os.path.join(os.environ['USERPROFILE'], 'Pictures', 'Screenshots')
            if os.path.exists(pics_dir):
                files = [f for f in os.listdir(pics_dir) if f.lower().endswith('.png')]
                if files:
                    latest = max(
                        [os.path.join(pics_dir, f) for f in files],
                        key=os.path.getctime
                    )
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    new_path = os.path.join(self.save_dir, filename)
                    os.rename(latest, new_path)
                    return True
        except Exception as e:
            assist_log.error(f"Ошибка переноса: {e}")
            logger.error(f"Ошибка переноса: {e}")
        return False

    def _get_clipboard_sequence(self):
        """Получаем номер последовательности буфера обмена"""
        try:
            win32clipboard.OpenClipboard()
            return win32clipboard.GetClipboardSequenceNumber()
        finally:
            win32clipboard.CloseClipboard()

    def _get_image_from_clipboard(self):
        """Улучшенное получение изображения из буфера обмена"""
        try:
            win32clipboard.OpenClipboard()

            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                try:
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                    if isinstance(data, bytes):
                        bmp_header = b'BM' + (len(data) + 14).to_bytes(4, 'little') + b'\x00\x00\x00\x00\x36\x00\x00\x00'
                        bmp_data = bmp_header + data
                        return Image.open(io.BytesIO(bmp_data))
                except Exception as e:
                    logger.error(f"Ошибка обработки DIB: {e}")

            try:
                image = ImageGrab.grabclipboard()
                if image:
                    return image
            except Exception as e:
                logger.error(f"Ошибка ImageGrab: {e}")

            png_format = win32clipboard.RegisterClipboardFormat("PNG")
            if win32clipboard.IsClipboardFormatAvailable(png_format):
                try:
                    data = win32clipboard.GetClipboardData(png_format)
                    if isinstance(data, bytes):
                        return Image.open(io.BytesIO(data))
                except Exception as e:
                    logger.error(f"Ошибка обработки PNG: {e}")

        except Exception as e:
            logger.error(f"Ошибка доступа к буферу: {e}")
        finally:
            win32clipboard.CloseClipboard()

        return None
    
    
class SystemScreenshot:
    def __init__(self, save_dir=get_path("user_data", "screenshots")):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self._worker = None
        self._thread = None

    def capture_area(self):
        """Захват области в отдельном потоке"""
        try:
            # Очищаем буфер перед захватом
            self._clear_clipboard()

            # Вызываем системный инструмент
            self._press_win_shift_s()
            assist_log.info("Выделите область на экране...")
            logger.info("Выделите область на экране...")

            # Запускаем в отдельном потоке
            return self._start_capture_thread("area")

        except Exception as e:
            assist_log.error(f"Ошибка: {e}")
            logger.error(f"Ошибка: {e}")
            return False

    def capture_fullscreen(self):
        """Захват всего экрана через Win+PrtScn в отдельном потоке"""
        try:
            # Очищаем буфер перед захватом
            self._clear_clipboard()
            self._press_win_prtscn()
            time.sleep(1)
            
            # Запускаем в отдельном потоке для fullscreen
            return self._start_capture_thread("fullscreen")
            
        except Exception as e:
            assist_log.error(f"Ошибка: {e}")
            logger.error(f"Ошибка: {e}")
            return False
        
    def _on_capture_finished(self, success):
        """Обработчик завершения захвата"""
        if success:
            thread_play_sound(type_sound="ok")
            assist_log.info("Скриншот успешно сохранен")
        else:
            thread_play_sound(type_sound="error")
            assist_log.warning("Не удалось сохранить скриншот")

    def _on_capture_error(self, error_msg):
        """Обработчик ошибки захвата"""
        thread_play_sound(type_sound="error")
        assist_log.error(f"Ошибка захвата: {error_msg}")
        logger.error(f"Ошибка захвата: {error_msg}")

    def cancel_capture(self):
        """Отмена захвата"""
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        
    def _wait_and_save_screenshot(self, timeout=15):
        """Логика ожидания скриншота с улучшенным детектированием отмены"""
        start_time = time.time()
        last_sequence = -1
        last_change_time = time.time()
        
        # Флаг что инструмент захвата был активирован
        snipping_started = False
        max_wait_after_cancel = 1.5  # Максимальное время ожидания после отмены

        while time.time() - start_time < timeout and self._is_running:
            try:
                current_sequence = self._get_clipboard_sequence()

                if current_sequence != last_sequence:
                    image = self._get_image_from_clipboard()
                    if image:
                        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        filepath = os.path.join(self.save_dir, filename)
                        image.save(filepath, "PNG")
                        return True

                    last_sequence = current_sequence
                    last_change_time = time.time()
                    snipping_started = True  # Буфер изменился - инструмент работал
                else:
                    # Если инструмент был активирован, но буфер не меняется долгое время - это отмена
                    if snipping_started and (time.time() - last_change_time > max_wait_after_cancel):
                        logger.info("Захват отменен пользователем")
                        return False
                        
                    # Если инструмент не активировался вообще за разумное время - тоже отмена
                    if not snipping_started and (time.time() - start_time > 3.0):
                        logger.info("Инструмент захвата не был активирован")
                        return False

            except Exception as e:
                logger.error(f"Ошибка проверки буфера: {e}")

            time.sleep(0.1)

        logger.warning("Таймаут ожидания скриншота")
        return False
    
    def _start_capture_thread(self, capture_type):
        """Запускает захват в отдельном потоке"""
        try:
            # Останавливаем предыдущий поток если есть
            if self._thread and self._thread.isRunning():
                self._thread.stop()

            # Создаем и настраиваем поток
            self._thread = ScreenshotThread(self.save_dir, capture_type)
            self._thread.finished_signal.connect(self._on_capture_finished)
            self._thread.error_signal.connect(self._on_capture_error)
            
            # Запускаем поток
            self._thread.start()
            return True

        except Exception as e:
            assist_log.error(f"Ошибка запуска потока: {e}")
            logger.error(f"Ошибка запуска потока: {e}")
            return False
        
        # noinspection PyUnresolvedReferences
    def _press_win_shift_s(self):
        """Нажатие Win+Shift+S"""
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Win
        ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)  # Shift
        ctypes.windll.user32.keybd_event(0x53, 0, 0, 0)  # S
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(0x53, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)

    # noinspection PyUnresolvedReferences
    def _press_win_prtscn(self):
        """Нажатие Win+PrtScn"""
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Win
        ctypes.windll.user32.keybd_event(0x2C, 0, 0, 0)  # PrtScn
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(0x2C, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)

    def _move_latest_screenshot(self):
        """Переносит последний скриншот из стандартной папки"""
        try:
            pics_dir = os.path.join(os.environ['USERPROFILE'], 'Pictures', 'Screenshots')
            if os.path.exists(pics_dir):
                files = [f for f in os.listdir(pics_dir) if f.lower().endswith('.png')]
                if files:
                    latest = max(
                        [os.path.join(pics_dir, f) for f in files],
                        key=os.path.getctime
                    )
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    new_path = os.path.join(self.save_dir, filename)
                    os.rename(latest, new_path)
                    return new_path
        except Exception as e:
            assist_log.error(f"Ошибка переноса: {e}")
            logger.error(f"Ошибка переноса: {e}")
        return None

    def _get_clipboard_sequence(self):
        """Получаем номер последовательности буфера обмена"""
        try:
            win32clipboard.OpenClipboard()
            return win32clipboard.GetClipboardSequenceNumber()
        finally:
            win32clipboard.CloseClipboard()

    def _clear_clipboard(self):
        """Очищаем буфер обмена"""
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()

    def _get_image_from_clipboard(self):
        """Улучшенное получение изображения из буфера обмена"""
        try:
            win32clipboard.OpenClipboard()

            # Проверяем доступные форматы
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                # Работаем с DIB (Device Independent Bitmap)
                try:
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                    if isinstance(data, bytes):
                        # Создаем BMP-файл в памяти
                        bmp_header = b'BM' + (len(data) + 14).to_bytes(4,
                                                                       'little') + b'\x00\x00\x00\x00\x36\x00\x00\x00'
                        bmp_data = bmp_header + data
                        return Image.open(io.BytesIO(bmp_data))
                except Exception as e:
                    assist_log.error(f"Ошибка обработки DIB: {e}")
                    logger.error(f"Ошибка обработки DIB: {e}")

            # Альтернативный способ через ImageGrab
            try:
                image = ImageGrab.grabclipboard()
                if image:
                    return image
            except Exception as e:
                assist_log.error(f"Ошибка ImageGrab: {e}")
                logger.error(f"Ошибка ImageGrab: {e}")

            # Проверяем PNG (если доступен)
            png_format = win32clipboard.RegisterClipboardFormat("PNG")
            if win32clipboard.IsClipboardFormatAvailable(png_format):
                try:
                    data = win32clipboard.GetClipboardData(png_format)
                    if isinstance(data, bytes):
                        return Image.open(io.BytesIO(data))
                except Exception as e:
                    assist_log.error(f"Ошибка обработки PNG: {e}")
                    logger.error(f"Ошибка обработки PNG: {e}")

        except Exception as e:
            assist_log.error(f"Ошибка доступа к буферу: {e}")
            logger.error(f"Ошибка доступа к буферу: {e}")
        finally:
            win32clipboard.CloseClipboard()

        return None