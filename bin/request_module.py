import requests
from bin.config_manager import get_config_value


# Получаем версию из конфига
APP_VERSION = get_config_value("app", "version", "1.0.0")
USER_AGENT = f"OWLAPP/Updater/v.{APP_VERSION}/"

# Создаем сессию с кастомным User-Agent
session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT
})