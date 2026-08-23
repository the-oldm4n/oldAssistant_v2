import uuid
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QLabel
from log_config import assist_log
from path_builder import get_path

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
                    assist_log.info(f"Загружен: {name} -> {families[0]}")
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
        assist_log.info(f"Установлен: {real_family}, размер: {size}, вес: {weight}")
    else:
        font = QFont("Arial", size)
        assist_log.error(f"Шрифт {font_family} не найден, используется Arial")
    
    app.setFont(font)
