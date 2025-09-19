import psutil
import subprocess
import pygetwindow as gw
import pyautogui
import time
import keyboard

from logging_config import debug_logger


class ToggleMuteDiscord():
    """Класс для мута микрофона в Discord"""

    def __init__(self):
        super().__init__()
        self.discord_window = self.get_discord_window()  # переименовал для ясности

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
                    debug_logger.info(f"Настоящее окно Discord найдено на попытке {attempt + 1}")
                    return discord_windows[0]  # возвращаем окно, а не список

                debug_logger.info(f"Настоящее окно Discord не найдено, попытка {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)

            except Exception as e:
                debug_logger.error(f"Ошибка поиска окна (попытка {attempt + 1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(delay)

        debug_logger.warn("Настоящее окно Discord не найдено после всех попыток")
        return None

    def get_window(self):
        """Возвращает окно Discord если оно существует"""
        return self.discord_window  # просто возвращаем найденное окно

    def simulate_key_combo(self):
        """Симуляция нажатия клавиш с проверкой результата"""
        debug_logger.info("Начинаем симуляцию клавиш Ctrl+Shift+M...")

        success = False

        # Пробуем все три способа последовательно
        methods = [
            self._try_pyautogui_hotkey,
            self._try_keyboard_lib,
            self._try_manual_emulation
        ]

        for method in methods:
            if method():
                success = True
                break
            time.sleep(0.1)  # небольшая пауза между попытками

        debug_logger.info(f"Результат симуляции клавиш: {success}")
        return success

    def _try_pyautogui_hotkey(self):
        """Пытается использовать pyautogui.hotkey"""
        try:
            debug_logger.info("Пробуем pyautogui.hotkey...")
            pyautogui.hotkey('ctrl', 'shift', 'm')
            debug_logger.info("Комбинация через pyautogui отправлена")
            return True
        except Exception as e:
            debug_logger.error(f"Ошибка pyautogui: {e}")
            return False

    def _try_keyboard_lib(self):
        """Пытается использовать keyboard"""
        try:
            debug_logger.info("Пробуем keyboard...")
            keyboard.press('ctrl')
            keyboard.press('shift')
            keyboard.press('m')
            time.sleep(0.05)  # короткая задержка для нажатия
            keyboard.release('m')
            keyboard.release('shift')
            keyboard.release('ctrl')
            debug_logger.info("Комбинация через keyboard отправлена")
            return True
        except Exception as e:
            debug_logger.error(f"Ошибка keyboard: {e}")
            return False

    def _try_manual_emulation(self):
        """Пытается использовать ручную эмуляцию"""
        try:
            debug_logger.info("Пробуем ручную эмуляцию...")
            pyautogui.keyDown('ctrl')
            time.sleep(0.05)
            pyautogui.keyDown('shift')
            time.sleep(0.05)
            pyautogui.press('m')
            time.sleep(0.05)
            pyautogui.keyUp('shift')
            time.sleep(0.05)
            pyautogui.keyUp('ctrl')
            debug_logger.info("Ручная эмуляция выполнена")
            return True
        except Exception as e:
            debug_logger.error(f"Ошибка ручной эмуляции: {e}")
            return False

    def activate_and_mute_discord(self):
        """Активирует окно Discord и выполняет мут с визуальной индикацией"""
        try:
            self.discord_window = self.get_discord_window()
            window = self.get_window()
            if not window:
                debug_logger.warn("Окно Discord не найдено")
                return False

            # Запоминаем текущее активное окно
            current_window = gw.getActiveWindow()

            debug_logger.info(f"Найдено окно Discord: {window.title}")
            debug_logger.info(f"Состояние окна: minimized={window.isMinimized}, visible={window.visible}")

            # Активируем и разворачиваем окно Discord
            if window.isMinimized:
                debug_logger.info("Разворачиваем окно...")
                window.restore()

            debug_logger.info("Активируем окно...")
            window.activate()
            time.sleep(0.1)

            # Убедимся что окно активно
            active_window = gw.getActiveWindow()
            if active_window and 'discord' in active_window.title.lower():
                debug_logger.info("Окно Discord активно!")
            else:
                debug_logger.info("Внимание: окно Discord не стало активным!")

            # Выполняем комбинацию для мута
            success = self.simulate_key_combo()

            if not success:
                debug_logger.error("Все методы нажатия клавиш не сработали!")
                return False

            time.sleep(0.4)

            # Сворачиваем окно Discord
            debug_logger.info("Сворачиваем окно...")
            window.minimize()

            # Возвращаем фокус и мышь
            if current_window:
                try:
                    debug_logger.info("Восстанавливаем предыдущее окно...")
                    current_window.activate()
                except:
                    debug_logger.info("Не удалось восстановить предыдущее окно")

            debug_logger.info("Мут выполнен успешно!")
            return True

        except Exception as e:
            debug_logger.info(f"Ошибка при активации и муте: {e}")
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
                            debug_logger.info(f"Запускаем Discord: {exe_path}")
                            subprocess.Popen([exe_path])
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            debug_logger.info(f"Ошибка при запуске: {e}")
            return False

    def smart_discord_mute(self):
        """Умная функция мута Discord с детальным логированием"""
        # Проверяем существует ли окно Discord
        if self.is_discord_window_exists():
            debug_logger.info("Окно Discord найдено, выполняем мут...")
            self.activate_and_mute_discord()
            return True
        else:
            debug_logger.info("Окно Discord не найдено, запускаем...")
            if self.launch_discord_from_process():
                time.sleep(1.5)
                self.activate_and_mute_discord()
                return True
            else:
                debug_logger.info("Не удалось запустить Discord")
                return False

    def main(self):
        """Запуск функции через отлов ошибок"""
        try:
            return self.smart_discord_mute()
        except Exception as e:
            debug_logger.error(f"Не удалось выполнить мут микрофона в Discord. Ошибка: {e}")
            return False
