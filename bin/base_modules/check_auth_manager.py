import json
import os

from bin.base_modules.session_manager import UserSessionManager
from bin.base_modules.update_dialog import UpdateApp
import requests
from PySide6.QtWidgets import QApplication, QMenu, QLabel
from PySide6.QtCore import Qt, QRect, QObject, QPropertyAnimation, QEasingCurve, QPoint, QUrl 
from PySide6.QtGui import QMouseEvent, QPixmap, QPainter, QPainterPath, QDesktopServices
from bin.base_modules.config_manager import get_config_value, set_config_value
from bin.base_modules.login_widget import LoginWindow
from mygui import sidebar_animated_signal
from log_config import logger
from config import domain


class CheckAuthManager(QObject):
    """
    
    """
    def __init__(self, auth_manager, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.auth = auth_manager
        self.session_manager = UserSessionManager()

    def open_login(self, message=""):
        try:
            self.login_window = LoginWindow(auth=self.auth, message=message)
            self.login_window.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.login_window.show()
            
            self.login_window.login_successful.connect(self.on_login_success)
            self.login_window.login_cancelled.connect(self.on_login_cancelled)
            
        except Exception as e:
            logger.error(f"[MAIN] Ошибка при запуске окна авторизации: {e}")

    def on_login_success(self):
        """Обработка успешного логина"""
        try:
            if self.auth.is_guest():
                self.session_manager.set_local_session()
            elif self.auth.user_data:
                username = self.auth.user_data['username']
                self.session_manager.set_user_session(username)
            else:
                raise RuntimeError("Неизвестное состояние авторизации")

            self.set_user_data(self.auth.user_data)
            self.main.check_up()
            
        except ValueError as e:
            self.show_message(str(e), "Ошибка", "error")
            self.open_login()

    def on_login_cancelled(self):
        """Обработка отмены логина"""
        logger.info("[MAIN] Логин отменен")
        self.close()
        
    def check_auth(self, auth):
        self.auth = auth
        
        status, message = self.auth.is_authenticated()
        if status:
            if self.auth.is_guest():
                logger.info("[MAIN] Автоматический вход: Гость")
                logger.info(f"[MAIN] Результат аутентификации: {message}")
                self.session_manager.set_local_session()
            else:
                logger.info(f"[MAIN] Автоматический вход: {self.auth.user_data['username']}")
                self.session_manager.set_user_session(self.auth.user_data['username'])
            
            self.set_user_data(self.auth.user_data)
            self.main.check_up()
        else:
           self.open_login(message)

    def on_profile_click(self, event):
        """Обработчик клика по профилю"""
        menu = QMenu(self.main)

        menu.addAction("Профиль", self.open_user_profile)
        menu.addAction("Выйти", self.logout_user)
        
        # Показываем меню под виджетом профиля
        menu.exec(self.main.user_profile_widget.mapToGlobal(
            QPoint(0, self.main.user_profile_widget.height())
        ))
               
    def set_user_data(self, user_data):
            """Установить данные пользователя"""
            self.main.user_data = user_data
            logger.info(f"[MAIN] Данные пользователя установлены: {user_data['username']}")
    
    def clear_user_data(self):
        """Очистить данные пользователя"""
        self.main.user_data = None
        self.set_default_avatar_svg()
                
    def update_user_profile(self, user_data=None):
        """Обновить профиль пользователя (можно вызывать без параметров)"""
        logger.info(f"[MAIN] Обновление профиля...")
        data = user_data or self.main.user_data
            
        if data and data.get('avatar') is None:
            return self.set_default_avatar_svg()
        
        if data and 'avatar' in data:
            self.load_user_avatar(data['avatar'])
        else:
            self.set_default_avatar_svg()

    def set_default_avatar_svg(self):
        """Установить SVG аватарку по умолчанию"""
        if hasattr(self.main, 'avatar_svg'):
            self.style_manager.apply_color_svg(self.main.avatar_svg)

    def load_user_avatar(self, avatar_path):
        """Загрузить пользовательскую аватарку"""
        try:
            avatar_url = f"{self.auth.base_url}/static/{avatar_path}"
            response = requests.get(avatar_url, timeout=10, verify=False)
            
            if response.status_code == 200:
                if hasattr(self.main, 'avatar_svg'):
                    self.main.avatar_svg.hide()

                if not hasattr(self, 'avatar_pixmap_label'):
                    self.avatar_pixmap_label = QLabel()
                    self.avatar_pixmap_label.setFixedSize(30, 30)
                    self.avatar_pixmap_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    self.avatar_pixmap_label.setStyleSheet("background: transparent;")
                    self.avatar_pixmap_label.setAlignment(Qt.AlignCenter)
                    avatar_index = self.main.user_profile_layout.indexOf(self.main.avatar_svg)
                    self.main.user_profile_layout.insertWidget(avatar_index, self.avatar_pixmap_label)
                else:
                    self.avatar_pixmap_label.show()

                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                rounded_pixmap = self.create_rounded_pixmap(pixmap, 30)
                self.avatar_pixmap_label.setPixmap(rounded_pixmap)
                
            else:
                logger.error(f"[MAIN] Ошибка загрузки аватара: {response.status_code}")
                self.set_default_avatar_svg()
                
        except Exception as e:
            logger.error(f"[MAIN] Ошибка загрузки аватара: {e}")
            self.set_default_avatar_svg()

    def create_rounded_pixmap(self, pixmap, size):
        if pixmap.isNull():
            return QPixmap()

        img_ratio = pixmap.width() / pixmap.height()
        circle_ratio = size / size
        
        if img_ratio > circle_ratio:
            scaled_height = size
            scaled_width = int(size * img_ratio)
        else:
            scaled_width = size
            scaled_height = int(size / img_ratio)
        
        scaled_pixmap = pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        x = (size - scaled_width) // 2
        y = (size - scaled_height) // 2
        
        rounded = QPixmap(size, size)
        rounded.fill(Qt.transparent)
        
        painter = QPainter(rounded)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
        
        return rounded
    
    def open_user_profile(self):
        username = self.main.user_data["username"]
        QDesktopServices.openUrl(QUrl(f"{domain}/user/{username}"))

    def refresh_user_data(self):
        pass
    
    def logout_user(self):
        """Выход с возвратом к LoginWindow"""
        logger.info("[MAIN] Выход из системы...")
        
        # Очищаем данные
        self.main.user_data = None
        self.auth.logout()

        self.restart_application()

    def restart_application(self):
        """Перезапуск приложения"""
        self.restart_dialog = UpdateApp(self.main)
        self.restart_dialog.restart_app()