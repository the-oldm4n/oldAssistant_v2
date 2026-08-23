from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit
from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtGui import QCursor
from mygui import CustomSvgWidget
from bin.base_modules.register_module import AuthManager
from path_builder import get_path
from log_config import logger
from mygui import main_apply_colors
from config import domain


class LoginWindow(QWidget):
    """
    Окно регистрации и авторизации в системе
    """
    # Добавляем сигналы
    login_successful = Signal()
    login_cancelled = Signal()

    def __init__(self, parent=None, auth=None, message=None):
        super().__init__(parent)
        self.auth = auth
        if not self.auth:
            self.auth = AuthManager(domain)
        self.style_manager = main_apply_colors
        self.svg_path = get_path("bin", "icons", "logo-app.svg")
        self.svg_icon_path = get_path("bin", "icons", "logo-owlapp.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.is_login_mode = False
        self.is_2fa_mode = False
        self.is_guest_access = True # <----------- Manage visibility of button 'login as guest'
        self.init_ui()
        self.apply_styles()
        self.switch_mode()
        if message:
            self.show_message(text=message, message_type="warning")

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
        self.drag_pos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(350, 730)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        
        # Основной layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.title_bar_widget = QWidget()
        self.title_bar_widget.setMaximumHeight(50)
        self.title_bar_widget.setObjectName("TitleBarLogin")
        self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
        self.title_bar_layout.setContentsMargins(10, 10, 10, 10)
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
        self.main_widget.setObjectName("LoginContainer")
        window_stack_layout = QVBoxLayout(self.main_widget)
        window_stack_layout.setContentsMargins(0, 0, 0, 0)
        window_stack_layout.setSpacing(0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(10)
        
        # Добавляем логотип
        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(80, 80)
        self.svg_image.setStyleSheet("background: transparent; border: none;")
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addSpacing(10)

        # Заголовок окна (будет меняться)
        self.title_label = QLabel("Создание аккаунта")
        self.title_label.setStyleSheet("""
            background: transparent; 
            font-size: 20px; 
            font-weight: bold;
            margin-bottom: 10px;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.title_label)
 
        self.notice_widget = QWidget()
        self.notice_widget.setObjectName("NoticeWidget")
        self.notice_widget.setFixedHeight(60)
        self.notice_widget.show()
        
        notice_layout = QHBoxLayout(self.notice_widget)
        notice_layout.setContentsMargins(15, 10, 15, 10)
        
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color: white; font-size: 14px; background: transparent;")
        notice_layout.addWidget(self.notice_label)
        
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: transparent;
                border: none;
            }
        """)
        
        content_layout.addWidget(self.notice_widget)

        # Поля формы
        self.label_username = QLabel("Логин")
        self.label_username.setStyleSheet("background: transparent;")
        self.field_username = QLineEdit()
        self.field_username.setStyleSheet("background: transparent;")
        self.field_username.setPlaceholderText("Введите логин")
        content_layout.addWidget(self.label_username, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.field_username)
        
        # Поле email (будет скрыто в режиме авторизации)
        self.label_email = QLabel("Почта")
        self.label_email.setStyleSheet("background: transparent;")
        self.field_email = QLineEdit()
        self.field_email.setStyleSheet("background: transparent;")
        self.field_email.setPlaceholderText("Введите email")
        content_layout.addWidget(self.label_email, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.field_email)
        
        self.label_password = QLabel("Пароль")
        self.label_password.setStyleSheet("background: transparent;")
        self.password_container = self.create_password_field("Введите пароль")
        self.password_container.setStyleSheet("background: transparent;")
        content_layout.addWidget(self.label_password, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.password_container)
        
        # Поле повторения пароля (будет скрыто в режиме авторизации)
        self.label_2password = QLabel("Повторите пароль")
        self.label_2password.setStyleSheet("background: transparent;")
        self.password2_container  = self.create_password_field("Повторите пароль")
        self.password2_container .setStyleSheet("background: transparent;")
        content_layout.addWidget(self.label_2password, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.password2_container )
        
        self.label_2fa = QLabel("Код двухфакторной аутентификации")
        self.label_2fa.setStyleSheet("background: transparent; font-weight: bold;")
        self.field_2fa = QLineEdit()
        self.field_2fa.setStyleSheet("background: transparent;")
        self.field_2fa.setPlaceholderText("Введите 6-значный код с почты")
        self.field_2fa.setMaxLength(6)
        
        self.resend_2fa_btn = QPushButton("Отправить код повторно")
        self.resend_2fa_btn.clicked.connect(self.resend_2fa_code)
        self.resend_2fa_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)

        self.hide_2fa_fields()
        
        content_layout.addWidget(self.label_2fa)
        content_layout.addWidget(self.field_2fa)
        content_layout.addWidget(self.resend_2fa_btn)
        
        content_layout.addSpacing(20)
        
        self.submit_btn = QPushButton("Создать аккаунт")
        self.submit_btn.clicked.connect(self.handle_submit)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel_login)
        
        self.back_btn = QPushButton("Назад")
        self.back_btn.clicked.connect(self.back_to_login)
        self.back_btn.hide()

        if self.is_guest_access:
            self.local_launch_btn = QPushButton("Локальный запуск (Гость)")
            self.local_launch_btn.clicked.connect(self.login_as_guest)
            self.local_launch_btn.hide()
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.submit_btn)
        
        content_layout.addLayout(buttons_layout)
        content_layout.addWidget(self.back_btn)
        if self.is_guest_access:
            content_layout.addWidget(self.local_launch_btn)

        content_layout.addStretch()

        self.switch_mode_label = QLabel(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Уже есть аккаунт? <a href='login'>Войти</a>"
        )
        self.switch_mode_label.setStyleSheet("background: transparent; margin-top: 10px;")
        self.switch_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.switch_mode_label.setOpenExternalLinks(False)
        self.switch_mode_label.linkActivated.connect(self.switch_mode)
        content_layout.addWidget(self.switch_mode_label)

        logo_layout = QHBoxLayout()

        logo_layout.addStretch()
        self.svg_icon = CustomSvgWidget(self.svg_icon_path)
        self.svg_icon.setFixedSize(20, 20)
        self.svg_icon.setStyleSheet("background: transparent; border: none;")
        logo_layout.addWidget(self.svg_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        link_label = QLabel()
        link_label.setText('''
            <a href="https://owl-app.ru" 
            style="color: #1E88E5; text-decoration: none; font-size: 13px;">
            owl-app.ru
            </a>
        ''')
        link_label.setStyleSheet("background: transparent;")
        link_label.setOpenExternalLinks(True)
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        logo_layout.addWidget(link_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        logo_layout.addStretch()
        content_layout.addLayout(logo_layout)
        
        
        window_stack_layout.addWidget(self.title_bar_widget)
        window_stack_layout.addLayout(content_layout)

        main_layout.addWidget(self.main_widget, 1)
        
    def login_as_guest(self):
        """Вход в режиме гостя"""
        logger.info("Вход как гость")

        guest_data = {
            'id': -1,
            'username': 'local_storage',
            'display_name': 'Username',
            'email_verified': False,
            'avatar': None,
            'is_guest': True
        }

        self.auth.user_data = guest_data
        self.auth.token = None

        self.auth._save_auth_data()

        self.show_message("Локальный запуск", "info")

        QTimer.singleShot(1000, self.finish_guest_login)
        
    def hide_2fa_fields(self):
        """Скрыть поля 2FA"""
        self.label_2fa.hide()
        self.field_2fa.hide()
        self.resend_2fa_btn.hide()

    def show_2fa_fields(self):
        """Показать поля 2FA"""
        self.label_2fa.show()
        self.field_2fa.show()
        self.resend_2fa_btn.show()

    def switch_to_2fa_mode(self):
        """Переключиться в режим 2FA"""
        self.is_2fa_mode = True
        
        # Скрываем основные поля
        self.label_username.hide()
        self.field_username.hide()
        self.label_email.hide()
        self.field_email.hide()
        self.label_password.hide()
        self.password_container.hide()
        self.label_2password.hide()
        self.password2_container.hide()
        if hasattr(self, 'local_launch_btn'):
            self.local_launch_btn.hide()
        self.switch_mode_label.hide()
        
        # Показываем 2FA поля
        self.show_2fa_fields()
        
        # Обновляем кнопки
        self.title_label.setText("Аутентификация")
        self.submit_btn.setText("Подтвердить")
        self.cancel_btn.hide()
        self.back_btn.show()
        
        # Обновляем сообщение
        self.show_message("Код отправлен на вашу почту", "info")

    def back_to_login(self):
        """Вернуться к обычному логину"""
        self.is_2fa_mode = False
        
        # Скрываем 2FA поля
        self.hide_2fa_fields()
        
        self.title_label.setText("Вход в аккаунт")
        self.label_email.show()
        self.field_email.show()
        self.label_password.show()
        self.password_container.show()
            
        # Обновляем кнопки
        self.back_btn.hide()
        self.cancel_btn.show()
        if hasattr(self, 'local_launch_btn'):
            self.local_launch_btn.show()
        self.switch_mode_label.show()
        self.setFixedSize(350, 620)

    def handle_submit(self):
        """Обработка отправки формы"""
        try:
            if self.is_2fa_mode:
                self.handle_2fa_verification()
            elif self.is_login_mode:
                self.handle_login()
            else:
                self.handle_register()
                
        except Exception as e:
            logger.error(f"Ошибка при обработке формы: {e}")
            self.show_message(f"Ошибка: {e}", "error")

    def handle_2fa_verification(self):
        """Обработка верификации 2FA кода"""
        code = self.field_2fa.text().strip()
        
        if len(code) != 6 or not code.isdigit():
            self.show_message("Введите 6-значный код", "error")
            return
            
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Проверка...")
        
        success, message = self.auth.verify_2fa(code)
        
        if success:
            self.show_message("Успешная верификация!", "info")
            self.login_successful.emit()
            self.close()
        else:
            self.show_message(f"Ошибка: {message}", "error")
            
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Подтвердить")

    def resend_2fa_code(self):
        """Повторная отправка кода 2FA"""
        if not self.auth.temp_2fa_token:
            self.show_message("Нет активной сессии 2FA", "error")
            return
        
        logger.info(f"Запрос повторной отправки с токеном: {self.auth.temp_2fa_token}")
            
        self.resend_2fa_btn.setEnabled(False)
        self.resend_2fa_btn.setText("Отправка...")
        
        success, message = self.auth.resend_2fa_code()
        
        if success:
            self.show_message("✅ Код отправлен повторно!", "info")
        else:
            self.show_message(f"❌ {message}", "error")
            # Если токен невалидный, возвращаем к логину
            if "неверный" in message.lower() or "истек" in message.lower():
                self.back_to_login()
                
        self.resend_2fa_btn.setEnabled(True)
        self.resend_2fa_btn.setText("Отправить код повторно")
        
    def finish_guest_login(self):
        """Завершить вход как гость"""
        self.login_successful.emit()
        self.close()

    def switch_mode(self):
        """Переключение между режимами регистрации и авторизации"""
        self.is_login_mode = not self.is_login_mode
        
        if self.is_login_mode:
            # Переключаемся в режим авторизации
            self.title_label.setText("Вход в аккаунт")
            self.submit_btn.setText("Войти")
            self.switch_mode_label.setText(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Нет аккаунта? <a href='register'>Зарегистрироваться</a>")
            
            # Скрываем ненужные поля
            self.label_username.hide()
            self.field_username.hide()
            self.label_2password.hide()
            self.password2_container.hide()
            self.setFixedSize(350, 620)

            if hasattr(self, 'local_launch_btn'):
                self.local_launch_btn.show()
            
        else:
            # Переключаемся в режим регистрации
            self.title_label.setText("Создание аккаунта")
            self.submit_btn.setText("Создать аккаунт")
            self.switch_mode_label.setText(
            "<style>"
            "a { color: #1E88E5; text-decoration: none; }"
            "a:hover { color: #0D47A1; text-decoration: underline; }"
            "</style>"
            "Уже есть аккаунт? <a href='login'>Войти</a>")
            
            # Показываем все поля
            self.label_username.show()
            self.field_username.show()
            self.label_2password.show()
            self.password2_container.show()
            self.setFixedSize(350, 730)

            if hasattr(self, 'local_launch_btn'):
                self.local_launch_btn.hide()

        self.clear_fields()

    def clear_fields(self):
        """Очистка полей ввода"""
        self.field_username.clear()
        self.field_email.clear()
        self.password_container.password_field.clear()
        self.password2_container.password_field.clear()

    def handle_register(self):
        """Обработка регистрации"""
        username = self.field_username.text().strip()
        email = self.field_email.text().strip()
        password = self.password_container.password_field.text()
        password_confirm = self.password2_container.password_field.text()

        # Валидация
        if not username:
            self.show_message("Введите логин", "error")
            return

        if not email or "@" not in email:
            self.show_message("Введите корректный email", "error")
            return

        if not password:
            self.show_message("Введите пароль", "error")
            return

        if len(password) < 6:
            self.show_message("Пароль должен содержать минимум 6 символов", "error")
            return

        if password != password_confirm:
            self.show_message("Пароли не совпадают", "error")
            return

        # Блокируем кнопку
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Регистрация...")

        # Регистрация через AuthManager
        success, result = self.auth.register(username, email, password)
        
        if success:
            # ⚠️ РЕГИСТРАЦИЯ УСПЕШНА - ПЕРЕКЛЮЧАЕМ НА АВТОРИЗАЦИЮ
            message = result['message'] if isinstance(result, dict) else result
            self.show_message(message, "success")
            
            # Сохраняем email для возможности повторной отправки
            self.pending_verification_email = email
            
            # Переключаемся на режим авторизации
            QTimer.singleShot(1500, self.switch_to_login_mode)
        else:
            self.show_message(f"Ошибка регистрации: {result}", "error")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Создать аккаунт")

    def switch_to_login_mode(self):
        """Переключиться на режим авторизации после регистрации"""
        self.switch_mode()
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Войти")
        
        # ⚠️ Добавляем кнопку повторной отправки письма
        self.add_resend_verification_button()
        self.setFixedSize(350, 660)

    def add_resend_verification_button(self):
        """Добавить кнопку повторной отправки письма подтверждения"""
        if hasattr(self, 'resend_btn'):
            self.resend_btn.show()
            return
            
        self.resend_btn = QPushButton("Отправить письмо подтверждения повторно")
        self.resend_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0078D7;
                border: 1px solid #0078D7;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #0078D7;
                color: white;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
                border: 1px solid #cccccc;
            }
        """)
        self.resend_btn.clicked.connect(self.resend_verification)
        
        # Добавляем кнопку в layout (перед switch_mode_label)
        content_layout = self.main_widget.layout()
        index = content_layout.indexOf(self.switch_mode_label)
        content_layout.insertWidget(index, self.resend_btn)

    def resend_verification(self):
        """Повторно отправить письмо подтверждения"""
        if not hasattr(self, 'pending_verification_email'):
            self.show_message("Email не найден", "error")
            return
            
        # Блокируем кнопку на 40 секунд
        self.resend_btn.setEnabled(False)
        self.resend_btn.setText("Отправка...")
        
        success, message = self.auth.resend_verification_email(self.pending_verification_email)
        
        if success:
            self.show_message("Письмо отправлено!", "success")
            # ⚠️ Таймер разблокировки кнопки через 40 секунд
            QTimer.singleShot(40000, self.enable_resend_button)
            
            # Обновляем счетчик на кнопке
            self.start_resend_countdown()
        else:
            self.show_message(f"Ошибка: {message}", "error")
            self.resend_btn.setEnabled(True)
            self.resend_btn.setText("Отправить письмо подтверждения повторно")

    def start_resend_countdown(self):
        """Запустить отсчет времени до возможности повторной отправки"""
        self.countdown_seconds = 40
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_resend_button)
        self.countdown_timer.start(1000)
        self.update_resend_button()

    def update_resend_button(self):
        """Обновить текст кнопки с отсчетом"""
        if self.countdown_seconds > 0:
            self.resend_btn.setText(f"Повторная отправка через {self.countdown_seconds}с")
            self.countdown_seconds -= 1
        else:
            self.countdown_timer.stop()
            self.enable_resend_button()

    def enable_resend_button(self):
        """Разблокировать кнопку повторной отправки"""
        self.resend_btn.setEnabled(True)
        self.resend_btn.setText("Отправить письмо подтверждения повторно")

    def handle_login(self):
        """Обработка авторизации"""
        try:
            email = self.field_email.text().strip()
            password = self.password_container.password_field.text()

            # Валидация
            if not self.auth.is_valid_email(email):
                self.show_message("Некорректная почта", "error")
                return
            
            if not email:
                self.show_message("Введите почту", "error")
                return

            if len(email) > 100:
                self.show_message("Email должен содержать не более 100 символов", "error")
                return

            if not password:
                self.show_message("Введите пароль", "error")
                return
            
            if len(password) < 6:
                self.show_message("Пароль должен содержать не менее 6 символов", "error")
                return

            if len(password) > 50:
                self.show_message("Пароль должен содержать не более 50 символов", "error")
                return

            logger.info(f"Начинаем авторизацию для: {email}")
            
            # Блокируем кнопку на время авторизации
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("Вход...")

            # Авторизация через AuthManager
            result, message = self.auth.login(email, password)
            
            logger.info(f"Результат авторизации: {result}, {message}")
            
            if result == True:
                # Обычный вход без 2FA
                self.show_message("Успешный вход!", "info")
                self.login_successful.emit()
                self.close()
            elif result == '2fa_required':
                # Требуется 2FA - показываем окно верификации
                self.show_message("Требуется двухфакторная аутентификация", "info")
                logger.info(f"Переход в режим 2FA с токеном: {self.auth.temp_2fa_token}")
                self.switch_to_2fa_mode()
            else:
                # Ошибка входа
                self.show_message(f"Ошибка входа: {message}", "error")

        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}")
            self.show_message(f"Неожиданная ошибка: {e}", "error")
        finally:
            # Разблокируем кнопку
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Войти")

    def cancel_login(self):
        """Обработка отмены"""
        self.login_cancelled.emit()
        self.close()

    def on_2fa_success(self):
        """Обработка успешной верификации 2FA"""
        self.show_message("Успешный вход!", "info")
        self.login_successful.emit()
        self.close()

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            if hasattr(self, 'svg_image'):
                self.style_manager.apply_color_svg(self.svg_image)

            if hasattr(self, 'svg_icon'):
                self.style_manager.apply_color_svg(self.svg_icon)

            if hasattr(self, 'close_svg'):
                self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#ff0000")

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
            self.main_widget.setStyleSheet("border-radius: 20px;")
        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def cancel_login(self):
        """Обработка отмены"""
        self.login_cancelled.emit()
        self.close()

    def setup_notice_widget(self):
        """Создать виджет уведомления"""
        self.notice_widget = QWidget(self)
        self.notice_widget.setObjectName("NoticeWidget")
        self.notice_widget.setFixedSize(300, 50)
        self.notice_widget.hide()
        
        layout = QHBoxLayout(self.notice_widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.notice_label)
        
        # Позиционируем вверху
        self.notice_widget.move(25, 25)
        
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: #F44336;
                border-radius: 8px;
                border: 1px solid #D32F2F;
            }
        """)

    def show_message(self, text, message_type="error"):
        """Показать уведомление"""
        try:
            self.notice_label.setText(text)
            
            # Меняем цвет в зависимости от типа
            colors = {
                "info": "#2196F3",
                "success": "#4CAF50", 
                "warning": "#FF9800",
                "error": "#F44336"
            }
            color = colors.get(message_type, "#F44336")
            
            # Показываем с цветом
            self.notice_widget.setStyleSheet(f"""
                #NoticeWidget {{
                    background: {color};
                    border-radius: 8px;
                    border: 1px solid {color};
                }}
            """)
            
            # Через 3 секунды возвращаем прозрачный стиль
            QTimer.singleShot(3000, self.hide_notice)
            
        except Exception as e:
            logger.error(f"Ошибка при показе уведомления: {e}")

    def hide_notice(self):
        """Скрыть уведомление (оставить место)"""
        self.notice_widget.setStyleSheet("""
            #NoticeWidget {
                background: transparent;
                border: none;
            }
        """)
        self.notice_label.clear() 
        
    def create_password_field(self, placeholder):
        """Создать поле пароля с кнопкой глазком рядом"""
        # Создаем контейнер для поля и кнопки
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Поле ввода
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(placeholder)
        field.setStyleSheet("background: transparent;")
        
        # Кнопка глазок
        toggle_btn = QPushButton()
        toggle_btn.setObjectName("ToggleVisiblePSWD")
        toggle_btn.setFixedSize(33, 33)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;

            }
            QPushButton:hover {
                background: rgba(100,100,100,0.4);
            }
        """)
        
        # SVG иконка
        eye_svg_path = get_path("bin", "icons", "visible.svg")
        svg_widget = CustomSvgWidget(eye_svg_path)
        svg_widget.setFixedSize(25, 25)
        svg_widget.setStyleSheet("background: transparent; border: none;")
        
        # Эффект цвета
        # color_effect = QGraphicsColorizeEffect()
        # svg_widget.setGraphicsEffect(color_effect)
        self.style_manager.apply_color_svg(svg_widget, specified_color="#CFCFCF")
        
        # Layout для кнопки с центрированием
        btn_layout = QHBoxLayout(toggle_btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(svg_widget)
        
        # Добавляем в контейнер
        container_layout.addWidget(field)
        container_layout.addWidget(toggle_btn)
        
        # Подключаем обработчик
        toggle_btn.clicked.connect(lambda: self.toggle_password_visibility(field, svg_widget))
        
        # Сохраняем ссылки
        container.password_field = field
        container.toggle_btn = toggle_btn
        container.svg_widget = svg_widget
        
        return container

    def toggle_password_visibility(self, field, svg_widget):
        """Переключить видимость пароля"""
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.style_manager.apply_color_svg(svg_widget)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            self.style_manager.apply_color_svg(svg_widget, specified_color="#CFCFCF")
