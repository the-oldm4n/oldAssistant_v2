import os
from config import dev_mode
from path_builder import get_path, get_app_data_dir
from log_config import logger

class UserSessionManager:
    def __init__(self):
        self.username = None
        self.is_local = False

    def set_local_session(self):
        """Инициализация локальной сессии"""
        self.username = "local_storage"
        self.is_local = True

    def set_user_session(self, username: str):
        """Инициализация сессии зарегистрированного пользователя"""
        if username.lower() == "local_storage":
            raise ValueError("Имя 'local_storage' зарезервировано системой")
        self.username = username
        self.is_local = False
        logger.info(f"[SESSION] Сессия пользователя: {username}")

    def _get_base_dir(self) -> str:
        """Возвращает базовую директорию в зависимости от режима"""
        return get_path() if dev_mode else get_app_data_dir()

    def get_user_data_dir(self) -> str:
        """Возвращает путь к папке пользователя"""
        if not self.username:
            raise RuntimeError("Сессия не инициализирована")
        
        base_dir = self._get_base_dir()

        user_dir = os.path.join(base_dir, self.username)
        
        if not os.path.exists(user_dir):
            os.makedirs(user_dir, exist_ok=True)
            logger.info(f"[SESSION] Создана папка пользователя: {user_dir}")
            
        return user_dir

    def get_data_file_path(self, filename: str) -> str:
        """Возвращает полный путь к файлу данных (games.json / movies.json)"""
        return os.path.join(self.get_user_data_dir(), filename)

    def get_root_storage_dir(self) -> str:
        """
        Возвращает путь к 'корневому' хранилищу для миграции.
        В dev_mode это get_path() (корень проекта).
        В prod это get_app_data_dir() (папка AppData).
        """
        return self._get_base_dir()