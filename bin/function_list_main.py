"""
Модуль с основными функциями: поиск в яндекс, выключение компа
"""
import json
import os
from datetime import datetime
from bin.lists import get_audio_paths
from log_config import logger, debuglog
import subprocess
import webbrowser
from bin.speak_functions import thread_react_detail, thread_react, react_detail
from path_builder import get_path, get_app_data_dir
from config import dev_mode

if dev_mode:
    settings_file = get_path('user_data', "settings.json")

else:
    settings_file =  os.path.join(get_app_data_dir(), 'user_data', 'settings.json')

def load_settings():
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings
        except json.JSONDecodeError:
            debuglog.error(f"Ошибка: файл {settings_file} содержит некорректный JSON.")
    else:
        debuglog.error(f"Файл настроек {settings_file} не найден.")

def get_current_speaker():
    settings = load_settings()
    return settings.get("voice", "johnny")

def search_yandex(command, name=None, name_2=None, name_3=None):
    """
    Поиск в инете по запросу
    :param name: имя ассистента
    :param name_2: доп. имя
    :param name_3: доп. имя
    :param command: сырая команда
    """
    exclude_words = [word for word in [name, name_2, name_3] if word is not None and word.strip()]
    exclude_list = ["в инете", "в интернете", "в браузере", "найди", "поищи", "посмотри", "гугли"]

    for phrase in exclude_list:
        command = command.replace(phrase, "")

    words = command.split()

    for i, word in enumerate(words):
        if any(ex_word in word.lower() for ex_word in exclude_words):
            words.pop(i)  # Удаляем только первое совпадение
            break  # Выходим из цикла после удаления

    query = ' '.join(words)
    url = f"https://www.ya.ru/search?text={query}"
    debuglog.info(f"Поиск по значению: {query}")
    webbrowser.open(url)

def shutdown_windows(react=True):
    """
    Выключение компа
    """
    if react:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        react_detail(audio_paths['off_file'])
    subprocess.run(["shutdown", "/s", "/t", "0"])

def restart_windows(react=True):
    """
    Рестарт компа
    """
    if react:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        react_detail(audio_paths['off_file'])
    subprocess.run(["shutdown", "/r", "/t", "0"])

def open_volume_mixer(react=True):
    """ Открывает микшер виндовс """
    try:
        subprocess.Popen(["sndvol.exe", "/R"])
        debuglog.info("Микшер громкости открыт")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при открытии микшера громкости: {e}", exc_info=True)
        debuglog.error(f"Ошибка при открытии микшера громкости: {e}", exc_info=True)

def close_volume_mixer(react=True):
    """ Открывает микшер виндовс """
    try:
        result = subprocess.run(['taskkill', '/IM', 'sndvol.exe', '/F'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding='cp866',
                                check=True)
        debuglog.info("Микшер громкости закрыт")
        debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при закрытии микшера громкости: {e}", exc_info=True)
        debuglog.error(f"Ошибка при закрытии микшера громкости: {e}", exc_info=True)
def open_calc(react=True):
    """ Открывает калькулятор """
    try:
        subprocess.Popen(["calc.exe", "/R"])
        debuglog.info("Калькулятор открыт")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при открытии калькулятора {e}", exc_info=True)
        debuglog.error(f"Ошибка при открытии калькулятора {e}", exc_info=True)

def close_calc(react=True):
    """ Закрывает калькулятор """
    try:
        result = subprocess.run(['taskkill', '/IM', 'CalculatorApp.exe', '/F'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding='cp866',
                                check=True)
        debuglog.info(f"Процесс успешно завершен.")
        debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка: {e}")
        debuglog.error(f"Ошибка: {e}")

def open_paint(react=True):
    """ Открывает paint """
    try:
        subprocess.Popen("mspaint.exe")
        debuglog.info("Paint открыт")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при открытии paint {e}", exc_info=True)
        debuglog.error(f"Ошибка при открытии paint {e}", exc_info=True)

def close_paint(react=True):
    """ Закрывает paint """
    try:
        result = subprocess.run(['taskkill', '/IM', 'mspaint.exe', '/F'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding='cp866',
                                check=True)
        debuglog.info(f"Пейнт закрыт.")
        debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка: {e}")
        debuglog.error(f"Ошибка: {e}")

def open_path(react=True):
    try:
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
        subprocess.Popen("rundll32 sysdm.cpl,EditEnvironmentVariables")
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка {e}", exc_info=True)
        debuglog.error(f"Ошибка {e}", exc_info=True)

def greeting():
    current_hour = datetime.now().hour

    speaker = get_current_speaker()
    audio_paths = get_audio_paths(speaker)

    if 4 <= current_hour < 11:
        thread_react_detail(audio_paths['morning_greet'])
    elif 11 <= current_hour < 18:
        thread_react(audio_paths['start_greet_folder'])
    else:
        thread_react_detail(audio_paths['evening_greet'])

def open_taskmgr(react=True):
    """ Открывает Диспетчер задач """
    try:
        subprocess.Popen("taskmgr.exe")
        debuglog.info("Диспетчер задач открыт")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка: {e}", exc_info=True)
        debuglog.error(f"Ошибка: {e}", exc_info=True)

def close_taskmgr(react=True):
    """ Закрывает Диспетчер задач """
    try:
        result = subprocess.run(['taskkill', '/IM', 'taskmgr.exe', '/F'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding='cp866',
                                check=True)
        debuglog.info(f"Диспетчер задач закрыт")
        debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка: {e}")
        debuglog.error(f"Ошибка: {e}")

def open_recycle_bin(react=True):
    """Открывает корзину"""
    try:
        # Используем explorer для открытия корзины
        subprocess.Popen('explorer.exe shell:RecycleBinFolder')
        debuglog.info("Корзина открыта")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при открытии корзины: {e}", exc_info=True)
        debuglog.error(f"Ошибка при открытии корзины: {e}", exc_info=True)

def close_recycle_bin(react=True):
    """Закрывает все окна корзины"""
    try:
        # Закрываем все окна с заголовком "Корзина" (может отличаться в разных языковых версиях)
        result = subprocess.run(['taskkill', '/FI', 'WINDOWTITLE eq Корзина*', '/F'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding='cp866',
                                check=True)
        debuglog.info("Корзина закрыта")
        debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при закрытии корзины: {e}")
        debuglog.error(f"Ошибка при закрытии корзины: {e}")

def open_appdata(react=True):
    """Открывает папку %appdata% (AppData/Roaming)"""
    try:
        # Полный путь к папке AppData/Roaming
        appdata_path = os.path.expandvars('%APPDATA%')

        # Открываем в проводнике
        subprocess.Popen(f'explorer "{appdata_path}"')

        debuglog.info("Папка %appdata% открыта")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths.get('start_folder'))
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при открытии %appdata%: {e}", exc_info=True)
        debuglog.error(f"Ошибка при открытии %appdata%: {e}", exc_info=True)


def close_appdata(react=True):
    """Закрывает все окна проводника в папке %appdata%"""
    try:
        title_list = ['Roaming', 'AppData']
        for title in title_list:
            # Закрываем все окна проводника, открытые в этой папке
            result = subprocess.run(['taskkill', '/FI', f'WINDOWTITLE eq {title}*', '/F'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    encoding='cp866',
                                    check=True)

            debuglog.info("Папка %appdata% закрыта")
            debuglog.info(f"Вывод subprocess:{result.stdout.strip()}. Ошибки:{result.stderr.strip()}")
        if react:
            speaker = get_current_speaker()
            audio_paths = get_audio_paths(speaker)
            thread_react(audio_paths['close_folder'])
    except Exception as e:
        speaker = get_current_speaker()
        audio_paths = get_audio_paths(speaker)
        error_file = audio_paths.get('error_file')
        thread_react_detail(error_file)
        logger.error(f"Ошибка при закрытии %appdata%: {e}")
        debuglog.error(f"Ошибка при закрытии %appdata%: {e}")