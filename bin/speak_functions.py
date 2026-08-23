import json
import os
import random
import threading
from log_config import assist_log, logger

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from path_builder import get_path, get_app_data_dir
from config import dev_mode

if dev_mode:
    settings_file = get_path('user_data', "settings.json")

else:
    settings_file =  os.path.join(get_app_data_dir(), 'user_data', 'settings.json')


def load_volume_assist():
    settings_file_path = settings_file
    if os.path.exists(settings_file_path):
        try:
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get('volume_assist', 0.2)  # Возвращаем значение по умолчанию, если ключ отсутствует
        except json.JSONDecodeError:
            assist_log.error(f"Ошибка: файл {settings_file_path} содержит некорректный JSON.")
            logger.error(f"Ошибка: файл {settings_file_path} содержит некорректный JSON.")
    else:
        assist_log.error(f"Файл настроек {settings_file_path} не найден.")
        logger.error(f"Файл настроек {settings_file_path} не найден.")
    return 0.2

def react(folder_path, trace):
    """
    Воспроизводит случайный аудиофайл из указанной папки.
    :param trace: для контекста, чтобы отследить вызов
    :param folder_path: Путь к папке с аудиофайлами.
    """
    volume_reduction_factor = load_volume_assist()  # Загружаем из файла настроек значение громкости
    try:
        # Получение списка файлов в папке
        audio_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.ogg')]

        if not audio_files:
            assist_log.info(f"В папке {folder_path} нет аудиофайлов.")
            logger.info(f"В папке {folder_path} нет аудиофайлов.")
            return

        # Выбор случайного файла
        random_audio_file = random.choice(audio_files)
        random_filename = os.path.basename(random_audio_file)[:-4]
        assist_log.info(f"Ответ ассистента: {random_filename}")
        logger.info(f"Ответ ассистента: {random_filename}. Traceback: {trace}")

        pygame.mixer.init()
        # Загрузка и воспроизведение аудиофайла
        pygame.mixer.music.load(random_audio_file)
        pygame.mixer.music.set_volume(volume_reduction_factor)  # Установка громкости
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        assist_log.error(f"Ошибка при воспроизведении аудио: {e}")
        logger.error(f"Ошибка при воспроизведении аудио: {e}")


def react_detail(file_path, trace=""):
    """
    Воспроизводит указанный аудиофайл.
    :param trace: для контекста, чтобы отследить вызов
    :param file_path: Путь к аудиофайлу.
    """
    volume_reduction_factor = load_volume_assist()  # Загружаем из файла настроек значение громкости
    try:
        file_name = os.path.basename(file_path)[:-4]
        assist_log.info(f"Ответ ассистента: {file_name}")
        logger.info(f"Ответ ассистента: {file_name}. Traceback: {trace}")

        pygame.mixer.init()
        # Остановить текущее воспроизведение
        pygame.mixer.music.stop()

        # Загрузка и воспроизведение аудиофайла
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(volume_reduction_factor)  # Установка громкости
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        assist_log.error(f"Ошибка при воспроизведении аудио: {e}")
        logger.error(f"Ошибка при воспроизведении аудио: {e}")

def thread_react(folder_path, trace=""):
    """
    Запускает функцию react в отдельном потоке.
    :param trace: можно передать метод или место из которого вызывается
    :param folder_path: Путь к папке с аудиофайлами.
    """
    thread = threading.Thread(target=react, args=(folder_path, trace), daemon=True)
    thread.start()

def thread_react_detail(file_path, trace=""):
    """
    Запускает функцию react в отдельном потоке.
    :param trace: можно передать метод или место из которого вызывается
    :param file_path: Путь к папке с аудиофайлами.
    """
    thread = threading.Thread(target=react_detail, args=(file_path, trace), daemon=True)
    thread.start()

def play_sound(type_sound):
    ok_path = get_path("bin", "speak_voice", "sounds", "ok.wav")
    error_path = get_path("bin", "speak_voice", "sounds", "error.wav")
    what_path = get_path("bin", "speak_voice", "sounds", "what.wav")
    try:
        if type_sound == "ok":
            file_path = ok_path
        elif type_sound == "what":
            file_path = what_path
        else:
            file_path = error_path

        pygame.mixer.init()
        # Остановить текущее воспроизведение
        pygame.mixer.music.stop()

        # Загрузка и воспроизведение аудиофайла
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(0.3)  # Установка громкости
        pygame.mixer.music.play()

    except Exception as e:
        assist_log.error(f"Ошибка при воспроизведении аудио: {e}")
        logger.error(f"Ошибка при воспроизведении аудио: {e}")
        
def thread_play_sound(type_sound):
    thread = threading.Thread(target=play_sound, args=(type_sound,), daemon=True)
    thread.start()
