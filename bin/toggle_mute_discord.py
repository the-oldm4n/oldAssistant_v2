import ctypes
import random
import psutil
import subprocess
import pydirectinput
import pygetwindow as gw
import pyautogui
import time
import keyboard
from log_config import debuglog


class ToggleMuteDiscord:
    """Класс для мута микрофона в Discord"""

    def __init__(self):
        super().__init__()
        self.discord_window = self.get_discord_window()

    def is_discord_window_exists(self):
        """Проверяет, существует ли окно Discord"""
        try:
            return self.discord_window is not None
        except:
            return False

    def get_discord_window(self, max_attempts=3, delay=0.2):
        """Ищет настоящее окно Discord с перезапросом и фильтрацией"""
        for attempt in range(max_attempts):
            try:
                # Обновляем список окон каждый раз
                all_windows = gw.getWindowsWithTitle('Discord')
                discord_windows = []

                # Фильтруем только настоящие окна Discord
                for window in all_windows:
                    title = window.title.lower()
                    if ('discord' in title and
                            not any(x in title for x in
                                    ['.py', '.txt', 'editor', 'code', 'pycharm', 'vscode', 'visual studio'])):
                        discord_windows.append(window)

                if discord_windows:
                    debuglog.info(f"Настоящее окно Discord найдено на попытке {attempt + 1}")
                    return discord_windows[0]  # возвращаем окно, а не список

                debuglog.info(f"Настоящее окно Discord не найдено, попытка {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)

            except Exception as e:
                debuglog.error(f"Ошибка поиска окна (попытка {attempt + 1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)

        debuglog.warn("Настоящее окно Discord не найдено после всех попыток")
        return None

    def get_window(self):
        """Возвращает окно Discord если оно существует"""
        return self.discord_window  # просто возвращаем найденное окно

    def simulate_key_combo(self):
        """Симуляция нажатия клавиш с проверкой результата - один случайный метод за вызов"""
        debuglog.info("Начинаем симуляцию клавиш Ctrl+Shift+M...")

        # Список всех доступных методов
        all_methods = [
            self._try_pydirectinput_hotkey,
            self._try_ctypes_hotkey,
            # self._try_pyautogui_hotkey,
            # self._try_keyboard_lib,
            # self._try_pywinauto_send_keys,
            # self._try_manual_emulation,
        ]

        # Инициализируем атрибут для хранения последнего метода, если его еще нет
        if not hasattr(self, 'last_used_method'):
            self.last_used_method = None

        # Создаем список методов, исключая последний использованный (если он есть)
        available_methods = all_methods.copy()
        if self.last_used_method in available_methods:
            available_methods.remove(self.last_used_method)

        # Если есть доступные методы, выбираем случайный из них
        if available_methods:
            selected_method = random.choice(available_methods)
        else:
            # Если все методы были использованы, выбираем любой
            selected_method = random.choice(all_methods)

        debuglog.info(f"Выбран метод: {selected_method.__name__}")

        # Пробуем только один выбранный метод
        success = selected_method()

        # Запоминаем последний использованный метод
        self.last_used_method = selected_method

        debuglog.info(f"Результат симуляции клавиш: {success}")
        return success

    def _try_ctypes_hotkey(self):
        """Пытается использовать низкоуровневый метод ctypes"""
        low_level_kb = LowLevelKeyboard()
        return low_level_kb._try_ctypes_hotkey()

    def _try_pydirectinput_hotkey(self):
        """Пытается использовать PyDirectInput для эмуляции Ctrl+Shift+M"""
        try:
            debuglog.info("Метод <<<[PyDirectInput]>>>")

            # Нажимаем Ctrl+Shift+M
            pydirectinput.keyDown('ctrl')
            pydirectinput.keyDown('shift')
            pydirectinput.keyDown('m')
            pydirectinput.keyUp('shift')
            pydirectinput.keyUp('ctrl')
            pydirectinput.keyUp('m')

            debuglog.info("Метод выполнен")
            return True
        except Exception as e:
            debuglog.error(f"Ошибка PyDirectInput: {e}")
            return False

    def _reset_keyboard(self):
        """Сбрасывает все зажатые клавиши"""
        try:
            for key in ['ctrl', 'shift', 'm']:
                pyautogui.keyUp(key)
                keyboard.release(key)
        except:
            pass

    # def _try_pyautogui_hotkey(self):
    #     """Пытается использовать pyautogui.hotkey"""
    #     self._reset_keyboard()
    #     try:
    #         debuglog.info("Метод <<<[pyautogui.hotkey]>>>")
    #         pyautogui.hotkey('ctrl', 'shift', 'm')
    #         debuglog.info("Метод выполнен")
    #         self._reset_keyboard()
    #         return True
    #     except Exception as e:
    #         debuglog.error(f"Ошибка pyautogui: {e}")
    #         return False
    #
    # def _try_keyboard_lib(self):
    #     """Пытается использовать keyboard"""
    #     self._reset_keyboard()
    #     try:
    #         debuglog.info("Метод <<<[keyboard]>>>")
    #         keyboard.press('ctrl')
    #         keyboard.press('shift')
    #         keyboard.press('m')
    #         keyboard.release('ctrl')
    #         keyboard.release('shift')
    #         keyboard.release('m')
    #         debuglog.info("Метод выполнен")
    #         self._reset_keyboard()
    #         return True
    #     except Exception as e:
    #         debuglog.error(f"Ошибка keyboard: {e}")
    #         return False
    #
    # def _try_manual_emulation(self):
    #     """Пытается использовать ручную эмуляцию"""
    #     self._reset_keyboard()
    #     try:
    #         debuglog.info("Метод <<<[Ручная эмуляция pyautogui]>>>")
    #         pyautogui.keyDown('ctrl')
    #         pyautogui.keyDown('shift')
    #         pyautogui.keyDown('m')
    #         pyautogui.keyUp('shift')
    #         pyautogui.keyUp('ctrl')
    #         pyautogui.keyUp('m')
    #         debuglog.info("Метод выполнен")
    #         self._reset_keyboard()
    #         return True
    #     except Exception as e:
    #         debuglog.error(f"Ошибка ручной эмуляции: {e}")
    #         return False
    #
    # def _try_pywinauto_send_keys(self):
    #     """Пытается использовать PyWinAuto для отправки ^+m в окно Discord"""
    #     from pywinauto import Application, ElementNotFoundError
    #     try:
    #         debuglog.info("Метод <<<[PyWinAuto]>>>")
    #
    #         # Подключаемся к окну Discord по заголовку
    #         app = Application(backend="uia").connect(title_re=".*Discord.*")
    #
    #         # Находим главное окно
    #         main_window = app.top_window()
    #
    #         # Если окно свернуто — разворачиваем (опционально)
    #         if main_window.is_minimized():
    #             main_window.restore()
    #             time.sleep(0.3)
    #
    #         # Отправляем хоткей: ^ = Ctrl, + = Shift, m = M
    #         main_window.type_keys('^+m', set_foreground=True)  # set_foreground=False — не активировать окно!
    #
    #         debuglog.info("Метод выполнен")
    #         return True
    #     except ElementNotFoundError:
    #         debuglog.error("Окно Discord не найдено через PyWinAuto")
    #         return False
    #     except Exception as e:
    #         debuglog.error(f"Ошибка PyWinAuto: {e}")
    #         return False

    def activate_and_mute_discord(self):
        """Активирует окно Discord и выполняет мут с визуальной индикацией"""
        try:
            self.discord_window = self.get_discord_window()
            window = self.get_window()
            if not window:
                debuglog.warn("Окно Discord не найдено")
                return False

            # Запоминаем текущее активное окно
            current_window = gw.getActiveWindow()

            debuglog.info(f"Найдено окно Discord: {window.title}")
            debuglog.info(f"Состояние окна: minimized={window.isMinimized}, visible={window.visible}")

            # Активируем и разворачиваем окно Discord
            if window.isMinimized:
                debuglog.info("Разворачиваем окно...")
                window.restore()

            debuglog.info("Активируем окно...")
            window.activate()
            # time.sleep(0.1)

            # Убедимся что окно активно
            active_window = gw.getActiveWindow()
            if active_window and 'discord' in active_window.title.lower():
                debuglog.info("Окно Discord активно!")
            else:
                debuglog.info("Внимание: окно Discord не стало активным!")

            # Выполняем комбинацию для мута
            success = self.simulate_key_combo()

            if not success:
                debuglog.error("Метод нажатия клавиш не сработал!")
                return False

            time.sleep(0.5)

            # Сворачиваем окно Discord
            debuglog.info("Сворачиваем окно...")
            window.minimize()

            # Возвращаем фокус
            if current_window:
                try:
                    debuglog.info("Восстанавливаем предыдущее окно...")
                    current_window.activate()
                except:
                    debuglog.info("Не удалось восстановить предыдущее окно")

            debuglog.info("Мут выполнен успешно!")
            return True

        except Exception as e:
            debuglog.info(f"Ошибка при активации и муте: {e}")
            return False

    def launch_discord_from_process(self):
        """Запускает Discord из пути процесса"""
        try:
            for proc in psutil.process_iter():
                try:
                    name = proc.name().lower()
                    if 'discord' in name:
                        exe_path = proc.exe()
                        if exe_path:
                            debuglog.info(f"Запускаем Discord: {exe_path}")
                            subprocess.Popen([exe_path])
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            debuglog.info(f"Ошибка при запуске: {e}")
            return False

    def smart_discord_mute(self):
        """Умная функция мута Discord с детальным логированием"""
        # Проверяем существует ли окно Discord
        if self.is_discord_window_exists():
            debuglog.info("Окно Discord найдено, выполняем мут...")
            self.activate_and_mute_discord()
            return True
        else:
            debuglog.info("Окно Discord не найдено, запускаем...")
            if self.launch_discord_from_process():
                time.sleep(1.5)
                self.activate_and_mute_discord()
                return True
            else:
                debuglog.info("Не удалось запустить Discord")
                return False

    def main(self):
        """Запуск функции через отлов ошибок"""
        try:
            return self.smart_discord_mute()
        except Exception as e:
            debuglog.error(f"Не удалось выполнить мут микрофона в Discord. Ошибка: {e}")
            return False


class LowLevelKeyboard:
    """Низкоуровневый класс для работы с клавиатурой через ctypes"""
    def __init__(self):
        self.user32 = ctypes.windll.user32
        # Константы Windows API
        self.VK_CONTROL = 0x11
        self.VK_SHIFT = 0x10
        self.VK_M = 0x4D
        self.KEYEVENTF_KEYDOWN = 0x0000
        self.KEYEVENTF_KEYUP = 0x0002

    def _try_ctypes_hotkey(self):
        """Пытается использовать низкоуровневый метод ctypes"""
        self._reset_keyboard()
        try:
            debuglog.info("Метод <<<[ctypes hotkey]>>>")

            # Нажимаем клавиши в правильном порядке
            self.user32.keybd_event(self.VK_CONTROL, 0, self.KEYEVENTF_KEYDOWN, 0)
            time.sleep(0.01)
            self.user32.keybd_event(self.VK_SHIFT, 0, self.KEYEVENTF_KEYDOWN, 0)
            time.sleep(0.01)
            self.user32.keybd_event(self.VK_M, 0, self.KEYEVENTF_KEYDOWN, 0)
            time.sleep(0.02)  # Задержка для нажатия

            # Отпускаем в обратном порядке
            self.user32.keybd_event(self.VK_M, 0, self.KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
            self.user32.keybd_event(self.VK_SHIFT, 0, self.KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
            self.user32.keybd_event(self.VK_CONTROL, 0, self.KEYEVENTF_KEYUP, 0)

            debuglog.info("Метод выполнен")
            self._reset_keyboard()
            return True
        except Exception as e:
            debuglog.error(f"Ошибка ctypes: {e}")
            self._reset_keyboard()
            return False

    def _reset_keyboard(self):
        """Сбрасывает все зажатые клавиши"""
        try:
            # Сбрасываем конкретные клавиши, которые используем
            keys_to_reset = [self.VK_CONTROL, self.VK_SHIFT, self.VK_M]
            for key in keys_to_reset:
                try:
                    self.user32.keybd_event(key, 0, self.KEYEVENTF_KEYUP, 0)
                except:
                    pass
            time.sleep(0.01)
        except Exception as e:
            debuglog.debug(f"Ошибка при сбросе клавиатуры: {e}")
