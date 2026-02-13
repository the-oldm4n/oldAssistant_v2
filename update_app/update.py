import os
import shutil
import subprocess
import time
import zipfile
import psutil
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, \
                               QPushButton, QLabel, QSizePolicy,
                               QGraphicsColorizeEffect, QSpacerItem)
import sys
from packaging import version
import requests
import send2trash
from check_and_download import DeltaDownloadThread, DownloadThread, GetManifestThread, VersionCheckThread
from apply_colors import ApplyColor
from custom_widgets import CustomSvgWidget, SVGProgressBar
from utils import get_path, logger, get_base_directory, update_signal, run_app_signal, get_config_value


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

class UpdateAuthManager:
    def __init__(self):
        self.token = None
        self.base_url = domain
        
    def get_update_token(self):
        """Получить временный токен для обновлений"""
        try:
            response = session.post(
                f"{self.base_url}/api/updates/token",
                json={
                    'app_id': 'assistant_updater',
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self.token = response.json()['token']
                return True
            return False
        except:
            return False
    
    def make_update_request(self, endpoint, data=None):
        """Выполнить запрос с токеном обновлений"""
        if not self.token:
            if not self.get_update_token():
                return None
        
        # Формируем данные с токеном
        request_data = data or {}
        request_data['token'] = self.token
        
        try:
            response = session.post(
                f"{self.base_url}{endpoint}",
                json=request_data,
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except:
            return None


class UnpackAppThread(QThread):
    """
    Класс, отвечающий за распаковку архива обновления, испускает сигнал по окончании распаковки.
    """
    unpack_complete = Signal(bool)

    def __init__(self):
        super().__init__()

        self.root_dir = get_base_directory()  # Корень (Assistant/)
        self.update_pack_dir = self.root_dir / "update_pack"
        self.update_pack_dir.mkdir(parents=True, exist_ok=True)
        self.update_file_path = self.find_update_file()

    def run(self):
        if not self.update_file_path:
            logger.error("Не найден файл обновления (*.zip)")
            update_signal.status_update.emit("Не найден файл обновления (*.zip)", 60)
            self.unpack_complete.emit(False)
            return

        if self.is_already_unpacked():
            logger.info("Архив уже распакован")
            update_signal.status_update.emit("Архив распакован", 70)
            self.unpack_complete.emit(True)
            return

        if not self.extract_archive(self.update_file_path):
            update_signal.status_update.emit("Не удалось распаковать архив с новой версией", 60)
            self.unpack_complete.emit(False)
            return
        logger.info(f"Архив с новой версией распакован по пути {self.update_pack_dir}")
        self.unpack_complete.emit(True)

    def is_already_unpacked(self):
        """Проверяет, распакован ли уже архив"""
        try:
            # Проверяем существование папки и наличие файлов
            if not os.path.exists(self.update_pack_dir):
                return False

            # Проверяем, есть ли содержимое (игнорируем скрытые файлы)
            visible_files = [f for f in os.listdir(self.update_pack_dir)
                             if not f.startswith('.') and f not in ['log', 'user_settings']]

            if not visible_files:
                return False

            # Проверяем ключевые файлы/папки которые должны быть после распаковки
            required_items = ['Assistant.exe', '_internal']
            for item in required_items:
                item_path = os.path.join(self.update_pack_dir, item)
                if not os.path.exists(item_path):
                    return False

            logger.info("Обновление уже распаковано")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки распаковки: {e}")
            return False

    def find_update_file(self):
        root_dir = get_base_directory()
        update_dir = root_dir / "update"
        pattern = f"stable_Assistant_*.zip"
        # Ищем самый свежий файл по дате изменения
        files = []
        for file in os.listdir(update_dir):
            if file.lower().startswith("stable") and file.lower().endswith('.zip'):
                file_path = os.path.join(update_dir, file)
                files.append((file_path, os.path.getmtime(file_path)))

        if files:
            # Сортируем по дате изменения (новые сначала)
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
        return None

    def extract_archive(self, archive_path):
        """Безопасная распаковка архива с обработкой кодировок"""
        try:
            # Очищаем папку перед распаковкой
            for item in os.listdir(self.update_pack_dir):
                item_path = os.path.join(self.update_pack_dir, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                else:
                    shutil.rmtree(item_path)

            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Безопасное извлечение имени файла
                    file_name = self._safe_decode_filename(file_info.filename)

                    # Защита от Zip Slip
                    target_path = os.path.join(self.update_pack_dir, file_name)
                    if not os.path.abspath(target_path).startswith(os.path.abspath(self.update_pack_dir)):
                        raise ValueError(f"Попытка распаковки вне целевой папки: {file_name}")

                    # Создаем папки если нужно
                    if file_name.endswith('/'):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as f:
                            f.write(zip_ref.read(file_info))
            return True

        except Exception as e:
            logger.error(f"Ошибка распаковки: {str(e)}", exc_info=True)
            update_signal.status_update.emit(f"Ошибка распаковки: {str(e)}", 60)
            return False

    def _safe_decode_filename(self, filename):
        """Безопасное декодирование имени файла из архива с поддержкой русского"""
        # Список кодировок для попытки декодирования (в порядке приоритета)
        encodings = [
            'cp866',  # DOS/Windows Russian
            'cp1251',  # Windows Cyrillic
            'utf-8',  # Unicode
            'cp437',  # DOS English
            'iso-8859-1',  # Latin-1
            'koi8-r'  # Russian KOI8-R
        ]

        # Сначала пробуем стандартное декодирование (для современных ZIP)
        try:
            return filename.encode('cp437').decode('utf-8')
        except UnicodeError:
            pass

        # Если не получилось, пробуем все кодировки по очереди
        for enc in encodings:
            try:
                return filename.encode('cp437').decode(enc)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

        # Если ничего не помогло, возвращаем как есть и логируем проблему
        logger.warning(f"Не удалось декодировать имя файла: {filename}")
        return filename


class UpdateWindow(QWidget):
    """
    Главное окно обновления.
    Содержит логику предварительной проверки обновлений, скачивание, установку и запуск основного приложения.
    """

    def __init__(self):
        super().__init__()
        self.check_thread = None
        self.download_thread = None
        self.unpack_thread = None
        self.update_completed = False
        self.root_dir = get_base_directory()
        self.update_pack_dir = self.root_dir / "update_pack"
        self.old_files_dir = self.root_dir / "old_files_backup"  # Папка для резервных копий
        self.no_check_mode = "--no-checked" in sys.argv
        self.install_mode = "--install-mode" in sys.argv
        self.batch_update = "--batch-update" in sys.argv
        run_app_signal.run_main_app.connect(self.run_main_app)
        self.setWindowIcon(QIcon(get_path('icon.ico')))
        self.parent_style = self.root_dir / "user_settings" / "color_settings.json"
        self.style_path = get_path('color.json')
        if self.parent_style.exists():
            style = self.parent_style
        else:
            style = self.style_path
        self.svg_path = get_path("logo.svg")
        self.version = get_config_value("app", "version")
        self.style_manager = ApplyColor(style)
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()
        self.start_update_process()

    def init_ui(self):
        try:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(250, 250)

            screen_geometry = QApplication.primaryScreen().availableGeometry()
            self.move(
                (screen_geometry.width() - self.width()) // 2,
                (screen_geometry.height() - self.height()) // 2
            )
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)

            self.main_widget = QWidget()
            self.main_widget.setObjectName("WindowContainer")
            content_layout = QVBoxLayout(self.main_widget)
            content_layout.setContentsMargins(15, 0, 15, 10)
            content_layout.addStretch()

            self.svg_image = CustomSvgWidget(self.svg_path)
            self.svg_image.setFixedSize(120, 110)
            self.svg_image.setStyleSheet("""
                    background: transparent;
                    border: none;
                    outline: none;
                """)
            self.color_svg = QGraphicsColorizeEffect()
            self.svg_image.setGraphicsEffect(self.color_svg)
            content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)
            
            content_layout.addStretch()
            
            self.progress = SVGProgressBar(
                svg_widget=self.svg_image,
                style="circle",
                circle_size=180,
                show_text=False,
                line_width=3)
            self.progress.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

            self.label = QLabel("Завершение программы...")
            self.label.setStyleSheet("background: transparent; min-height: 35px; max-height: 35px; font-size:14px")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setWordWrap(True)
            self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            content_layout.addWidget(self.label)

            self.button_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

            # Кнопка выхода
            self.error_button = QPushButton("Закрыть")
            self.error_button.clicked.connect(self.quit_application)
            self.error_button.setStyleSheet("""width:100px; border-radius:5px""")
            self.error_button.hide()
            content_layout.addWidget(self.error_button, alignment=Qt.AlignmentFlag.AlignCenter)

            self.setLayout(layout)
            layout.addWidget(self.main_widget, 1)
        except Exception as e:
            logger.error(f"Ошибка в init_ui: {e}")

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            # Применение к SVG
            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_progressbar(widget=self.progress)

            # Применение общего стиля окна
            if hasattr(self, 'central_widget'):
                self.central_widget.setObjectName("CentralWidget")
            if hasattr(self, 'title_bar_widget'):
                self.title_bar_widget.setObjectName("TitleBar")
            # Применяем стили к текущему окну
            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):  # Для стандартных виджетов (например, QMainWindow, QPushButton)
                    selector = widget
                else:  # Для виджетов с objectName (например, TitleBar, CentralWidget)
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            self.setStyleSheet(style_sheet)
            self.main_widget.setStyleSheet("""border-radius:20px""")
        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def start_update_process(self):
        if self.check_thread is not None:
            return

        self.label.setText("Проверка...")

        # 1. Сначала закрываем основную программу
        if self.is_main_app_running():
            self.set_status("Закрытие Assistant.exe...", 0)
            self.kill_main_app()
            time.sleep(2)  # Даем время на закрытие
        
        # 2. Проверяем режим batch_update
        if self.batch_update:
            self.set_status("Пропуск проверки обновлений...", 30)
            QTimer.singleShot(1000, self.start_install_batch)
            
        # 3. Проверяем режим no-check
        if self.no_check_mode:
            self.set_status("Пропуск проверки обновлений...", 30)
            QTimer.singleShot(1000, self.start_install_from_existing)  # Прямо к установке
        else:
            # 3. Запускаем обычную цепочку из UI потока
            self.start_check_update()

    def start_check_update(self):
        """Запуск проверки обновлений из UI потока"""
        self.set_status("Поиск обновлений...", 10)
        import traceback
        logger.info("=== ВТОРАЯ ПРОВЕРКА ВЕРСИИ! Стек вызовов: ===")
        logger.info(traceback.format_stack())
        logger.info("=============================================")

        self.check_thread = VersionCheckThread()
        self.check_thread.version_checked.connect(self.on_version_checked)
        self.check_thread.check_failed.connect(self.on_check_failed)
        self.check_thread.start()

    def on_version_checked(self, stable_version, exp_version):
        """Обработка результата проверки в UI потоке"""
        if hasattr(self, 'check_attempts'):
            delattr(self, 'check_attempts')
        try:
            # Получаем текущую версию с обработкой ошибок
            current_version_str = self.version
            if not current_version_str:
                logger.warning("Не удалось получить текущую версию из конфига, используем '0.0.0'")
                current_version_str = "0.0.0"

            current_version = version.parse(current_version_str)

            # Проверяем stable_version на None
            if stable_version is None:
                logger.error("Не удалось получить стабильную версию с сервера")
                self.retry_version_check()
                return

            stable_ver = version.parse(stable_version)

            if stable_ver > current_version:
                self.set_status("Скачивание обновления...", 30)
                self.get_update_manifest(current_version, stable_version)
            else:
                self.set_status("Установлена последняя версия", 100)
                QTimer.singleShot(200, self.run_main_app)

        except Exception as e:
            logger.error(f"Ошибка при обработке версий: {e}")
            self.retry_version_check()
            
    def get_update_manifest(self, current_version, target_version, attempt=1, max_attempts=3):
        """Получение манифеста обновлений с повторными попытками"""
        try:
            update_auth = UpdateAuthManager()
            self.manifest_thread = GetManifestThread(current_version, update_auth)
            
            # Используем лямбду для передачи attempt и max_attempts
            self.manifest_thread.check_success.connect(
                lambda manifest: self.on_manifest_ready(manifest, target_version)
            )
            self.manifest_thread.check_failed.connect(
                lambda: self.on_manifest_failed(current_version, target_version, attempt, max_attempts)
            )
            self.manifest_thread.start()
            
        except Exception as e:
            logger.error(f"Ошибка получения манифеста: {e}")
            self.on_manifest_failed(current_version, target_version, attempt, max_attempts)
            
    def on_manifest_failed(self, current_version, target_version, attempt=1, max_attempts=3):
        """Обработка ошибки получения манифеста с повторными попытками"""
        if attempt <= max_attempts:
            logger.warning(f"❌ Попытка {attempt}/{max_attempts} получить манифест не удалась")
            self.set_status(f"Повторная попытка получить обновление ({attempt}/{max_attempts})...", 30)
            
            # Повторная попытка через 2 секунды
            QTimer.singleShot(2000, lambda: self.retry_get_manifest(current_version, target_version, attempt, max_attempts))
        else:
            logger.error("❌ Не удалось получить манифест после всех попыток, запускаем приложение без обновления")
            self.set_status("Не удалось проверить обновления", 0)
            # Запускаем основное приложение без обновления
            QTimer.singleShot(2000, self.run_main_app)

    def retry_get_manifest(self, current_version, target_version, attempt, max_attempts):
        """Повторная попытка получить манифест"""
        self.get_update_manifest(current_version, target_version, attempt + 1, max_attempts)

    def on_manifest_ready(self, manifest, target_version):
        """Обработка готового манифеста и запуск соответствующей загрузки"""
        try:
            # Получаем текущую версию
            current_version_str = get_config_value("app", "version")
            if not current_version_str:
                current_version_str = "0.0.0"
            
            current_ver = version.parse(current_version_str)
            latest_ver = version.parse(target_version)
            
            if current_ver == latest_ver:
                logger.info("Установлена последняя версия, запускаем приложение")
                self.set_status("Установлена последняя версия", 100)
                QTimer.singleShot(1000, self.run_main_app)
                return
            
            # Удаление файлов (если таковые есть в манифесте)
            files_to_delete = self.collect_files_for_deletion(current_ver, latest_ver, manifest)
            if files_to_delete:
                self.set_status("Очистка устаревших файлов...", 75)
                self.delete_files_safely(files_to_delete)
            
            # Определяем стратегию обновления
            strategy = self.get_update_strategy(current_ver, latest_ver, manifest)
            logger.info(f"Стратегия обновления: {strategy}")
            
            if strategy == "full":
                logger.info("Требуется полная установка (было критическое обновление)")
                self.start_download(target_version)
            else:
                logger.info("Дельта-обновление доступно")
                # Собираем все файлы из всех версий между current и latest
                files_to_update = self.collect_all_changed_files(current_ver, latest_ver, manifest)
                
                if self.batch_update:
                    # В batch-режиме проверяем есть ли уже скачанные файлы
                    self.process_batch_delta(files_to_update, manifest, target_version)
                else:
                    self.start_delta_download(files_to_update, manifest, target_version)
                    
        except Exception as e:
            logger.error(f"Ошибка обработки манифеста: {e}")
            
    def process_batch_delta(self, files_to_update, manifest, target_version):
        """Обработка дельта-обновления в batch-режиме"""
        try:
            root_dir = get_base_directory()
            temp_dir = root_dir / "update" / f'{target_version}_temp'
            
            # Проверяем существование папки
            if not os.path.exists(temp_dir):
                logger.info(f"Папка обновления не найдена, начинаем полную загрузку: {temp_dir}")
                self.start_delta_download(files_to_update, manifest, target_version, skip_existing=False)
                return
            
            # Проверяем наличие файлов
            missing_files = []
            for file_path in files_to_update:
                local_path = temp_dir / file_path
                if not os.path.exists(local_path):
                    missing_files.append(file_path)
            
            if missing_files:
                logger.info(f"Найдено {len(missing_files)} отсутствующих файлов, докачиваем...")
                self.start_delta_download(missing_files, manifest, target_version, skip_existing=True)
            else:
                logger.info("Все файлы присутствуют, начинаем установку")
                self.install_delta_update(temp_dir)
                
        except Exception as e:
            logger.error(f"Ошибка обработки batch-дельта: {e}")
            self.show_error("Ошибка обработки обновления")

    def get_update_strategy(self, current_ver, target_ver, manifest):
        """Определяет стратегию обновления: full или delta"""
        try:
            # Преобразуем версии из манифеста в объекты Version для сравнения
            version_objects = []
            version_to_str_map = {}
            
            for ver_str in manifest.keys():
                try:
                    if any(marker in ver_str.lower() for marker in ['-beta', '-alpha', '-exp', '-rc', '-dev']):
                        continue
                    ver_obj = version.parse(ver_str)
                    version_objects.append(ver_obj)
                    version_to_str_map[ver_obj] = ver_str
                except:
                    continue
            
            # Сортируем объекты Version
            version_objects.sort()
            
            logger.info(f"🔎 Доступные версии в манифесте: {[str(v) for v in version_objects]}")
            logger.info(f"🔎 Текущая версия: {current_ver}, Целевая версия: {target_ver}")
            
            # Находим индексы в отсортированном списке
            current_idx = version_objects.index(current_ver)
            target_idx = version_objects.index(target_ver)
            
            logger.info(f"🔎 Индексы: current_idx={current_idx}, target_idx={target_idx}")
            
            # ИСПРАВЛЕНИЕ: проверяем ВСЕ версии от текущей до целевой включительно
            # если в текущей версии full_update=true, то не нужна полная установка
            for i in range(current_idx + 1, target_idx + 1):  # ← current_idx + 1
                version_obj = version_objects[i]
                version_str = version_to_str_map[version_obj]
                full_update = manifest[version_str].get('full_update', False)
                
                logger.info(f"🔎 Проверка версии {version_str}: full_update={full_update}")
                
                if full_update:
                    logger.info(f"🚨 Найдено полное обновление в версии {version_str}")
                    return "full"
            
            logger.info("✅ Дельта-обновление доступно")
            return "delta"
            
        except (ValueError, Exception) as e:
            logger.error(f"❌ Ошибка определения стратегии обновления: {e}")
            return "full"

    def collect_all_changed_files(self, current_ver, target_ver, manifest):
        """Собирает все измененные файлы между версиями"""
        try:
            # Преобразуем версии из манифеста в объекты Version для сравнения
            version_objects = []
            version_to_str_map = {}  # Сопоставление Version -> строковый ключ
            
            for ver_str in manifest.keys():
                try:
                    ver_obj = version.parse(ver_str)
                    version_objects.append(ver_obj)
                    version_to_str_map[ver_obj] = ver_str
                except:
                    continue
            
            # Сортируем объекты Version
            version_objects.sort()
            
            # Находим индексы в отсортированном списке объектов Version
            current_idx = version_objects.index(current_ver)
            target_idx = version_objects.index(target_ver)
            
            all_files = set()
            for i in range(current_idx + 1, target_idx + 1):
                version_obj = version_objects[i]
                version_str = version_to_str_map[version_obj]  # Получаем строковый ключ
                files = manifest[version_str].get('changed_files', [])  # Используем changed_files
                all_files.update(files)
            
            logger.info(f"Собрано {len(all_files)} файлов для дельта-обновления")
            return list(all_files)
            
        except ValueError as e:
            logger.error(f"❌ Версия не найдена в collect_all_changed_files: {e}")
            logger.error(f"❌ Текущая: {current_ver}, Целевая: {target_ver}")
            logger.error(f"❌ Доступные: {[str(v) for v in version_objects]}")
            return []
        except Exception as e:
            logger.error(f"Ошибка сбора файлов: {e}")
            return []

    def retry_version_check(self, attempt=1, max_attempts=3):
        """Повторная попытка проверки версии"""
        if attempt > max_attempts:
            self.set_status("Не удалось получить версию с сервера", 0)
            self.show_error("Ошибка получения версии")
            # Запускаем основную программу через некоторое время
            QTimer.singleShot(3000, self.run_main_app)
            return

        self.set_status(f"Повторная проверка ({attempt}/{max_attempts})...", 20)
        logger.info(f"Повторная попытка проверки версии: {attempt}/{max_attempts}")

        QTimer.singleShot(2000, lambda: self.start_check_update())

    def on_check_failed(self):
        """Обработка ошибки проверки"""
        # Используем атрибут для отслеживания попыток
        if not hasattr(self, 'check_attempts'):
            self.check_attempts = 1
        else:
            self.check_attempts += 1

        if self.check_attempts <= 3:
            self.set_status(f"Ошибка проверки ({self.check_attempts}/3)", 0)
            QTimer.singleShot(1500, self.start_check_update)
        else:
            self.set_status("Не удалось проверить обновления", 0)
            # Запускаем основную программу
            QTimer.singleShot(2000, self.run_main_app)

    def delete_files_safely(self, items_to_delete):
        """Безопасное удаление файлов в корзину с бэкапом в old_files_backup"""
        deleted_count = 0
        os.makedirs(self.old_files_dir, exist_ok=True)
        backup_dir = self.old_files_dir / "deletion_backup"
        logger.info(f"Бэкап папка для удаленных файлов: {backup_dir}")
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            
            for item_path in items_to_delete:
                clean_path = item_path.rstrip('/') if item_path.endswith('/') else item_path
                full_path = self.root_dir / clean_path
                
                if not os.path.exists(full_path):
                    logger.warning(f"Файл для удаления не существует: {item_path}")
                    continue
                    
                try:
                    backup_path = backup_dir / clean_path
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    
                    if os.path.isfile(full_path):
                        shutil.copy2(full_path, backup_path)
                        logger.info(f"Создан бэкап файла: {backup_path}")
                    elif os.path.isdir(full_path):
                        shutil.copytree(full_path, backup_path)
                        logger.info(f"Создан бэкап файла: {backup_path}")
                    
                    send2trash.send2trash(str(full_path))
                    logger.info(f"Файл перемещен в корзину: {item_path}")
                    deleted_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка удаления {item_path}: {e}")
                    
            logger.info(f"Перемещено в корзину {deleted_count} файлов/папок")
            return True
                
        except Exception as e:
            logger.error(f"Ошибка в процессе удаления: {e}")
            return False

    def collect_files_for_deletion(self, current_ver, target_ver, manifest):
        """Собирает все файлы для удаления между версиями"""
        try:
            version_objects = []
            version_to_str_map = {}
            
            for ver_str in manifest.keys():
                try:
                    ver_obj = version.parse(ver_str)
                    version_objects.append(ver_obj)
                    version_to_str_map[ver_obj] = ver_str
                except:
                    continue
            
            if not version_objects:
                logger.warning("В манифесте нет валидных версий")
                return []
            
            version_objects.sort()
            
            try:
                current_idx = version_objects.index(current_ver)
            except ValueError:
                logger.error(f"Текущая версия {current_ver} не найдена в манифесте")
                return []
            
            try:
                target_idx = version_objects.index(target_ver)
            except ValueError:
                logger.error(f"Целевая версия {target_ver} не найдена в манифесте")
                return []
            
            if target_idx <= current_idx:
                logger.info("Целевая версия не требует удаления файлов")
                return []
            
            all_deletions = set()
            
            for i in range(current_idx + 1, target_idx + 1):
                version_obj = version_objects[i]
                version_str = version_to_str_map[version_obj]
                
                deletions = manifest[version_str].get('deleted_files', [])
                if deletions:
                    if isinstance(deletions, str):
                        if deletions.strip():
                            deletion_list = [d.strip() for d in deletions.split(',') if d.strip()]
                            all_deletions.update(deletion_list)
                    elif isinstance(deletions, list):
                        all_deletions.update(deletions)
            
            logger.info(f"Найдено {len(all_deletions)} элементов для удаления")
            return list(all_deletions)
            
        except Exception as e:
            logger.error(f"Ошибка сбора файлов для удаления: {e}")
            return []
            
    def start_delta_download(self, files_to_update, manifest, target_version, skip_existing=False):
        """Запуск загрузки дельта-обновления"""
        if not files_to_update:
            logger.warning("Нет файлов для дельта-обновления")
            return
            
        self.set_status("Загрузка обновления...", 30)
        update_auth = UpdateAuthManager()
        self.download_thread = DeltaDownloadThread(files_to_update,
                                                   manifest,
                                                   target_version,
                                                   update_auth,
                                                   skip_existing)
        self.download_thread.download_complete.connect(self.on_delta_download_complete)
        self.download_thread.download_progress.connect(self.on_download_progress)
        self.download_thread.start()

    def on_delta_download_complete(self, temp_dir, success, skipped, error):
        """Обработка завершения дельта-загрузки"""
        logger.info(f"🎯 on_delta_download_complete ВЫЗВАН!")
        logger.info(f"📊 Параметры: temp_dir={temp_dir}, success={success}, skipped={skipped}, error={error}")
        
        if success:
            self.set_status("Установка обновления...", 80)
            self.install_delta_update(temp_dir)
        else:
            logger.error(f"❌ Ошибка загрузки: {error}")
            self.show_error("Ошибка загрузки обновления")

    def install_delta_update(self, temp_dir):
        """Установка дельта-обновления с резервным копированием"""
        try:
            # Очищаем старую папку бэкапа, но сохраняем deletion_backup
            if os.path.exists(self.old_files_dir):
                # Сохраняем папку deletion_backup если она есть
                deletion_backup_path = self.old_files_dir / "deletion_backup"
                
                # Временная папка для сохранения deletion_backup
                temp_backup_dir = None
                
                if os.path.exists(deletion_backup_path):
                    # Сохраняем deletion_backup во временную папку
                    temp_backup_dir = self.root_dir / "temp_deletion_backup"
                    if os.path.exists(temp_backup_dir):
                        shutil.rmtree(temp_backup_dir)
                    shutil.copytree(deletion_backup_path, temp_backup_dir)
                    logger.info("Сохранена папка deletion_backup")
                
                # Отправляем ВСЁ содержимое old_files_backup в корзину, кроме deletion_backup
                for item in os.listdir(self.old_files_dir):
                    item_path = os.path.join(self.old_files_dir, item)
                    
                    # Пропускаем папку deletion_backup (мы её уже сохранили)
                    if item == "deletion_backup":
                        continue
                        
                    try:
                        if os.path.isfile(item_path):
                            send2trash.send2trash(item_path)
                            logger.info(f"Файл отправлен в корзину: {item}")
                        elif os.path.isdir(item_path):
                            send2trash.send2trash(item_path)
                            logger.info(f"Папка отправлена в корзину: {item}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки в корзину {item}: {e}")
                        # Если не получилось в корзину, удаляем обычным способом
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                
                # Восстанавливаем deletion_backup из временной папки
                if temp_backup_dir and os.path.exists(temp_backup_dir):
                    if os.path.exists(deletion_backup_path):
                        shutil.rmtree(deletion_backup_path)
                    shutil.copytree(temp_backup_dir, deletion_backup_path)
                    shutil.rmtree(temp_backup_dir)
                    logger.info("Восстановлена папка deletion_backup")
                
                logger.info("Очищена старая папка бэкапа (содержимое отправлено в корзину)")
            
            # Создаем папку для резервных копий (она уже должна существовать)
            os.makedirs(self.old_files_dir, exist_ok=True)
            
            self.set_status("Создание резервных копий...", 85)
            
            # Создаем резервные копии файлов, которые будут обновлены
            backup_success = self.create_backup_files(temp_dir)
            
            if not backup_success:
                logger.error("Ошибка создания резервных копий")
                self.show_error("Ошибка создания резервных копий")
                return
            
            self.set_status("Копирование новых файлов...", 90)
            
            # Копируем новые файлы из временной папки
            copy_success = self.copy_delta_files(temp_dir)
            
            if copy_success:
                self.update_completed = True
                self.set_status("Обновление завершено", 100)
                QTimer.singleShot(1000, self.run_main_app)
            else:
                # Восстанавливаем из резервной копии при ошибке
                self.restore_from_backup()
                self.show_error("Ошибка установки обновления")
                
        except Exception as e:
            logger.error(f"Ошибка установки дельта-обновления: {e}")
            self.restore_from_backup()
            self.show_error("Ошибка установки обновления")

    def create_backup_files(self, temp_dir):
        """Создает резервные копии файлов, которые будут обновлены"""
        try:
            backup_count = 0
            
            # Получаем список файлов для обновления из временной папки
            for root, dirs, files in os.walk(temp_dir):
                for onefile in files:
                    
                    # ИСКЛЮЧАЕМ Update.exe из бэкапа
                    if onefile in ["Update.exe", "Assistant.exe"]:
                        logger.info(f"Пропускаем бэкап {onefile}")
                        continue
                    
                    relative_path = os.path.relpath(os.path.join(root, onefile), temp_dir)
                    source_file = os.path.join(self.root_dir, relative_path)
                    
                    # Если файл существует в основном приложении, создаем резервную копию
                    if os.path.exists(source_file):
                        backup_file = os.path.join(self.old_files_dir, relative_path)
                        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                        shutil.copy2(source_file, backup_file)
                        backup_count += 1
                        logger.info(f"Создана резервная копия: {backup_file}")
            
            # ОСОБАЯ ОБРАБОТКА ДЛЯ Assistant.exe
            assistant_temp_path = os.path.join(temp_dir, "Assistant.exe")
            if os.path.exists(assistant_temp_path):
                parent_dir = os.path.dirname(self.root_dir)
                assistant_source = os.path.join(parent_dir, "Assistant.exe")
                
                if os.path.exists(assistant_source):
                    backup_file = os.path.join(self.old_files_dir, "Assistant.exe")
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    shutil.copy2(assistant_source, backup_file)
                    backup_count += 1
                    logger.info(f"Создана резервная копия Assistant.exe: {backup_file}")
            
            logger.info(f"Создано резервных копий: {backup_count} файлов")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания резервных копий: {e}")
            return False

    def copy_delta_files(self, temp_dir):
        """Копирует новые файлы из временной папки в основное приложение"""
        try:
            logger.info(f"=== НАЧАЛО КОПИРОВАНИЯ ===")
            logger.info(f"Источник: {temp_dir}")
            logger.info(f"Назначение: {self.root_dir}")
            logger.info(f"Папка бэкапа: {self.old_files_dir}")
            
            copy_count = 0
            for root, dirs, files in os.walk(temp_dir):
                for onefile in files:
                    # ИСКЛЮЧАЕМ Update.exe из копирования
                    if onefile == "Update.exe":
                        logger.info(f"Пропускаем копирование Update.exe - будет обработан отдельно через swap-updater")
                        continue
                    
                    # ИСКЛЮЧАЕМ Assistant.exe из копирования в основную папку
                    if onefile == "Assistant.exe":
                        logger.info(f"Пропускаем копирование Assistant.exe - будет обработан отдельно")
                        continue
                    
                    relative_path = os.path.relpath(os.path.join(root, onefile), temp_dir)
                    source_file = os.path.join(root, onefile)
                    dest_file = os.path.join(self.root_dir, relative_path)
                    
                    # Логируем КАЖДЫЙ файл перед копированием
                    logger.info(f"Копируем: {source_file} -> {dest_file}")
                    
                    # Создаем директории если нужно
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    
                    # Копируем файл
                    shutil.copy2(source_file, dest_file)
                    copy_count += 1
                    logger.info(f"Обновлен файл: {dest_file}")
            
            # ОСОБАЯ ОБРАБОТКА ДЛЯ Assistant.exe - копируем на уровень выше
            assistant_source = os.path.join(temp_dir, "Assistant.exe")
            if os.path.exists(assistant_source):
                parent_dir = os.path.dirname(self.root_dir)
                assistant_dest = os.path.join(parent_dir, "Assistant.exe")
                shutil.copy2(assistant_source, assistant_dest)
                logger.info(f"Обновлен Assistant.exe: {assistant_dest}")
            
            logger.info(f"=== КОПИРОВАНИЕ ЗАВЕРШЕНО: {copy_count} файлов ===")
            return True
        except Exception as e:
            logger.error(f"Ошибка копирования дельта-файлов: {e}")
            return False
    
    def restore_from_backup(self):
        """Восстанавливает файлы из резервной копии, включая deletion_backup"""
        try:
            if not os.path.exists(self.old_files_dir):
                logger.info("Нет папки бэкапа для восстановления")
                return

            # 1. Восстанавливаем обычные бэкапы (из корня old_files_backup)
            regular_backup_restored = self._restore_regular_backups()
            
            # 2. Восстанавливаем удаленные файлы из deletion_backup
            deletion_backup_restored = self._restore_deletion_backup()
            
            # 3. Восстанавливаем Assistant.exe если есть
            assistant_restored = self._restore_assistant_exe()
            
            logger.info(f"Восстановление завершено: обычные={regular_backup_restored}, удаленные={deletion_backup_restored}, Assistant={assistant_restored}")
            
        except Exception as e:
            logger.error(f"Ошибка восстановления из резервной копии: {e}")

    def _restore_regular_backups(self):
        """Восстанавливает обычные бэкапы файлов"""
        try:
            restored_count = 0
            for root, dirs, files in os.walk(self.old_files_dir):
                # Пропускаем папку deletion_backup - её восстанавливаем отдельно
                if "deletion_backup" in root:
                    continue
                    
                for file in files:
                    if file == "Update.exe":
                        continue
                    
                    relative_path = os.path.relpath(os.path.join(root, file), self.old_files_dir)
                    backup_file = os.path.join(root, file)
                    dest_file = os.path.join(self.root_dir, relative_path)
                    
                    # Восстанавливаем файл
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(backup_file, dest_file)
                    logger.info(f"Восстановлен файл из резервной копии: {dest_file}")
                    restored_count += 1
            
            logger.info(f"Восстановлено {restored_count} обычных файлов")
            return restored_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка восстановления обычных бэкапов: {e}")
            return False

    def _restore_deletion_backup(self):
        """Восстанавливает файлы, которые были удалены в процессе обновления"""
        try:
            deletion_backup_path = self.old_files_dir / "deletion_backup"
            
            if not os.path.exists(deletion_backup_path):
                logger.info("Нет папки deletion_backup для восстановления")
                return False
            
            restored_count = 0
            for root, dirs, files in os.walk(deletion_backup_path):
                for file in files:
                    # Получаем относительный путь от deletion_backup
                    relative_to_deletion = os.path.relpath(os.path.join(root, file), deletion_backup_path)
                    backup_file = os.path.join(root, file)
                    dest_file = os.path.join(self.root_dir, relative_to_deletion)
                    
                    # Проверяем, существует ли уже файл в назначении
                    if os.path.exists(dest_file):
                        logger.warning(f"Файл уже существует, пропускаем восстановление: {dest_file}")
                        continue
                    
                    # Восстанавливаем файл
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(backup_file, dest_file)
                    logger.info(f"Восстановлен удаленный файл: {dest_file}")
                    restored_count += 1
            
            # Восстанавливаем папки (если они пустые после восстановления файлов)
            for root, dirs, files in os.walk(deletion_backup_path):
                for dir_name in dirs:
                    dir_relative = os.path.relpath(os.path.join(root, dir_name), deletion_backup_path)
                    dest_dir = os.path.join(self.root_dir, dir_relative)
                    
                    # Создаем папку если её нет
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir, exist_ok=True)
                        logger.info(f"Создана папка: {dest_dir}")
            
            logger.info(f"Восстановлено {restored_count} удаленных файлов из deletion_backup")
            return restored_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка восстановления из deletion_backup: {e}")
            return False

    def _restore_assistant_exe(self):
        """Восстанавливает Assistant.exe"""
        try:
            assistant_backup = os.path.join(self.old_files_dir, "Assistant.exe")
            if os.path.exists(assistant_backup):
                parent_dir = os.path.dirname(self.root_dir)
                assistant_dest = os.path.join(parent_dir, "Assistant.exe")
                
                # Проверяем, существует ли уже Assistant.exe
                if os.path.exists(assistant_dest):
                    # Создаем резервную копию текущего перед восстановлением
                    current_backup = assistant_dest + ".current_backup"
                    shutil.copy2(assistant_dest, current_backup)
                    logger.info(f"Создана резервная копия текущего Assistant.exe: {current_backup}")
                
                shutil.copy2(assistant_backup, assistant_dest)
                logger.info(f"Восстановлен Assistant.exe из резервной копии: {assistant_dest}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка восстановления Assistant.exe: {e}")
            return False

    def start_download(self, version):
        """Запуск загрузки из UI потока"""
        self.download_thread = DownloadThread("stable", version)
        self.download_thread.download_complete.connect(self.on_download_complete)
        self.download_thread.download_progress.connect(self.on_download_progress)
        self.download_thread.start()

    def on_download_progress(self, progress_percent):
        """Обработка прогресса загрузки"""
        # Преобразуем прогресс от 0-100% к диапазону 30-60%
        mapped_progress = 30 + int(progress_percent * 0.3)  # 30% + (30% от progress_percent)
        self.progress.setValue(mapped_progress)

    def on_download_complete(self, file_path, success, skipped, error):
        """Обработка завершения загрузки"""
        if success:
            # Устанавливаем 60% при завершении скачивания
            self.progress.setValue(60)
            self.set_status("Распаковка...", 60)
            self.start_unpack()
        else:
            self.set_status(f"Ошибка загрузки: {error}", 0)
            self.show_error("Ошибка загрузки")

    def start_unpack(self):
        """Запуск распаковки из UI потока"""
        self.unpack_thread = UnpackAppThread()
        self.unpack_thread.unpack_complete.connect(self.on_unpack_complete)
        self.unpack_thread.start()

    def on_unpack_complete(self, success):
        """Обработка завершения распаковки"""
        if success:
            self.set_status("Установка...", 80)
            self.install_update()
        else:
            self.set_status("Ошибка распаковки", 0)
            self.show_error("Ошибка распаковки")

    def install_update(self):
        """Синхронная установка в UI потоке"""
        try:
            # Удаляем старые файлы
            self.set_status("Удаление старых файлов...", 85)
            self.delete_old_files()

            # Копируем новые
            self.set_status("Копирование новых файлов...", 90)
            if self.copy_new_files():
                self.set_status("Обновление завершено", 100)
                QTimer.singleShot(1000, self.run_main_app)
            else:
                self.show_error("Ошибка установки")

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            self.show_error("Ошибка установки")
            
    def start_install_batch(self):
        """Запуск установки из уже скачанных файлов (batch режим)"""
        try:
            if hasattr(self, 'update_completed') and self.update_completed:
                logger.info("Обновление уже завершено, пропускаем проверку")
                return
        
            self.start_check_update()
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска batch установки: {e}")
            self.show_error("Ошибка установки")

    def start_install_from_existing(self):
        """Запуск установки из уже распакованного архива (режим --no-checked)"""
        self.set_status("Проверка распакованного обновления...", 60)

        # Проверяем, есть ли распакованные файлы
        unpack_thread = UnpackAppThread()
        if unpack_thread.is_already_unpacked():
            self.set_status("Начинаем установку...", 60)
            QTimer.singleShot(1000, self.install_update)
        else:
            self.set_status("Распаковка обновления...", 50)
            self.start_unpack()

    def run_main_app(self):
        """Запускает основную программу с флагом обновления и закрывает updater"""
        try:
            main_app = os.path.join(os.path.dirname(get_base_directory()), "Assistant.exe")
            if os.path.exists(main_app):
                # Запускаем с аргументом --updated
                subprocess.Popen([main_app, "--updated"])
                logger.info("Основная программа запущена после обновления")
            else:
                logger.error("Основная программа не найдена")

            # Даем время на запуск перед закрытием
            QTimer.singleShot(500, self.close)

        except Exception as e:
            logger.error(f"Ошибка запуска основной программы: {e}")
            self.close()

    def set_status(self, text, progress=None):
        self.label.setText(text)
        if progress is not None:
            self.progress.setValue(progress)

    def show_error(self, message):
        self.label.setText(message)
        self.error_button.show()
        self.button_spacer.changeSize(20, 0)

    def quit_application(self):
        sys.exit(1)

    def is_main_app_running(self):
        """Проверяет, запущена ли основная программа"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'Assistant.exe':
                return True
        return False

    def kill_main_app(self):
        """Завершает основную программу"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'Assistant.exe':
                try:
                    proc.kill()
                    proc.wait(timeout=5)  # Ждем завершения
                except:
                    pass

    def delete_old_files(self):
        preserved = ["user_settings", "update", "update_pack", "log"]

        # Удаление внутри self.root_dir (как раньше)
        for item in os.listdir(self.root_dir):
            full_path = os.path.join(self.root_dir, item)
            if os.path.isdir(full_path):
                if os.path.basename(full_path) not in preserved:
                    shutil.rmtree(full_path, ignore_errors=True)
            elif os.path.isfile(full_path):
                if os.path.basename(full_path) != "Assistant.exe":
                    try:
                        os.remove(full_path)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении старых файлов: {e}")
                        pass

        parent_dir = os.path.dirname(self.root_dir)  # Получаем родительскую папку
        assistant_exe_path = os.path.join(parent_dir, "Assistant.exe")

        if os.path.isfile(assistant_exe_path):
            try:
                os.remove(assistant_exe_path)
                logger.info(f"Удалён {assistant_exe_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления {assistant_exe_path}: {e}")

    def copy_new_files(self):
        try:
            # Путь к папке _internal внутри update_pack
            update_internal_dir = os.path.join(self.update_pack_dir, "_internal")

            # Копируем содержимое _internal из update_pack в целевую _internal, кроме user_settings
            if os.path.exists(update_internal_dir):
                for item in os.listdir(update_internal_dir):
                    # Пропускаем только в НЕ режиме установки
                    if not self.install_mode:
                        if item in ["user_settings", "Update.exe", "log"]:
                            continue

                    src = os.path.join(update_internal_dir, item)
                    dst = os.path.join(self.root_dir, item)

                    for _ in range(5):  # 5 попыток
                        try:
                            if os.path.isdir(src):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                            else:
                                if os.path.exists(dst):
                                    try:
                                        os.rename(dst, dst + ".old")
                                    except:
                                        pass
                                shutil.copy2(src, dst)
                            break
                        except Exception:
                            time.sleep(1)

            # Копируем Assistant.exe на уровень выше
            assistant_src = os.path.join(self.update_pack_dir, "Assistant.exe")
            if os.path.exists(assistant_src):
                parent_dir = os.path.dirname(self.root_dir)  # Родительская папка
                assistant_dst = os.path.join(parent_dir, "Assistant.exe")
                shutil.copy2(assistant_src, assistant_dst)

            return True
        except Exception as e:
            logger.error(f"Ошибка копирования: {e}")
            return False


def main():
    try:
        app = QApplication(sys.argv)
        window = UpdateWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Ошибка {e}")

if __name__ == "__main__":
    main()