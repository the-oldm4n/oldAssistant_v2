import json
import os
import random
import threading

from logging_config import logger, debug_logger
from path_builder import get_path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # Скрываем приветствие pygame
import pygame


def load_volume_assist():
    settings_file_path = get_path('user_settings', 'settings.json')
    if os.path.exists(settings_file_path):
        try:
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get('volume_assist', 0.2)  # Возвращаем значение по умолчанию, если ключ отсутствует
        except json.JSONDecodeError:
            logger.error(f"Ошибка: файл {settings_file_path} содержит некорректный JSON.")
            debug_logger.error(f"Ошибка: файл {settings_file_path} содержит некорректный JSON.")
    else:
        logger.error(f"Файл настроек {settings_file_path} не найден.")
        debug_logger.error(f"Файл настроек {settings_file_path} не найден.")
    return 0.2

def react(folder_path):
    """
    Воспроизводит случайный аудиофайл из указанной папки.
    :param folder_path: Путь к папке с аудиофайлами.
    """
    volume_reduction_factor = load_volume_assist()  # Загружаем из файла настроек значение громкости
    try:
        # Получение списка файлов в папке
        audio_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.ogg')]

        if not audio_files:
            logger.info(f"В папке {folder_path} нет аудиофайлов.")
            debug_logger.info(f"В папке {folder_path} нет аудиофайлов.")
            return

        # Выбор случайного файла
        random_audio_file = random.choice(audio_files)
        random_filename = os.path.basename(random_audio_file)[:-4]
        logger.info(f"Ответ ассистента: {random_filename}")
        debug_logger.info(f"Ответ ассистента: {random_filename}")

        pygame.mixer.init()
        # Загрузка и воспроизведение аудиофайла
        pygame.mixer.music.load(random_audio_file)
        pygame.mixer.music.set_volume(volume_reduction_factor)  # Установка громкости
        pygame.mixer.music.play()

        # Ожидание завершения воспроизведения
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        logger.error(f"Ошибка при воспроизведении аудио: {e}")
        debug_logger.error(f"Ошибка при воспроизведении аудио: {e}")


def react_detail(file_path):
    """
    Воспроизводит указанный аудиофайл.
    :param file_path: Путь к аудиофайлу.
    """
    volume_reduction_factor = load_volume_assist()  # Загружаем из файла настроек значение громкости
    try:
        file_name = os.path.basename(file_path)[:-4]
        logger.info(f"Ответ ассистента: {file_name}")
        debug_logger.info(f"Ответ ассистента: {file_name}")

        pygame.mixer.init()
        # Остановить текущее воспроизведение
        pygame.mixer.music.stop()

        # Загрузка и воспроизведение аудиофайла
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(volume_reduction_factor)  # Установка громкости
        pygame.mixer.music.play()

        # Ожидание завершения воспроизведения
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        logger.error(f"Ошибка при воспроизведении аудио: {e}")
        debug_logger.error(f"Ошибка при воспроизведении аудио: {e}")

def thread_react(folder_path):
    """
    Запускает функцию react в отдельном потоке.
    :param folder_path: Путь к папке с аудиофайлами.
    """
    thread = threading.Thread(target=react, args=(folder_path,), daemon=True)
    thread.start()

def thread_react_detail(file_path):
    """
    Запускает функцию react в отдельном потоке.
    :param file_path: Путь к папке с аудиофайлами.
    """
    thread = threading.Thread(target=react_detail, args=(file_path,), daemon=True)
    thread.start()