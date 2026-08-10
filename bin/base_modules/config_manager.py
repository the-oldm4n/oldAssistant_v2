import configparser
import os
from pathlib import Path
from path_builder import get_app_data_dir, get_path
from config import dev_mode, app_name

if dev_mode:
    config_path = get_path("config.ini")
else:
    config_path = os.path.join(get_app_data_dir(), "config.ini")


def get_config_value(section, key, default=None, base_path=config_path):
    """Получение конкретного значения из конфига"""
    if not os.path.exists(base_path):
        config = load_default_config(base_path)
    else:
        config = configparser.ConfigParser()
        config.read(base_path, encoding='utf-8')

    if not config.has_section(section) or not config.has_option(section, key):
        return default
    
    return config.get(section, key, fallback=default)


def set_config_value(section, key, value):
    """Обновление значения в конфиге"""
    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
    else:
        config = load_default_config(config_path)

    if not config.has_section(section):
        config.add_section(section)

    if isinstance(value, bool):
        value = str(value)
    
    config.set(section, key, str(value))

    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)


def load_default_config(config_path):
    """
    Создает конфигурационный файл с настройками по умолчанию
    Возвращает объект configparser с загруженными настройками
    """
    config = configparser.ConfigParser()

    config['app'] = {
        'version': '0.0.0',
        'name': app_name,
        'build': 'prod'
    }

    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

    return config


def update_version(version_str: str):
    numbers = version_str.split('-')[0].split('.')
    major = numbers[0]
    minor = numbers[1] if len(numbers) > 1 else '0'
    patch = numbers[2] if len(numbers) > 2 else '0'

    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [StringStruct('FileVersion', '{major}.{minor}.{patch}.0'),
          StringStruct('ProductVersion', '{version_str}')]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [0x409, 1200])])
  ]
)"""

    with open(get_path('version.txt'), 'w', encoding='utf-8') as f:
        f.write(content)