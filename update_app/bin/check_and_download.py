import os
import re
import requests
from PySide6.QtCore import QThread, Signal, QObject, QRunnable, Slot
from utils import get_app_data_dir
from log_config import logger
from config import domain, session, update_name, prefix_url


class VersionCheckSignals(QObject):
    """Сигналы для QRunnable (т.к. QRunnable не наследует QObject)"""
    version_checked = Signal(str)
    check_failed = Signal()


class VersionCheckThread(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = VersionCheckSignals()
    
    @Slot()
    def run(self):
        """Это выполнится в отдельном потоке из пула"""
        try:
            response = session.get(f"{domain}/{prefix_url}/version", timeout=5)
            stable_version = None
            
            if response.status_code == 200:
                data = response.json()
                stable = data.get("stable")
                
                if isinstance(stable, dict):
                    stable_version = stable.get('version', '').strip()
                elif isinstance(stable, str):
                    stable_version = stable.strip()
                else:
                    stable_version = str(stable).strip() if stable else ''
            
            if not stable_version:
                logger.warning("Stable version is empty or not found")
                self.signals.check_failed.emit()
            else:
                self.signals.version_checked.emit(stable_version)
                
        except Exception as e:
            logger.error(f"Version check error: {e}")
            self.signals.check_failed.emit()

def check_version():
    try:
        version_url = f"{domain}/{prefix_url}/version"
        response = session.get(version_url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            stable_data = data.get("stable", {}) or {}
            version = stable_data.get("version")

            if version:
                logger.info(f"Последняя стабильная версия: {version}")

            return version
        else:
            logger.error(f"Ошибка сервера: {response.status_code}")
            return None, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения: {str(e)}")
        return None, None


class DownloadThread(QThread):
    download_complete = Signal(str, bool, bool, str)  # file_path, success, skipped, error
    download_progress = Signal(int)

    def __init__(self, type_version, version=None, parent=None):
        super().__init__(parent)
        self.type_version = type_version
        self.version = version

    def run(self):
        download_update(
            type_version=self.type_version,
            on_complete=self._handle_complete,
            on_progress=self._handle_progress,
            version=self.version)

    def _handle_complete(self, file_path, success=True, skipped=False, error=None):
        self.download_complete.emit(file_path, success, skipped, error)

    def _handle_progress(self, progress_percent):
        self.download_progress.emit(progress_percent)

def get_filename_from_cd(cd):
    """Получение имени файла из Content-Disposition"""
    if not cd:
        return None
    match = re.search(r'filename="?([^"]+)"?', cd)
    return match.group(1) if match else None


def download_update(type_version, on_complete=None, on_progress=None, version=None):
    """Загрузка файла с сохранением оригинального имени, очисткой старых версий и обработкой прерываний"""
    if type_version not in ["stable"]:
        logger.error("Недопустимый тип версии")
        return None

    download_url = None
    temp_suffix = ".tempdownload"  # Суффикс для временных файлов
    file_path = None
    temp_file_path = None

    if version is None:
        download_url = f"{domain}/{prefix_url}/download/{type_version}"

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
            logger.info(f"Файл уже существует: {file_path}")
            if callable(on_complete):
                on_complete(file_path, success=True, skipped=True)
            return file_path

        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        logger.info(f"Начинаю загрузку: {filename}")
        with session.get(download_url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()

            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0

            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if total_size > 0 and callable(on_progress):
                            progress_percent = int((downloaded_size / total_size) * 100)
                            on_progress(progress_percent)

        if os.path.getsize(temp_file_path) == total_size or total_size == 0:
            os.rename(temp_file_path, file_path)
            logger.info(f"Файл успешно загружен: {file_path}")

            if callable(on_complete):
                on_complete(file_path, success=True, skipped=False)
            return file_path
        else:
            raise Exception("Размер скачанного файла не соответствует ожидаемому")

    except (requests.exceptions.RequestException, Exception) as e:
        error_msg = f"Ошибка при загрузке: {str(e)}"
        logger.error(error_msg, exc_info=True)

        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Удален неполный файл: {temp_file_path}")
            except Exception as cleanup_error:
                logger.error(f"Ошибка при удалении временного файла: {str(cleanup_error)}")

        if callable(on_complete):
            on_complete(None, success=False, error=error_msg)
        return None