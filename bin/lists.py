import os
import sys
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from logging_config import debug_logger
from path_builder import get_path

default_keywords_data = {
    "keywords_shutdown": ["питание", "комп", "компьютер", "выключи", "выключение"],
    "keywords_restart": ["перезагрузка", "рестарт", "перезапуск"],
    "keywords_search": ["найди", "поищи", "посмотри", "загугли", "найти"],
    "censored_list": ["сука", "сучка", "пизда", "ебаный", "ебать", "ёб твою мать", 
    "ебаный рот", "нахуй", "хуй", "блять", "блядь", "ебучий", "епта",
    "ёпта" , "пидор" , "пидорас", "пидар", "пиздюк",
    "ебанутый", "ебарь", "ебанат", "еблан", "ебло", "уебок", "уебан",
    "ебливый", "еблище", "заебись", "наебать", "объебать", "хуятина",
    "подъебать", "разъебать", "съебать", "елдак", "шлюха", "нихуя"],
    "keywords_no": ["нет", "не", "no", "отмена", "не надо", "стоп", "нельзя"],
    "keywords_yes": ["на", "да", "ага", "угу", "yes", "конечно", "давай", "го"],
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

help_data = {
    "name_label": {
        "title": "Основное имя ассистента",
        "description": "Основа команды",
        "usage": "Реагирует на указанное имя. Укажите любое слово, которое распознается через микрофон, без спец. символов и цифр."
    },
    "name2_label": {
        "title": "Дополнительное имя ассистента",
        "description": "Дополнительная вариация для основного имени",
        "usage": "Также реагирует на указанное имя. Укажите любое слово, которое распознается через микрофон, без спец. символов и цифр."
    },
    "voice_label": {
        "title": "Голос озвучки ассистента",
        "description": "Выберите, каким голосом будет говорить ассистент",
        "usage": "Выберите любой вариант из списка и голос автоматически применится. Протестируйте, нажав на кнопку ниже."
    },
    "volume_label": {
        "title": "Громкость ассистента",
        "description": "Тонкая регулировка громкости.",
        "usage": "Настройка применяется автоматически."
    },
    "steam_label": {
        "title": "Путь до файла steam.exe",
        "description": "Указание пути до steam.exe необходимо для корректного запуска ярлыков, которые работают через стим.",
        "usage": ""
    },
    "default_btn": {
        "title": "По умолчанию",
        "description": "Сброс до стандартных настроек.",
        "usage": "ВНИМАНИЕ! Сброс происходит СРАЗУ после нажатия на кнопку."
    },
    "censor_check": {
        "title": "Реагировать на мат",
        "description": "Воспроизводить ли реакцию ассистента, если он распознает нецензурную брань.",
        "usage": "Вкл. по умолчанию."
    },
    "correct_command_check": {
        "title": "Запоминать предыдущую команду",
        "description": "Запоминание предыдущей команды позволяет не говорить всю фразу заново, "
                        "а только саму команду.(Пример: 'Джонни открой ...' Здесь бот не понял конкретно команду, "
                        "но он запомнил то, что его упомянули и действие для команды. Теперь будет достаточно произнести "
                        "только саму команду для запуска действия. 'Калькулятор' и бот автоматически восстановит предыдущую "
                        "команду 'Джонни открой ' и подставит 'Калькулятор').",
        "usage": "Если у вас возникают ложные срабатывания, либо функция кажется неудобной, то выключите ее. "
        "Количество попыток неограничено, режим прослушивания повтора отключится автоматически, если не получает данные на входе "
        "в течение 10 секунд"
    },
    "update_check": {
        "title": "Запуск утилиты обновления",
        "description": "Проверка обновления перед запуском основной программы.",
        "usage": "Вкл. по умолчанию."
    },
    "start_win_check": {
        "title": "Запуск с Windows",
        "description": "Автозапуск с системой.",
        "usage": "Вкл. по умолчанию."
    },
    "minimize_check": {
        "title": "Запуск в трей",
        "description": "Программа запускается и сворачивается в трей.",
        "usage": "Выкл. по умолчанию."
    },
    "widget_check": {
        "title": "Открывать виджет",
        "description": "Запуск виджета при включении программы.",
        "usage": "Вкл. по умолчанию."
    },
    "keep_watch_check": {
        "title": "Расширенная обработка команд",
        "description": "Позволяет давать команду ассистенту без упоминания его имени.",
        "usage": "ВНИМАНИЕ! Повышается вероятность случайного срабатывания. Распознанная команда обрабатывается "
        "через подтверждение (Да/Нет)."
    },
    "snow_check": {
        "title": "Снегопад",
        "description": "Регулировка состояния.",
        "usage": ""
    },
    "garland_check": {
        "title": "Гирлянда",
        "description": "Регулировка состояния.",
        "usage": "В заголовке есть кнопка для переключения режимов гирлянды."
    },
    "add_link_btn": {
        "title": "Добавить ярлык",
        "description": "Создание ярлыка на рабочем столе.",
        "usage": ""
    },
    "label_input": {
        "title": "Устройство ввода",
        "description": "Выбор устройства для обработки голоса в текст.",
        "usage": "При первом запуске берется значение по умолчанию в системе."
    },
    "list_selector": {
        "title": "Список хук-слов",
        "description": "Группы основных списков слов/фраз, которые используются в обработке команд. Можно добавлять новые слова"
        "в любой группе, а также изменять уже существующие. Полезно ознакомиться, чтобы понимать какие ключевые слова отвечают "
        "за тот или иной функционал.",
        "usage": "Сброс списков к стандартным значениям откатит внесенные изменения."
    },
    "words_list": {
        "title": "Список хук-слов",
        "description": "Список слов в определенной группе.",
        "usage": "ПКМ по элементу списка для вызова контекстного меню."
    },
    "reset_words_list": {
        "title": "Сброс списков к значениям по умолчанию",
        "description": "Сброс происходит после подтверждения.",
        "usage": ""
    },
    "style_widget": {
        "title": "Стилизация интерфейса",
        "description": "Здесь можно выбрать стили из предложенных, применить созданные ранее стили, а также создать свой "
        "особый стиль.",
        "usage": "Видео по созданию собственных стилей во вкладке 'Гайды'."
    },
    "drag_toggle_btn": {
        "title": "Кастомизация виджета",
        "description": "Укажите необходимые значки, которые будут располагаться на виджете. Можно изменить порядок, нажав на "
        "кнопку и перетаскивая в удобном порядке.",
        "usage": "После настройки, нажмите Применить."
    },
    "snow_panel_checkbox": {
        "title": "Снегопад на виджете",
        "description": "Переключатель снегопада на виджете.",
        "usage": "Вкл. по умолчанию."
    },
    "font_combo": {
        "title": "Стилизация часов",
        "description": "Доступно несколько стилей для часов на виджете.",
        "usage": "После настройки, нажмите Применить."
    },
    "btn_shortcut": {
        "title": "Создание команды для ярлыка",
        "description": "Можно создать команду, используя следующие типы ярлыков: стандартный, steam-ярлык, а также ярлыки от "
        "Epic Games.",
        "usage": "Исполняемые файлы не поддерживаются для запуска. Сделайте отдельный ярлык исполняемого файла."
    },
    "btn_folder": {
        "title": "Создание команды для папки",
        "description": "Создание команды, которая будет привязана к определенной папке.",
        "usage": "Путь можно указать к абсолютно любой папке."
    },
    "btn_url": {
        "title": "Создание команды для url-ссылки",
        "description": "Команда для запуска браузера (если он закрыт) и открытия указанной ссылки.",
        "usage": "Например команда 'ютуб' с ссылкой на сайт встроена по умолчанию."
    },
    "search_btn": {
        "title": "Автопоиск ярлыков",
        "description": "Поиск и копирование ярлыков в папку ассистента с рабочего стола, а также меню Пуск.",
        "usage": "Полезно, если хотите добавить много ярлыков разом и они есть как минимум на рабочем столе."
    },
    "key_input_app": {
        "title": "Новая команда",
        "description": "Слово или короткая фраза, которая легко распознается ботом.",
        "usage": "Попробуйте сказать нужную фразу и сверьте распознанный вариант в окне логов."
    },
    "label_link_app": {
        "title": "Выбор ярлыка",
        "description": "Выберите из выпадающего списка название ярлыка. Можно ввести название нужного "
        "ярлыка для быстрого поиска.",
        "usage": "Попробуйте сказать нужную фразу и сверьте распознанный вариант в окне логов."
    },
    "label_folder": {
        "title": "Выбор папки",
        "description": "Выберите папку через кнопку 'Обзор', либо можете написать вручную.",
        "usage": ""
    },
    "url_path": {
        "title": "Выбор url-ссылки",
        "description": "Укажите правильную ссылку на желаемый сайт.",
        "usage": ""
    },
    "commands_list": {
        "title": "Добавленные команды",
        "description": "Здесь отображается список созданных вами команд.",
        "usage": "ПКМ по элементу списка для вызова контекстного меню. В меню находятся следующие пункты: "
        "редактирование и удаление команды."
    },
    "process_widget_info": {
        "title": "Процессы ярлыков",
        "description": "Список процессов, которые принадлежат определенному ярлыку. Создается при первом запуске "
        "ярлыка через бота (голосовой командой).",
        "usage": "Во время первого запуска бот ищет процессы в течение 40 секунд, которые запустились сразу после "
        "запуска ярлыка и сохраняет их для дальнейшего использования. Закрытие программы происходит за счет закрытия процессов, "
        "которые бот сохранил."
    },
    "links_list": {
        "title": "Список ярлыков",
        "description": "Список ярлыков, для которых сохранены какие-либо процессы.",
        "usage": ""
    },
    "processes_list": {
        "title": "Список процессов",
        "description": "Здесь отображается список процессов, найденных ботом при первом запуске ярлыка.",
        "usage": "Вы можете добавить или удалить процессы с помощью кнопок ниже."
    },
    "censor_conter_widget": {
        "title": "Счетчик нецензурных слов",
        "description": "Статистика произнесенных (либо ложно засчитанных ботом) матерных слов.",
        "usage": "Учет ведется независимо от состояния чекбокса 'Реагировать на мат' в настройках. "
        "Для сброса счетчика требуется подтверждение."
    },
    "check_button_update": {
        "title": "Запуск проверки обновления",
        "description": "Ручная проверка наличия обновлений на сервере.",
        "usage": "Проверяет последнюю стабильную версию и сравнивает с текущей версией программы."
    },
    "check_exp_update": {
        "title": "Чекбокс 'Проверка бета-версий'",
        "description": "При включенном режиме: Во время ручной проверки обновлений ищет самую свежую версию, "
        "включая экспериментальные.",
        "usage": ""
    },
    "rollback_version": {
        "title": "Откат до стабильной версии",
        "description": "Производит полное скачивание и установку свежей стабильной версии, независимо от текущей. "
        "Полезно, если у вас замечаются проблемы с приложением, связанные с нехваткой файлов.",
        "usage": "Откат требует подтверждения. После подтверждения будет автоматически произведено скачивание и установка "
        "с сохранением пользовательских данных (кастомные команды, и др.)."
    },
    "open_log_folder": {
        "title": "Открыть папку с подробными логами",
        "description": "В папке содержится файл с debug-логами для отладки.",
        "usage": "Этот файл можно направить разработчику в случае непредвиденной ошибки.."
    },
    "open_log_file": {
        "title": "Посмотреть логи",
        "description": "Открывается окно, где будет выведено последние 1000 строк из файла debug-лога.",
        "usage": "Сделано для удобства просмотра свежих сведений и отладки."
    },
    "": {
        "title": "",
        "description": "",
        "usage": ""
    }
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
    "ютуб": "www.youtube.com"
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
                    debug_logger.info(f"Загружен: {name} -> {families[0]}")
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
        debug_logger.info(f"Установлен: {real_family}, размер: {size}, вес: {weight}")
    else:
        font = QFont("Arial", size)
        debug_logger.error(f"Шрифт {font_family} не найден, используется Arial")
    
    app.setFont(font)

