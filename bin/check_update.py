import os
import re
from packaging import version
from typing import Tuple, Optional, Dict
import requests
from PySide6.QtCore import QThread, Signal
from bin.request_module import session

from logging_config import debug_logger
from path_builder import get_path

domain = "https://owl-app.ru"
# domain = "http://127.0.0.1:5000"

class GetManifestThread(QThread):
    check_success = Signal(dict)  # Передаем весь манифест
    check_failed = Signal()
    
    def __init__(self, current_version, auth_manager=None, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.auth_manager = auth_manager

    def run(self):
        try:
            manifest_url = f"{domain}/api/updates/manifest"
            
            # Формируем данные запроса в зависимости от режима
            if self.auth_manager and self.auth_manager.is_guest():
                # Гостевой режим
                debug_logger.info("👤 Запрос манифеста в гостевом режиме")
                data = {"guest": True}
                headers = {}
            elif self.auth_manager and self.auth_manager.token:
                # Авторизованный пользователь
                debug_logger.info("🔐 Запрос манифеста с JWT токеном")
                data = {"token": self.auth_manager.token}
                headers = {"Authorization": f"Bearer {self.auth_manager.token}"}
            else:
                # Нет авторизации
                debug_logger.error("❌ Нет авторизации для запроса манифеста")
                self.check_failed.emit()
                return

            # POST запрос
            response = session.post(
                manifest_url,
                json=data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                full_manifest = response.json()
                debug_logger.info("✅ Получен полный манифест обновлений")
                
                # Фильтруем манифест начиная с текущей версии пользователя
                filtered_manifest = self._filter_manifest_since_version(
                    full_manifest, 
                    str(self.current_version)
                )
                
                self.check_success.emit(filtered_manifest)
            else:
                debug_logger.error(f"❌ Ошибка получения манифеста: {response.status_code}")
                self.check_failed.emit()
                
        except requests.exceptions.RequestException as e:
            debug_logger.error(f"🌐 Ошибка сети при получении манифеста: {e}")
            self.check_failed.emit()
        except Exception as e:
            debug_logger.error(f"💥 Неожиданная ошибка: {e}")
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
                debug_logger.warning(f"Версия {user_version} не найдена в манифесте")
                return full_manifest
                
        except Exception as e:
            debug_logger.error(f"Ошибка фильтрации манифеста: {e}")
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
                    debug_logger.info(f"Последняя стабильная версия: {stable}")
                if exp:
                    debug_logger.info(f"Экспериментальная версия: {exp}")
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
                debug_logger.info(f"Последняя стабильная версия: {version}")
            if exp_version:
                debug_logger.info(f"Экспериментальная версия: {exp_version}")

            return version, exp_version
        else:
            debug_logger.error(f"Ошибка сервера: {response.status_code}")
            return None, None

    except requests.exceptions.RequestException as e:
        debug_logger.error(f"Ошибка соединения: {str(e)}")
        return None, None


def check_all_versions() -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Получает все версии с сервера
    Возвращает кортеж: (стабильные_версии, экспериментальные_версии)
    """
    try:
        versions_url = f"{domain}/versions"

        response = session.get(versions_url, timeout=5)
        response.raise_for_status()  # Генерирует исключение для HTTP-ошибок

        data = response.json()

        # Проверяем структуру ответа
        if not isinstance(data, dict):
            raise ValueError("Некорректный формат ответа сервера")

        # Получаем списки всех версий
        stable_versions = data.get("stable", [])
        experimental_versions = data.get("experimental", [])

        # Проверяем, что это действительно списки
        if not isinstance(stable_versions, list):
            stable_versions = []
        if not isinstance(experimental_versions, list):
            experimental_versions = []

        # Логируем информацию
        debug_logger.info(f"Получено стабильных версий: {len(stable_versions)}")
        debug_logger.info(f"Получено экспериментальных версий: {len(experimental_versions)}")

        return stable_versions, experimental_versions

    except requests.exceptions.RequestException as e:
        debug_logger.error(f"Ошибка соединения: {str(e)}")
        return None, None
    except ValueError as e:
        debug_logger.error(f"Ошибка формата данных: {str(e)}")
        return None, None
    except Exception as e:
        debug_logger.error(f"Неожиданная ошибка: {str(e)}")
        return None, None

def load_changelog():
    download_url = f"{domain}/getchangelog"
    changelog_path = get_path('update', 'changelog.md')

    try:
        # Создаем папку, если ее нет
        os.makedirs(os.path.dirname(changelog_path), exist_ok=True)

        with session.get(download_url, stream=True) as response:
            response.raise_for_status()  # Проверяем статус ответа

            # Записываем содержимое в файл
            with open(changelog_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Пропускаем пустые chunk
                        f.write(chunk)

        debug_logger.debug(f"Changelog успешно сохранен в: {changelog_path}")
        return True

    except requests.exceptions.RequestException as e:
        debug_logger.error(f"Ошибка при загрузке changelog: {str(e)}")
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
        debug_logger.error("Недопустимый тип версии")
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
        download_dir = get_path("update")
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
            debug_logger.info(f"Файл уже существует: {file_path}")
            if callable(on_complete):
                on_complete(file_path, success=True, skipped=True)
            return file_path

        # Удаляем старые временные файлы (если есть)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # Скачиваем во временный файл
        debug_logger.info(f"Начинаю загрузку: {filename}")
        with session.get(download_url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()

            # Получаем ожидаемый размер файла
            total_size = int(r.headers.get('content-length', 0))

            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:  # Фильтруем keep-alive chunks
                        f.write(chunk)

        # Проверяем целостность скачанного файла
        if os.path.getsize(temp_file_path) == total_size or total_size == 0:
            # Переименовываем временный файл в постоянный
            os.rename(temp_file_path, file_path)
            debug_logger.info(f"Файл успешно загружен: {file_path}")

            if callable(on_complete):
                on_complete(file_path, success=True, skipped=False)
            return file_path
        else:
            raise Exception("Размер скачанного файла не соответствует ожидаемому")

    except (requests.exceptions.RequestException, Exception) as e:
        error_msg = f"Ошибка при загрузке: {str(e)}"
        debug_logger.error(error_msg, exc_info=True)

        # Удаляем временный файл при ошибке
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                debug_logger.info(f"Удален неполный файл: {temp_file_path}")
            except Exception as cleanup_error:
                debug_logger.error(f"Ошибка при удалении временного файла: {str(cleanup_error)}")

        if callable(on_complete):
            on_complete(None, success=False, error=error_msg)
        return None

def download_single_file(file_path, target_version, auth_manager, on_progress=None):
    """Загрузка одного файла с сервера с использованием AuthManager"""
    try:
        # Проверяем авторизацию
        if not auth_manager or not auth_manager.is_authenticated():
            debug_logger.error("Пользователь не авторизован для загрузки файлов")
            return False
        
        # Используем токен из AuthManager
        token = auth_manager.token
        
        # Формируем URL и данные запроса
        url = f"{domain}/api/updates/{target_version}/{file_path}"

        if auth_manager.is_guest():
            debug_logger.info("Загрузка в гостевом режиме")
            response = session.post(
                url,
                json={"guest": True},  # или просто пустой JSON
                stream=True,
                timeout=30
            )
        else:
            data = {'token': token}
            headers = {"Authorization": f"Bearer {token}"}
            # Отправляем запрос с токеном
            response = session.post(
                url,
                json=data,
                headers=headers,
                stream=True,
                timeout=30
            )
        
        if response.status_code == 200:
            # Создаем директории если нужно
            local_path = get_path("update", f'{target_version}_temp', file_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
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
                            on_progress(file_path, progress)
            
            debug_logger.info(f"Файл загружен: {file_path}")
            return True
        else:
            debug_logger.error(f"Получен ответ от сервера: {response}")
            debug_logger.error(f"Ошибка загрузки {file_path}: {response.status_code}")
            if response.status_code == 401:
                debug_logger.error("Токен недействителен, требуется повторная авторизация")
            return False
            
    except requests.exceptions.Timeout:
        debug_logger.error(f"Таймаут при загрузке файла: {file_path}")
        return False
    except requests.exceptions.ConnectionError:
        debug_logger.error(f"Ошибка подключения при загрузке файла: {file_path}")
        return False
    except Exception as e:
        debug_logger.error(f"Ошибка при загрузке {file_path}: {str(e)}")
        return False

def download_delta_files(files_to_update, manifest, auth_manager, on_complete=None, on_progress=None):
    """Загрузка всех файлов дельта-обновления с авторизацией"""
    try:
        # Проверяем авторизацию
        if not auth_manager or not auth_manager.is_authenticated():
            error_msg = "Пользователь не авторизован"
            debug_logger.error(error_msg)
            if callable(on_complete):
                on_complete(file_path=None, success=False, error=error_msg)
            return False
        
        total_files = len(files_to_update)
        if total_files == 0:
            debug_logger.warning("Нет файлов для загрузки")
            if callable(on_complete):
                on_complete(file_path=None, success=True, skipped=True)
            return True
        
        # ✅ СНАЧАЛА определяем target_version
        target_version = None
        for file_path in files_to_update:
            file_ver = find_file_version(file_path, manifest)
            if file_ver:
                target_version = file_ver
                break
        
        if not target_version:
            debug_logger.error("❌ Не удалось определить целевую версию")
            if callable(on_complete):
                on_complete(file_path=None, success=False, error="Не удалось определить версию")
            return False
        
        # ✅ ТЕПЕРЬ используем target_version для проверки файлов
        temp_dir = get_path("update", f'{target_version}_temp')
        
        # ✅ ПРОВЕРЯЕМ - ВСЕ ЛИ ФАЙЛЫ УЖЕ СКАЧАНЫ
        all_files_exist = True
        for file_path in files_to_update:
            local_path = os.path.join(temp_dir, file_path)
            if not os.path.exists(local_path):
                all_files_exist = False
                break
        
        if all_files_exist:
            debug_logger.info("✅ Все файлы дельта-обновления уже скачаны")
            if callable(on_complete):
                on_complete(file_path=None, success=True, skipped=True, batch=True)
            return True
        
        debug_logger.info(f"Начинаем загрузку {total_files} файлов...")
        
        successful_downloads = 0
        failed_downloads = 0
        
        for i, file_path in enumerate(files_to_update):
            # Находим к какой версии принадлежит файл
            file_target_version = find_file_version(file_path, manifest)
            
            if not file_target_version:
                debug_logger.error(f"Не найдена версия для файла: {file_path}")
                failed_downloads += 1
                continue
            
            # Прогресс по файлам
            if on_progress:
                file_progress = ((i + 1) / total_files) * 100
                on_progress(f"Файл {i+1}/{total_files} ({file_path})", file_progress)
                
            # ✅ ПРОВЕРЯЕМ КОНКРЕТНЫЙ ФАЙЛ
            local_path = os.path.join(temp_dir, file_path)
            if os.path.exists(local_path):
                debug_logger.info(f"📁 Файл уже существует, пропускаем: {file_path}")
                successful_downloads += 1
                continue
                
            # Загружаем файл
            success = download_single_file(file_path, file_target_version, auth_manager, on_progress)
            
            if success:
                successful_downloads += 1
                debug_logger.info(f"Успешно загружен: {file_path} ({successful_downloads}/{total_files})")
            else:
                failed_downloads += 1
                debug_logger.error(f"Ошибка загрузки: {file_path}")
        
        # Формируем итоговый результат
        if failed_downloads == 0:
            debug_logger.info(f"✅ Все файлы успешно загружены ({successful_downloads}/{total_files})")
            if callable(on_complete):
                local_path = get_path("update", f'{target_version}_temp')
                on_complete(file_path=local_path, success=True, skipped=False, batch=True)
            return True
        else:
            error_msg = f"Загружено {successful_downloads}/{total_files} файлов. Ошибок: {failed_downloads}"
            debug_logger.error(f"❌ {error_msg}")
            if callable(on_complete):
                on_complete(file_path=None, success=False, error=error_msg)
            return False
        
    except Exception as e:
        error_msg = f"Неожиданная ошибка при загрузке файлов: {str(e)}"
        debug_logger.error(error_msg)
        if callable(on_complete):
            on_complete(file_path=None, success=False, error=error_msg)
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
        debug_logger.info(f"Файл {file_path} будет загружен из версии {latest_version}")
    else:
        debug_logger.error(f"Файл {file_path} не найден")
    
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
            if any(marker in ver_str.lower() for marker in ['-beta', '-alpha', '-exp', '-rc', '-dev']):
                    continue
            version_objects.append(version.parse(ver_str))
        except:
            continue
    
    # Сортируем объекты Version
    version_objects.sort()
    
    debug_logger.info(f"Проверка обновления: {current_version} -> {target_version}")
    debug_logger.info(f"Доступные версии: {[str(v) for v in version_objects]}")
    
    try:
        # Находим индексы в отсортированном списке объектов Version
        current_idx = version_objects.index(current_version)
        target_idx = version_objects.index(target_version)
        
        debug_logger.info(f"Индексы: current={current_idx}, target={target_idx}")
        
        # Проверяем все версии между текущей и целевой
        for i in range(current_idx + 1, target_idx + 1):
            version_obj = version_objects[i]
            version_str = str(version_obj)
            
            # Получаем full_update из манифеста по строковому ключу
            full_update = manifest.get(version_str, {}).get('full_update', False)
            debug_logger.info(f"🔎 Проверка версии {version_str}: full_update={full_update}")
            
            if full_update:
                debug_logger.info("Найдена версия с full_update=True")
                return True
    
    except ValueError as e:
        debug_logger.error(f"Версия не найдена: {e}")
        debug_logger.error(f"Текущая: {current_version}, Целевая: {target_version}")
        debug_logger.error(f"Доступные: {[str(v) for v in version_objects]}")
        return True
    
    debug_logger.info("Дельта-обновление доступно")
    return False