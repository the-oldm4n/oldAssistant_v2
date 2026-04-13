import os
import sys
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QLabel
from log_config import debuglog
from path_builder import get_path

default_keywords_data = {
    "keywords_shutdown": ["питание", "комп", "компьютер", "выключи", "выключение"],
    "keywords_restart": ["перезагрузка", "рестарт", "перезапуск"],
    "keywords_search": ["найди", "поищи", "посмотри", "загугли", "найти"],
    "censored_list": ["сука", "сучка", "пизда", "ебаный", "ебать", "ёб твою мать", 
                    "ебаный рот", "нахуй", "хуй", "блять", "блядь", "ебучий", "епта",
                    "ёпта", "пидор", "пидорас", "пидар", "пиздюк",
                    "ебанутый", "ебарь", "ебанат", "еблан", "ебло", "уебок", "уебан",
                    "ебливый", "еблище", "заебись", "наебать", "объебать", "хуятина",
                    "подъебать", "разъебать", "съебать", "елдак", "шлюха", "нихуя"],
    "keywords_no": ["нет", "не", "отмена", "не надо", "стоп", "нельзя"],
    "keywords_yes": ["на", "да", "ага", "угу", "конечно", "давай", "го"],
    "keywords_reject": ["отмена", "отменить", "отмени", "сброс", "сбрось", "сбросить",
                        "остановить", "остановись", "останови", "стоп", "забудь"],
    "screen_list": ["скрин", "область", "выдели область", "скриншот"],
    "fullscreen_list": ["фулл скрин", "весь экран", "сфоткать"],
    "action_up": ["открыть", "включить", "запустить", "подключить"],
    "action_down": ["закрыть", "выключить", "отключить", "отрубить", "вырубить"],
    "keywords_player": ["плеер", "плейлист", "музыка", "проигрыватель",
                        "аудио", "песня", "трек", "трэк", "поставь"],
    "keywords_playpause": ["пауза", "пуск", "запуск", "включить", "врубить",
                            "отрубить", "выключить", "стоп", "продолжить", "плэй",
                            "включи", "выключи", "запусти", "отруби"],
    "keywords_next": ["некст", "следующий", "дальше", "вперед", "переключить"],
    "keywords_prev": ["бэк", "назад", "обратно", "предыдущий"]
}

font_digital = get_path("bin", "fonts", "Digital Numbers", "DigitalNumbers-Regular.ttf")
font_grape_nuts = get_path("bin", "fonts", "Grape_Nuts", "GrapeNuts-Regular.ttf")
font_cinzel_decorative = get_path("bin", "fonts", "Cinzel_Decorative", "CinzelDecorative-Regular.ttf")
font_michroma = get_path("bin", "fonts", "Michroma", "Michroma-Regular.ttf")
font_bruno_ace = get_path("bin", "fonts", "Bruno_Ace", "BrunoAce-Regular.ttf")
font_jacquard = get_path("bin", "fonts", "Jacquard_12", "Jacquard12-Regular.ttf")
font_nova_round = get_path("bin", "fonts", "Nova_Round", "NovaRound-Regular.ttf")
font_orbitron = get_path("bin", "fonts", "Orbitron", "static", "Orbitron-Regular.ttf")
font_special_elite = get_path("bin", "fonts", "Special_Elite", "SpecialElite-Regular.ttf")
font_metamorphous = get_path("bin", "fonts", "Metamorphous", "Metamorphous-Regular.ttf")

fonts_list = {
    "digital": font_digital,
    "grape_nuts": font_grape_nuts,
    "cinzel_decorative": font_cinzel_decorative,
    "michroma": font_michroma,
    "bruno_ace": font_bruno_ace,
    "nova_round": font_nova_round,
    "jacquard": font_jacquard,
    "orbitron": font_orbitron,
    "special_elite": font_special_elite,
    "metamorphous": font_metamorphous,
}

commands_list = {
    "ютуб": {
        "name": "www.youtube.com",
        "desc": "Ссылка www.youtube.com",
        "type": "url"
    },
    "микшер": {
        "name": "mixer",
        "desc": "Микшер",
        "type": "system"
    },
    "калькулятор": {
        "name": "calculator",
        "desc": "Калькулятор",
        "type": "system"
    },
    "пейнт": {
        "name": "paint",
        "desc": "Paint",
        "type": "system"
    },
    "пэйнт": {
        "name": "paint",
        "desc": "Paint",
        "type": "system"
    },
    "переменные": {
        "name": "environment",
        "desc": "Переменные среды",
        "type": "system"
    },
    "диспетчер": {
        "name": "task_manager",
        "desc": "Диспетчер задач",
        "type": "system"
    },
    "корзина": {
        "name": "recycler",
        "desc": "Корзина",
        "type": "system"
    },
    "ап дата": {
        "name": "appdata",
        "desc": "AppData",
        "type": "system"
    },
    "блютуз": {
        "name": "bluetooth",
        "desc": "Bluetooth",
        "type": "system"
    }
}

def get_audio_paths(speaker):
    """
    Функция для создания путей к аудиофайлам с учетом структуры после сборки
    :param speaker: Имя голоса
    :return: Словарь с путями к аудиофайлам и папкам
    """
    # Получаем базовый путь с учетом всех возможных вариантов
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS  # onefile режим
        else:
            base_path = os.path.dirname(sys.executable)
            # Проверяем наличие _internal
            if os.path.exists(os.path.join(base_path, '_internal')):
                base_path = os.path.join(base_path, '_internal')
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Формируем путь к папке с голосом
    voice_base = os.path.join(base_path, 'bin', 'speak_voice', speaker) if not getattr(sys, 'frozen',
                                                                                       False) else os.path.join(
        base_path, 'speak_voice', speaker)

    # Проверяем существование пути (на случай разных вариантов сборки)
    if not os.path.exists(voice_base):
        # Пробуем альтернативный вариант пути
        alt_path = os.path.join(base_path, 'bin', 'speak_voice', speaker) \
            if getattr(sys, 'frozen', False) else os.path.join(base_path, 'speak_voice', speaker)
        if os.path.exists(alt_path):
            voice_base = alt_path

    # Создаем все необходимые пути
    paths = {
        'what_folder': os.path.join(voice_base, 'what'),
        'start_folder': os.path.join(voice_base, 'start'),
        'approve_folder': os.path.join(voice_base, 'approve'),
        'close_folder': os.path.join(voice_base, 'close'),
        'start_greet_folder': os.path.join(voice_base, 'start_greet', 'other'),
        'greet_folder': os.path.join(voice_base, 'start_greet'),
        'other_folder': os.path.join(voice_base, 'other'),
        'echo_folder': os.path.join(voice_base, 'echo'),
        'close_assist_folder': os.path.join(voice_base, 'close_assist'),
        'player_folder': os.path.join(voice_base, 'player'),
        'censored_folder': os.path.join(voice_base, 'censored'),
        'confirm_folder': os.path.join(voice_base, 'cancel_confirm'),
        'start_script': os.path.join(voice_base, "start_script"),

        # Аудиофайлы
        'morning_greet': os.path.join(voice_base, 'start_greet', 'С добрым утром.ogg'),
        'evening_greet': os.path.join(voice_base, 'start_greet', 'Добрый вечер.ogg'),
        'error_file': os.path.join(voice_base, 'other', 'Произошла ошибка.ogg'),
        'off_file': os.path.join(voice_base, 'other', 'Отключаю питание.ogg'),
        'del_file': os.path.join(voice_base, 'other', 'Файл удален.ogg'),
        'restart_file': os.path.join(voice_base, 'other', 'Я ненадолго.ogg'),
        'wait_load_file': os.path.join(voice_base, 'other', 'Подожди, собираю данные о процессах.ogg'),
        'done_load_file': os.path.join(voice_base, 'other', 'Процессы записаны.ogg'),
        'start_rust': os.path.join(voice_base, 'other', 'Я в раст не пойду.ogg'),
        'prorok_sanboy': os.path.join(voice_base, 'other', 'Пророк санбой.ogg'),
        'update_button': os.path.join(voice_base, 'other', 'Еще не готово.ogg'),
        'what_command': os.path.join(voice_base, 'other', 'Не понял команду.ogg')
    }

    return paths

def setup_custom_font_label(text: str, font_style="Comfortaa", weight="Medium"):
    """
    Args:
        text (str): текст, который будет написан в выбранном стиле.
        font_style (str, optional): стиль шрифта. Defaults to "Comfortaa". Others: "Flatiron".
    """
    # Загрузка шрифта
    if font_style == "Flatiron":
        font_path = get_path("bin", "fonts", "Flatiron", "Flatiron Regular.otf")
    elif font_style == "Comfortaa":
        font_path = get_path("bin", "fonts", "Comfortaa", "static", "Comfortaa-Medium.ttf")
    else:
        font_path = get_path("bin", "fonts", "Flatiron", "Flatiron Regular.otf")
        
    if weight == "Thin":
        weight_type = QFont.Weight.Thin           # 100
    elif weight == "ExtraLight":
        weight_type = QFont.Weight.ExtraLight     # 200
    elif weight == "Light":
        weight_type = QFont.Weight.Light          # 300
    elif weight == "Normal":
        weight_type = QFont.Weight.Normal         # 400
    elif weight == "Medium":
        weight_type = QFont.Weight.Medium         # 500
    elif weight == "DemiBold":
        weight_type = QFont.Weight.DemiBold       # 600
    elif weight == "Bold":
        weight_type = QFont.Weight.Bold           # 700
    elif weight == "ExtraBold":
        weight_type = QFont.Weight.ExtraBold      # 800
    elif weight == "Black":
        weight_type = QFont.Weight.Black

        
    font_id = QFontDatabase.addApplicationFont(font_path)
    
    if font_id == -1:
        return None
    
    font_families = QFontDatabase.applicationFontFamilies(font_id)
    if not font_families:
        return None
    
    font_family = font_families[0]
    
    # Создание лейбла с кастомным шрифтом
    label = QLabel(text)
    custom_font = QFont(font_family, 30, weight_type)
    label.setFont(custom_font)
    
    return label

def setup_global_font(app, font_family="Open Sans", size=12, weight="Normal"):
    """Устанавливает шрифт для всего приложения"""
    # Словарь шрифтов с ПРАВИЛЬНЫМИ путями
    font_paths = {
        "Comfortaa": "Comfortaa/static/Comfortaa-Medium.ttf",
        "Open Sans": "Open_Sans/OpenSans-VariableFont_wdth,wght.ttf",
        "Anonymous Pro": "Anonymous_Pro/AnonymousPro-Regular.ttf"
    }
    
    # Загружаем ВСЕ шрифты при первом вызове
    if not hasattr(app, '_fonts_loaded'):
        loaded_families = {}
        for name, path in font_paths.items():
            font_path = get_path("bin", "fonts", *path.split('/'))
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    loaded_families[name] = families[0]  # Сохраняем реальное имя
                    debuglog.info(f"Загружен: {name} -> {families[0]}")
        app._loaded_font_families = loaded_families
        app._fonts_loaded = True
    
    # Маппинг весов
    weight_map = {
        "Light": 300, "Normal": 400, "Medium": 500, 
        "SemiBold": 600, "Bold": 700, "ExtraBold": 800
    }
    
    # Устанавливаем выбранный шрифт
    if font_family in app._loaded_font_families:
        real_family = app._loaded_font_families[font_family]
        font = QFont(real_family, size, weight_map.get(weight, 400))
        debuglog.info(f"Установлен: {real_family}, размер: {size}, вес: {weight}")
    else:
        font = QFont("Arial", size)
        debuglog.error(f"Шрифт {font_family} не найден, используется Arial")
    
    app.setFont(font)

