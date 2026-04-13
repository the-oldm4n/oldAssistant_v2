import configparser
import os
from pathlib import Path
from path_builder import get_path, get_app_data_dir
from config import dev_mode

if dev_mode:
    config_file = get_path("config.ini")
else:
    config_file = os.path.join(get_app_data_dir(), "config.ini")


def get_config_value(section, key, default=None):
    """Получение конкретного значения из конфига"""
    config_path = Path(config_file)

    if not config_path.exists():
        config = load_default_config(config_path)
    else:
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')

    return config.get(section, key, fallback=default)


def set_config_value(section, key, value):
    """Обновление значения в конфиге"""
    config_path = Path(config_file)

    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
    else:
        config = load_default_config(config_path)

    if not config.has_section(section):
        config.add_section(section)

    config.set(section, key, str(value) if value is not None else "")

    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)


def load_default_config(config_path):
    """
    Создает конфигурационный файл с настройками по умолчанию
    Возвращает объект configparser с загруженными настройками
    """
    config = configparser.ConfigParser()

    # Настройки по умолчанию
    config['app'] = {
        'version': '0.0.0',
        'name': 'Voxodium',
        'build': 'prod',
        'basepath': os.path.dirname(config_path)
    }

    # Создаем директорию если её нет
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Сохраняем конфиг в файл
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