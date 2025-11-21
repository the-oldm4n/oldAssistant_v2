import os
import re
import uuid
import requests
from PySide6.QtCore import QThread, Signal
from packaging import version
from utils import get_config_value, logger, get_base_directory

domain = "https://owl-app.ru"
# domain = "http://127.0.0.1:5000"

# Получаем версию из конфига
APP_VERSION = get_config_value("app", "version", "1.0.0")
USER_AGENT = f"OWLAPP/Updater/v.{APP_VERSION}/"

# Создаем сессию с кастомным User-Agent
session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT
})

class GetManifestThread(QThread):
    check_success = Signal(dict)
    check_failed = Signal()
    
    def __init__(self, current_version, update_auth_manager, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.update_auth = update_auth_manager  # Используем UpdateAuthManager

    def run(self):
        try:
            # Получаем манифест через UpdateAuthManager
            manifest = self.update_auth.make_update_request('/api/updates/manifest')
            
            if manifest:
                logger.info("✅ Получен манифест обновлений")
                
                # Фильтруем манифест начиная с текущей версии пользователя
                filtered_manifest = self._filter_manifest_since_version(
                    manifest, 
                    str(self.current_version)
                )
                
                self.check_success.emit(filtered_manifest)
            else:
                logger.error("❌ Не удалось получить манифест")
                self.check_failed.emit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения манифеста: {e}")
            self.check_failed.emit()

    def _filter_manifest_since_version(self, full_manifest, user_version):
        """Фильтрует манифест начиная с версии пользователя"""
        try:
            versions = sorted(full_manifest.keys())
            
            if user_version in versions:
                user_idx = versions.index(user_version)
                # Возвращаем только версии начиная с пользовательской
                return {
                    ver: full_manifest[ver] 
                    for ver in versions[user_idx:] 
                    if ver in full_manifest
                }
            else:
                # Если версия не найдена, возвращаем весь манифест
                logger.warning(f"Версия {user_version} не найдена в манифесте")
                return full_manifest
                
        except Exception as e:
            logger.error(f"Ошибка фильтрации манифеста: {e}")
            return full_manifest


class VersionCheckThread(QThread):
    version_checked = Signal(str, str)  # Сигнал для stable и exp версий
    check_failed = Signal()  # Сигнал при ошибке

    def run(self):
        try:
            version_url = f"{domain}/version"
            response = session.get(version_url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                stable = data.get("stable", {}).get("version", "")
                exp = data.get("experimental", {}).get("exp_version", "")
                if stable:
                    logger.info(f"Последняя стабильная версия: {stable}")

                if exp:
                    logger.info(f"Экспериментальная версия: {exp}")
                self.version_checked.emit(stable, exp)
            else:
                self.check_failed.emit()
        except requests.exceptions.RequestException:
            self.check_failed.emit()

def check_version():
    try:
        version_url = f"{domain}/version"
        response = session.get(version_url, timeout=5)  # Добавляем таймаут

        if response.status_code == 200:
            data = response.json()

            stable_data = data.get("stable", {}) or {}
            experimental_data = data.get("experimental", {}) or {}

            version = stable_data.get("version")
            exp_version = experimental_data.get("exp_version")

            if version:
                logger.info(f"Последняя стабильная версия: {version}")
            if exp_version:
                logger.info(f"Экспериментальная версия: {exp_version}")

            return version, exp_version
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
    if type_version not in ["stable", "exp"]:
        logger.error("Недопустимый тип версии")
        return None

    download_url = None
    temp_suffix = ".tempdownload"  # Суффикс для временных файлов
    file_path = None
    temp_file_path = None

    if version is None:
        download_url = f"{domain}/download/{type_version}"
    else:
        download_url = f"{domain}/load/{type_version}/{version}"

    try:
        root_dir = get_base_directory()
        download_dir = root_dir / "update"
        os.makedirs(download_dir, exist_ok=True)

        # Получаем имя файла из заголовков
        with session.head(download_url, allow_redirects=True) as r:
            r.raise_for_status()
            content_disposition = r.headers.get('Content-Disposition')
            filename = get_filename_from_cd(content_disposition) or f"{type_version}_update.zip"

        file_path = os.path.join(download_dir, filename)
        temp_file_path = file_path + temp_suffix

        # Если уже есть полная версия файла
        if os.path.exists(file_path):
            logger.info(f"Файл уже существует: {file_path}")
            if callable(on_complete):
                on_complete(file_path, success=True, skipped=True)
            return file_path

        # Удаляем старые временные файлы (если есть)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # Скачиваем во временный файл
        logger.info(f"Начинаю загрузку: {filename}")
        with session.get(download_url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()

            # Получаем ожидаемый размер файла
            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0

            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # Фильтруем keep-alive chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # Отправляем прогресс (от 0 до 100%)
                        if total_size > 0 and callable(on_progress):
                            progress_percent = int((downloaded_size / total_size) * 100)
                            on_progress(progress_percent)

        # Проверяем целостность скачанного файла
        if os.path.getsize(temp_file_path) == total_size or total_size == 0:
            # Переименовываем временный файл в постоянный
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

        # Удаляем временный файл при ошибке
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Удален неполный файл: {temp_file_path}")
            except Exception as cleanup_error:
                logger.error(f"Ошибка при удалении временного файла: {str(cleanup_error)}")

        if callable(on_complete):
            on_complete(None, success=False, error=error_msg)
        return None
    
    
class DeltaDownloadThread(QThread):
    download_complete = Signal(str, bool, bool, str)
    download_progress = Signal(int)

    def __init__(self, files_to_update, manifest, target_version, update_auth_manager, skip_existing=False, parent=None):
        super().__init__(parent)
        self.files_to_update = files_to_update
        self.manifest = manifest
        self.target_version = target_version
        self.update_auth = update_auth_manager
        self.skip_existing = skip_existing

    def run(self):
        download_delta_files(
            files_to_update=self.files_to_update,
            manifest=self.manifest,
            target_version=self.target_version,
            update_auth=self.update_auth,
            on_complete=self._handle_complete,
            on_progress=self._handle_progress,
            skip_existing=self.skip_existing
        )

    def _handle_complete(self, file_path, success=True, skipped=False, error=None):
        logger.info(f"📥 _handle_complete получен: file_path={file_path}, success={success}")
        self.download_complete.emit(file_path, success, skipped, error)
        
    def _handle_progress(self, progress_percent):
        self.download_progress.emit(progress_percent)
            
def download_delta_files(files_to_update, manifest, target_version, update_auth, on_complete=None, on_progress=None, skip_existing=False):
    """Загрузка всех файлов дельта-обновления"""
    try:
        if not update_auth or not update_auth.token:
            if not update_auth.get_update_token():
                error_msg = "Не удалось получить токен для обновлений"
                logger.error(error_msg)
                if callable(on_complete):
                    on_complete(None, success=False, error=error_msg)
                return False
        
        root_dir = get_base_directory()
        temp_dir = root_dir / "update" / f'{target_version}_temp'
        os.makedirs(temp_dir, exist_ok=True)
        
        # Если skip_existing=True, фильтруем уже существующие файлы
        if skip_existing:
            existing_files = []
            files_to_download = []
            
            for file_path in files_to_update:
                local_path = temp_dir / file_path
                if os.path.exists(local_path):
                    existing_files.append(file_path)
                    logger.debug(f"Файл уже существует, пропускаем: {file_path}")
                else:
                    files_to_download.append(file_path)
            
            logger.info(f"Пропущено {len(existing_files)} существующих файлов, осталось {len(files_to_download)} для загрузки")
            files_to_update = files_to_download
        else:
            # Очищаем папку от старых файлов если не пропускаем существующие
            for file_path in files_to_update:
                local_path = temp_dir / file_path
                if os.path.exists(local_path):
                    os.remove(local_path)
        
        total_files = len(files_to_update)
        if total_files == 0:
            logger.warning("Нет файлов для загрузки")
            if callable(on_complete):
                on_complete(str(temp_dir), success=True, skipped=True)
            return True
        
        logger.info(f"Начинаем загрузку {total_files} файлов...")
        
        # СОЗДАЕМ client_session_id для всей сессии загрузки
        client_session_id = str(uuid.uuid4())
        logger.info(f"Начинаем загрузку {total_files} файлов, session: {client_session_id}")

        successful_downloads = 0
        failed_downloads = 0
        
        for i, file_path in enumerate(files_to_update):
            # Находим к какой версии принадлежит файл
            file_target_version = find_file_version(file_path, manifest)
            
            if not file_target_version:
                logger.error(f"Не найдена версия для файла: {file_path}")
                failed_downloads += 1
                continue
            
            # Прогресс по файлам
            if on_progress:
                file_progress = ((i + 1) / total_files) * 100
                on_progress(int(file_progress))
                
            # Загружаем файл
            success = download_single_file(
                file_path, 
                file_target_version, 
                update_auth, 
                temp_dir,
                on_progress,
                client_session_id
            )
            
            if success:
                successful_downloads += 1
                logger.info(f"Успешно загружен: {file_path} ({successful_downloads}/{total_files})")
            else:
                failed_downloads += 1
                logger.error(f"Ошибка загрузки: {file_path}")
        
        # Формируем итоговый результат
        if failed_downloads == 0:
            logger.info(f"✅ Все файлы успешно загружены ({successful_downloads}/{total_files})")
            if callable(on_complete):
                on_complete(str(temp_dir), success=True, skipped=False)
            return True
        else:
            error_msg = f"Загружено {successful_downloads}/{total_files} файлов. Ошибок: {failed_downloads}"
            logger.error(f"❌ {error_msg}")
            if callable(on_complete):
                on_complete(None, success=False, error=error_msg)
            return False
        
    except Exception as e:
        error_msg = f"Неожиданная ошибка при загрузке файлов: {str(e)}"
        logger.error(error_msg)
        if callable(on_complete):
            on_complete(None, success=False, error=error_msg)
        return False

def download_single_file(file_path, target_version, update_auth, temp_dir, on_progress=None, client_session_id=None):
    """Загрузка одного файла с сервера с использованием UpdateAuthManager"""
    try:
        # Проверяем авторизацию
        if not update_auth or not update_auth.token:
            logger.error("Не удалось получить токен для загрузки файлов")
            return False
        
        # Используем токен из UpdateAuthManager
        token = update_auth.token
        
        # Формируем URL и данные запроса
        url = f"{domain}/api/updates/{target_version}/{file_path}"
        data = {'token': token}
        # Добавляем client_session_id если есть (новые клиенты)
        if client_session_id:
            data['client_session_id'] = client_session_id
            logger.info(f"Используем session_id: {client_session_id}")
        headers = {"Authorization": f"Bearer {token}"}
        # Отправляем запрос с токеном
        response = session.post(
            url,
            json=data,
            headers=headers,
            stream=True,
            timeout=30
        )
        
        # Получаем session_id из заголовка (может быть None для старых клиентов)
        new_session_id = response.headers.get('X-Download-Session')
        if new_session_id and new_session_id != client_session_id:
            logger.info(f"Получен новый session_id от сервера: {new_session_id}")
            client_session_id = new_session_id
        
        if response.status_code == 200:
            local_path = temp_dir / file_path
            
            local_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Созданы директории для: {local_path}")
            
            # Скачиваем файл
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Отправляем прогресс если нужно
                        if on_progress and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            on_progress(progress)  # Только прогресс, без текста
            
            logger.info(f"Файл загружен: {file_path}")
            return True
        else:
            logger.error(f"Ошибка загрузки {file_path}: {response.status_code}")
            if response.status_code == 401:
                logger.error("Токен недействителен, требуется повторная авторизация")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"Таймаут при загрузке файла: {file_path}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Ошибка подключения при загрузке файла: {file_path}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при загрузке {file_path}: {str(e)}")
        return False

def find_file_version(file_path, manifest):
    """Находит самую новую версию где файл был изменен"""
    latest_version = None
    
    for ver, data in manifest.items():
        if file_path in data.get('changed_files', []):
            # Если это первая найденная версия или версия новее текущей
            if latest_version is None or version.parse(ver) > version.parse(latest_version):
                latest_version = ver
    
    if latest_version:
        logger.info(f"Файл {file_path} будет загружен из версии {latest_version}")
    else:
        logger.error(f"Файл {file_path} не найден")
    
    return latest_version


def get_update_strategy(current_version, target_version, manifest):
    """Определяет стратегию обновления"""
    # current_version и target_version уже объекты Version
    # Преобразуем версии из манифеста в объекты Version для точного сравнения
    
    if target_version <= current_version:
        return "none"  # Не нужно обновление
    
    if should_force_full_update(current_version, target_version, manifest):
        return "full"  # Полная установка
    else:
        return "delta"  # Дельта-обновление

def should_force_full_update(current_version, target_version, manifest):
    """Проверяет, нужна ли полная установка из-за пропущенных версий"""
    # Создаем список версий из манифеста как объекты Version
    version_objects = []
    for ver_str in manifest.keys():
        try:
            version_objects.append(version.parse(ver_str))
        except:
            continue
    
    # Сортируем объекты Version
    version_objects.sort()
    
    logger.info(f"🔍 Проверка обновления: {current_version} -> {target_version}")
    logger.info(f"📋 Доступные версии: {[str(v) for v in version_objects]}")
    
    try:
        # Находим индексы в отсортированном списке объектов Version
        current_idx = version_objects.index(current_version)
        target_idx = version_objects.index(target_version)
        
        logger.info(f"📊 Индексы: current={current_idx}, target={target_idx}")
        
        # Проверяем все версии между текущей и целевой
        for i in range(current_idx + 1, target_idx + 1):
            version_obj = version_objects[i]
            version_str = str(version_obj)
            
            # Получаем full_update из манифеста по строковому ключу
            full_update = manifest.get(version_str, {}).get('full_update', False)
            logger.info(f"🔎 Проверка версии {version_str}: full_update={full_update}")
            
            if full_update:
                logger.info("✅ Найдена версия с full_update=True")
                return True
    
    except ValueError as e:
        logger.error(f"❌ Версия не найдена: {e}")
        logger.error(f"❌ Текущая: {current_version}, Целевая: {target_version}")
        logger.error(f"❌ Доступные: {[str(v) for v in version_objects]}")
        return True
    
    logger.info("✅ Дельта-обновление доступно")
    return False


