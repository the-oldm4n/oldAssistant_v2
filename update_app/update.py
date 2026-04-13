import os
import send2trash
import win32api
import shutil
import subprocess
import time
import psutil
import sys
from packaging import version
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, Qt, QCursor
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from check_and_download import DownloadThread, VersionCheckThread
from utils import get_app_data_dir, get_path, get_base_directory, run_app_signal, logger
from config import update_name, domain, session, base_name


style_path = get_path("color.json")
from mygui.config import mygui_config
mygui_config.configure(colors_path=style_path, 
                 presets_path=get_path("for_gui", "color_presets"), 
                 custom_presets_path=get_path("for_gui", "presets"),
                 custom_selectors=get_path("for_gui", "custom_selectors.json"))
from mygui import main_apply_colors, CustomSvgWidget, SVGProgressBar
main_apply_colors.init()


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
                    'app_id': 'voxodium_updater',
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
        self.is_restart_app = "--restart-app" in sys.argv
        self.no_check_mode = "--no-checked" in sys.argv
        self.main_exe_path = None
        if "--target" in sys.argv:
            idx = sys.argv.index("--target")
            if idx + 1 < len(sys.argv):
                self.main_exe_path = sys.argv[idx + 1]
        
        if self.main_exe_path == None:
           self.main_exe_path = os.path.join(get_base_directory(), base_name)
        self.name_exe = os.path.basename(self.main_exe_path)

        logger.info(f"Path main exe {self.main_exe_path}")

        run_app_signal.run_main_app.connect(self.run_main_app)
        self.svg_path = get_path("icons", "logo.svg")
        self.icon_close_path = get_path("icons", "close.svg")
        self.style_manager = main_apply_colors
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()

        if self.is_restart_app:
            self.restart_main_app()
        else:
            self.start_update_process()

    def title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        self.drag_pos = None
        event.accept()

    def init_ui(self):
        try:
            self.drag_pos = None

            self.setWindowIcon(QIcon(get_path('icon.ico')))
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(300, 300)

            screen_geometry = self.screen().availableGeometry()
            self.move(
                (screen_geometry.width() - self.width()) // 2,
                (screen_geometry.height() - self.height()) // 2
            )
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)

            self.title_bar_widget = QWidget()
            self.title_bar_widget.setMaximumHeight(40)
            self.title_bar_widget.setObjectName("TitleBarLogin")
            self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
            self.title_bar_layout.setContentsMargins(5, 5, 5, 5)
            self.title_bar_layout.setSpacing(0)

            self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
            self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
            self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release

            self.close_button = QPushButton()
            self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.close_button.clicked.connect(self.close)
            self.close_button.setFixedSize(30, 30)
            self.close_button.setObjectName("TitleBarCloseBtnV2")
            self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_button)
            self.close_svg.setFixedSize(25, 25)
            self.close_svg.move(2, 2)
            self.close_svg.setStyleSheet("background: transparent;")
            self.title_bar_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)

            self.main_widget = QWidget()
            self.main_widget.setObjectName("WindowContainer")
            window_stack_layout = QVBoxLayout(self.main_widget)
            window_stack_layout.setContentsMargins(5, 5, 5, 5)

            content_layout = QVBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(0)

            self.svg_image = CustomSvgWidget(self.svg_path)
            self.svg_image.setFixedSize(120, 120)
            self.svg_image.setStyleSheet("background: transparent;")
            
            self.progress = SVGProgressBar(
                svg_widget=self.svg_image,
                style="circle",
                circle_size=180,
                show_text=False,
                line_width=5)
            content_layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

            self.label = QLabel("Завершение программы...")
            self.label.setStyleSheet("background: transparent; font-size:16px")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setWordWrap(True)
            content_layout.addWidget(self.label)

            content_layout.addStretch()

            window_stack_layout.addWidget(self.title_bar_widget)
            window_stack_layout.addLayout(content_layout)

            main_layout.addWidget(self.main_widget, 1)
        except Exception as e:
            logger.error(f"Ошибка init_ui: {e}")

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            self.style_manager.apply_color_svg(self.svg_image)
            self.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")
            self.style_manager.apply_progressbar(widget=self.progress)

            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):
                    selector = widget
                else:
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"

            self.setStyleSheet(style_sheet)
            self.main_widget.setStyleSheet("""border-radius:20px""")
        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def restart_main_app(self):
        if self.is_main_app_running():
            self.kill_main_app()
        QTimer.singleShot(100, self.run_main_app)

    def start_update_process(self):
        if self.check_thread is not None:
            return

        self.label.setText("Проверка...")

        if self.is_main_app_running():
            self.set_status("Закрытие программы...", 0)
            self.kill_main_app()
            time.sleep(2)

        if self.no_check_mode:
            self.set_status("Пропуск проверки обновлений...", 30)
            QTimer.singleShot(100, self.install_update)
        else:
            self.start_check_update()

    def start_check_update(self):
        """Запуск проверки обновлений из UI потока"""
        self.set_status("Поиск обновлений...", 10)

        self.check_thread = VersionCheckThread()
        self.check_thread.version_checked.connect(self.on_version_checked)
        self.check_thread.check_failed.connect(self.on_check_failed)
        self.check_thread.start()

    def get_current_version(self):
        try:
            if not self.main_exe_path:
                logger.warning("main_exe_path не задан")
                return None

            if not os.path.exists(self.main_exe_path):
                logger.warning(f"Файл не найден: {self.main_exe_path}")
                return None

            if not os.path.isfile(self.main_exe_path):
                logger.warning(f"Путь не указывает на файл: {self.main_exe_path}")
                return None

            version_info = win32api.GetFileVersionInfo(self.main_exe_path, "\\")
            ms = version_info['FileVersionMS']
            ls = version_info['FileVersionLS']
            file_version = f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"
            return file_version

        except Exception as e:
            logger.error(f"Ошибка получения версии из {self.main_exe_path}: {e}")
            return None

    def on_version_checked(self, stable_version):
        try:
            # УСПЕХ → сбросить счётчик
            if hasattr(self, '_retry_count'):
                delattr(self, '_retry_count')

            self.version = self.get_current_version() or "0.0.0"
            logger.info(f"[UPD] Текущая версия - {self.version}")
            logger.info(f"[UPD] Найденная версия - {stable_version!r}")

            current_version = version.parse(self.version)

            if not stable_version or not str(stable_version).strip():
                raise ValueError("Пустая версия")

            stable_ver = version.parse(str(stable_version).strip())

            if stable_ver > current_version:
                self.set_status("Скачивание обновления...", 30)
                self.start_download()
            else:
                self.set_status("Установлена последняя версия", 100)
                QTimer.singleShot(50, self.run_main_app)

        except Exception as e:
            logger.error(f"Ошибка при обработке версий: {e}")
            self.retry_version_check()

    def on_check_failed(self):
        """Вызывается при сетевой ошибке или таймауте"""
        self.retry_version_check()

    def retry_version_check(self, max_attempts=3):
        if not hasattr(self, '_retry_count'):
            self._retry_count = 1
        else:
            self._retry_count += 1

        if self._retry_count > max_attempts:
            self.set_status("Не удалось проверить обновления", 0)
            self.show_error("Ошибка подключения")
            QTimer.singleShot(200, self.run_main_app)
            return

        self.set_status(f"Повторная проверка ({self._retry_count}/{max_attempts})...", 20)
        logger.info(f"Повторная попытка: {self._retry_count}/{max_attempts}")
        QTimer.singleShot(200, self.start_check_update)

    def start_download(self):
        """Запуск загрузки из UI потока"""
        self.download_thread = DownloadThread("stable")
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
            self.set_status("Подготовка...", 60)
            self.install_update()
        else:
            self.set_status(f"Ошибка загрузки: {error}", 0)
            self.show_error("Ошибка загрузки")

    def install_update(self):
        """Синхронная установка в UI потоке"""
        try:
            update_file = os.path.join(get_app_data_dir(), "update", update_name)
            self.set_status("Копирование...", 60)
            logger.info(f"Для реплейса {self.main_exe_path}; {update_file}")
            if self.replace_exe(self.main_exe_path, update_file):
                self.set_status("Обновление завершено", 100)
                QTimer.singleShot(100, self.run_main_app)
            else:
                self.show_error("Ошибка установки")

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            self.show_error("Ошибка установки")

    def replace_exe(self, old_exe_path: str, new_exe_path: str, target_name: str = base_name):
        """
        Заменяет old_exe_path новым файлом из new_exe_path,
        переименовывая его в target_name в той же папке, что и old_exe_path.
        
        Предполагается, что old_exe_path НЕ используется (процесс завершён).
        """
        if not os.path.exists(new_exe_path):
            raise FileNotFoundError(f"Новый файл не найден: {new_exe_path}")

        target_dir = os.path.dirname(old_exe_path)
        final_path = os.path.join(target_dir, target_name)

        # Удаляем старый файл, если существует
        if os.path.exists(old_exe_path):
            send2trash.send2trash(old_exe_path)

        # Переименовываем/перемещаем новый файл на место старого
        shutil.move(new_exe_path, final_path)

        return True

    def run_main_app(self):
        """Запускает основную программу с флагом обновления и закрывает updater"""
        try:
            main_app = self.main_exe_path
            if os.path.exists(main_app):
                subprocess.Popen([main_app, "--updated"])
                logger.info("Основная программа запущена после обновления")
            else:
                logger.error("Основная программа не найдена")

            QTimer.singleShot(200, self.close)

        except Exception as e:
            logger.error(f"Ошибка запуска основной программы: {e}")
            self.close()

    def set_status(self, text, progress=None):
        self.label.setText(text)
        if progress is not None:
            self.progress.setValue(progress)

    def show_error(self, message):
        self.label.setText(message)

    def quit_application(self):
        sys.exit(1)

    def is_main_app_running(self):
        """Проверяет, запущена ли основная программа"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == self.name_exe:
                return True
        return False

    def kill_main_app(self):
        """Завершает основную программу"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == self.name_exe:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except:
                    pass


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