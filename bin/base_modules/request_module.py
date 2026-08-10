import requests
from bin.base_modules.config_manager import get_config_value
from config import user_agent

app_version = get_config_value("app", "version", "1.0.0")
USER_AGENT = f"{user_agent}/Updater/v.{app_version}/"

session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT
})