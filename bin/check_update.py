import os
import re
from typing import Tuple, Optional, Dict
import requests
from PySide6.QtCore import Signal, QObject, QRunnable, Slot
from bin.request_module import session

from log_config import debuglog
from path_builder import get_app_data_dir
from config import domain, path_name, update_name


class VersionCheckSignals(QObject):
    """Сигналы для QRunnable (т.к. QRunnable не наследует QObject)"""
    version_checked = Signal(str, str)
    check_failed = Signal()

class VersionCheckThread(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = VersionCheckSignals()
    
    @Slot()
    def run(self):
        """Это выполнится в отдельном потоке из пула"""
        try:
            response = session.get(f"{domain}/{path_name}/version", timeout=5)
            if response.status_code == 200:
                data = response.json()
                stable = data.get("stable", {}).get("version", "")
                exp = data.get("experimental", {}).get("exp_version", "")
                self.signals.version_checked.emit(stable, exp)
            else:
                self.signals.check_failed.emit()
        except Exception as e:
            debuglog.error(f"Version check error: {e}")
            self.signals.check_failed.emit()

def check_version():
    try:
        version_url = f"{domain}/{path_name}/version"
        response = session.get(version_url, timeout=5)  # Добавляем таймаут

        if response.status_code == 200:
            data = response.json()

            stable_data = data.get("stable", {}) or {}
            experimental_data = data.get("experimental", {}) or {}

            version = stable_data.get("version")
            exp_version = experimental_data.get("exp_version")

            if version:
                debuglog.info(f"Последняя стабильная версия: {version}")
            if exp_version:
                debuglog.info(f"Экспериментальная версия: {exp_version}")

            return version, exp_version
        else:
            debuglog.error(f"Ошибка сервера: {response.status_code}")
            return None, None

    except requests.exceptions.RequestException as e:
        debuglog.error(f"Ошибка соединения: {str(e)}")
        return None, None


def check_all_versions() -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Получает все версии с сервера
    Возвращает кортеж: (стабильные_версии, экспериментальные_версии)
    """
    try:
        versions_url = f"{domain}/{path_name}/versions"

        response = session.get(versions_url, timeout=5)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("Некорректный формат ответа сервера")

        stable_versions = data.get("stable", [])
        experimental_versions = data.get("experimental", [])

        if not isinstance(stable_versions, list):
            stable_versions = []
        if not isinstance(experimental_versions, list):
            experimental_versions = []

        debuglog.info(f"Получено стабильных версий: {len(stable_versions)}")
        debuglog.info(f"Получено экспериментальных версий: {len(experimental_versions)}")

        return stable_versions, experimental_versions

    except requests.exceptions.RequestException as e:
        debuglog.error(f"Ошибка соединения: {str(e)}")
        return None, None
    except ValueError as e:
        debuglog.error(f"Ошибка формата данных: {str(e)}")
        return None, None
    except Exception as e:
        debuglog.error(f"Неожиданная ошибка: {str(e)}")
        return None, None

def load_changelog(changelog_path):
    download_url = f"{domain}/{path_name}/getchangelog"
    try:
        os.makedirs(os.path.dirname(changelog_path), exist_ok=True)

        with session.get(download_url, stream=True) as response:
            response.raise_for_status()

            with open(changelog_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        debuglog.debug(f"Changelog успешно сохранен в: {changelog_path}")
        return True

    except requests.exceptions.RequestException as e:
        debuglog.error(f"Ошибка при загрузке changelog: {str(e)}")
        return False

def get_filename_from_cd(cd):
    """Получение имени файла из Content-Disposition"""
    if not cd:
        return None
    match = re.search(r'filename="?([^"]+)"?', cd)
    return match.group(1) if match else None

def download_update(type_version, on_complete=None, version=None):
    """Загрузка файла с сохранением оригинального имени, очисткой старых версий и обработкой прерываний"""
    if type_version not in ["stable", "exp"]:
        debuglog.error("Недопустимый тип версии")
        return None

    download_url = None
    temp_suffix = ".tempdownload"
    file_path = None
    temp_file_path = None

    if version is None:
        download_url = f"{domain}/{path_name}/download/{type_version}"
    else:
        download_url = f"{domain}/{path_name}/load/{type_version}/{version}"

    try:
        download_dir = os.path.join(get_app_data_dir(), "update")
        os.makedirs(download_dir, exist_ok=True)

        with session.head(download_url, allow_redirects=True) as r:
            r.raise_for_status()
            content_disposition = r.headers.get('Content-Disposition')
            filename = update_name

        file_path = os.path.join(download_dir, filename)
        temp_file_path = file_path + temp_suffix

        if os.path.exists(file_path):
            debuglog.info(f"Файл уже существует: {file_path}")
            if callable(on_complete):
                on_complete(file_path, success=True, skipped=True)
            return file_path

        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        debuglog.info(f"Начинаю загрузку: {filename}")
        with session.get(download_url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()

            total_size = int(r.headers.get('content-length', 0))

            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        if os.path.getsize(temp_file_path) == total_size or total_size == 0:
            os.rename(temp_file_path, file_path)
            debuglog.info(f"Файл успешно загружен: {file_path}")

            if callable(on_complete):
                on_complete(file_path, success=True, skipped=False)
            return file_path
        else:
            raise Exception("Размер скачанного файла не соответствует ожидаемому")

    except (requests.exceptions.RequestException, Exception) as e:
        error_msg = f"Ошибка при загрузке: {str(e)}"
        debuglog.error(error_msg, exc_info=True)

        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                debuglog.info(f"Удален неполный файл: {temp_file_path}")
            except Exception as cleanup_error:
                debuglog.error(f"Ошибка при удалении временного файла: {str(cleanup_error)}")

        if callable(on_complete):
            on_complete(None, success=False, error=error_msg)
        return None