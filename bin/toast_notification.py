import shiboken6
import winsound
from mygui import CustomSvgWidget, main_apply_colors
from log_config import debuglog
from path_builder import get_path
from PySide6.QtCore import QParallelAnimationGroup, QEasingCurve, QPropertyAnimation, QPoint, QEvent, QTimer, \
    QAbstractAnimation, Qt
from PySide6.QtWidgets import (QApplication, QLabel, QGraphicsColorizeEffect, QHBoxLayout, QWidget, QVBoxLayout,
                               QDialog, QMessageBox, QPushButton)


class ToastNotification(QDialog):
    """
    Окно всплывающего уведомления
    """
    _active_toast = None
    _creating_notification = False  # Флаг для защиты от рекурсии

    def __init__(self, parent=None, message="", timeout=3500):
        super().__init__(parent)
        if ToastNotification._active_toast:
            ToastNotification._active_toast.close_immediately()

            # Сохраняем ссылку на текущее уведомление
        ToastNotification._active_toast = self
        self.parent = parent
        if self.parent:
            self.parent.installEventFilter(self)
        self.timeout = timeout
        self.message = message
        self.svg_path = get_path("bin","icons",  "logo-app.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.style_manager = main_apply_colors
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(300)  # Продолжительность анимации прозрачности
        self.opacity_animation.setKeyValueAt(0.0, 0.0)
        self.opacity_animation.setKeyValueAt(0.7, 0.0)
        self.opacity_animation.setKeyValueAt(1.0, 1.0)

        # Модифицируем анимацию позиции для движения сверху вниз
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.setDuration(700)

    def init_ui(self):
        # Настройки окна
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 100)

        # Получаем полупрозрачный цвет на основе стиля TitleBar
        background_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=320)

        # Основной layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_container = QWidget()
        main_container.setObjectName("MainContainer")
        main_container.setStyleSheet(f"""
            #MainContainer {{
                background: {background_color};
                border-radius: 10px;
            }}
        """)
        
         # Layout для основного контейнера
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # --- Контент: иконка + текст ---
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # Иконка
        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(50, 50)
        self.svg_image.setStyleSheet("background: transparent; border: none;")
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignRight)

        # Текст
        self.label = QLabel(self.message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.label, stretch=1)

        close_btn = QPushButton("")
        close_btn.setObjectName("CloseButton_clear")
        close_btn.setFixedSize(35, 20)
        close_btn.clicked.connect(self.hide_animated)
        self.close_svg = CustomSvgWidget(self.icon_close_path, close_btn)
        self.close_svg.setFixedSize(20, 20)
        self.close_svg.move(8, 0)
        self.close_svg.setStyleSheet("background: transparent;")
        content_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        close_btn.setStyleSheet("""
                #CloseButton_clear {
                    border: none;
                    background: transparent;
                    border-radius: 10px;
                }
                #CloseButton_clear:hover {
                    background: rgba(70, 70, 70, 240);
                }
                """)

        # Добавляем content_widget в container_layout
        container_layout.addWidget(content_widget)

        # Добавляем main_container в main_layout
        main_layout.addWidget(main_container)

        self.setLayout(main_layout)

        # --- Анимация и таймер ---
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.setDuration(500)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_animated)

    def eventFilter(self, obj, event):
        """Обработка событий родительского окна"""
        if ToastNotification._active_toast:
            if obj == self.parent:
                if event.type() == QEvent.Type.WindowStateChange:
                    if self.parent.isActiveWindow():
                        self.handle_parent_restored()
                elif event.type() == QEvent.Type.Hide:
                    if self.parent.isHidden():
                        self.handle_parent_hidden()
        return super().eventFilter(obj, event)

    def handle_parent_minimized(self):
        """Родитель свернут в трей"""
        if hasattr(self, 'animation_group') and self.animation_group.state() == QAbstractAnimation.State.Running:
            self.animation_group.stop()

        self.close_immediately()

    def handle_parent_restored(self):
        """Родитель восстановлен из трея"""
        # Можно автоматически показать уведомление снова, если нужно
        pass

    def handle_parent_hidden(self):
        """Родитель скрыт (например, закрыт)"""
        self.close_immediately()

    def recalculate_position(self):
        """Пересчет позиции уведомления"""
        if self.parent and not self.parent.isMinimized():
            parent_geo = self.parent.geometry()
            end_x = parent_geo.right() - self.width()
            end_y = parent_geo.top() + 34
            self.move(end_x, end_y)
        else:
            screen_geo = QApplication.primaryScreen().geometry()
            end_x = screen_geo.width() - self.width()
            end_y = 0
            self.move(end_x, end_y)

    def close_immediately(self):
        """Безопасное закрытие уведомления без анимации"""
        try:
            # 1. Останавливаем все анимации и таймеры
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()

            if hasattr(self, 'animation') and self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()

            if (hasattr(self, 'animation_group')
                    and self.animation_group.state() == QParallelAnimationGroup.State.Running):
                self.animation_group.stop()

            if (hasattr(self, 'opacity_animation')
                    and self.opacity_animation.state() == QPropertyAnimation.State.Running):
                self.opacity_animation.stop()

            # 2. Проверяем, существует ли еще виджет
            if shiboken6.isValid(self):
                # 3. Скрываем вместо закрытия (более безопасно)
                self.hide()

                # 4. Отсоединяем от родителя, если он существует
                if self.parent and shiboken6.isValid(self.parent):
                    self.setParent(None)

                # 5. Планируем реальное удаление
                self.deleteLater()

            # 6. Очищаем ссылку
            if ToastNotification._active_toast is self:
                ToastNotification._active_toast = None

        except Exception as e:
            debuglog.error(f"Ошибка при закрытии уведомления: {e}")
    
    def showEvent(self, event):
        try:
            # Устанавливаем начальную прозрачность
            self.setWindowOpacity(0.0)
            screen_geo = QApplication.primaryScreen().availableGeometry()
            if self.parent and self.parent.isVisible() and not self.parent.isMinimized():
                parent_geo = self.parent.geometry()
                start_x = parent_geo.right() - self.width()
                start_y = parent_geo.top() - self.height()
                end_x = start_x
                end_y = parent_geo.top() + 100
            else:
                start_x = screen_geo.width() + self.width()
                start_y = screen_geo.height() - self.height() - 70
                end_x = screen_geo.width() - self.width()
                end_y = start_y

            self.move(start_x, start_y)
            
            super().showEvent(event)

            # Настраиваем анимацию позиции  
            self.animation.setStartValue(QPoint(start_x, start_y))
            self.animation.setEndValue(QPoint(end_x, end_y))
            self.animation.setEasingCurve(QEasingCurve.Type.OutBack)

            # Запускаем обе анимации параллельно
            self.animation.start()
            self.opacity_animation.start()

            # Таймер для автоматического скрытия
            self.timer.start(self.timeout) 
        except Exception as e:
            debuglog.error(f"showEvent FAILED: {e}", exc_info=True)
            raise

    def hide_animated(self):
        """Анимация скрытия с изменением прозрачности"""
        # Создаем анимацию для исчезновения     
        opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        opacity_animation.setDuration(400)
        opacity_animation.setStartValue(1.0)
        opacity_animation.setEndValue(0.0)
        
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(opacity_animation)
        self.animation_group.finished.connect(self.close_immediately)
        self.animation_group.start()

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()
            # Применение к SVG
            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_color_svg(self.close_svg, strength=0.95, specified_color="#FF0000")

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

            # Устанавливаем стиль для текущего окна
            self.setStyleSheet(style_sheet)

        except Exception as e:
            debuglog.error(f"Ошибка в методе apply_styles: {e}")


class SimpleNotice():
    def __init__(self, parent=None, message="", title="Уведомление", message_type="info",
                 buttons=QMessageBox.StandardButton.Ok):
        self.parent = parent
        self.type = message_type
        self.message = message
        self.title = title
        self.buttons = buttons
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.style_manager = main_apply_colors
        self.styles = self.style_manager.load_styles()
        self.result = None
        self.main = None
        self.drag_pos = None
        self.container = None
        self.init_ui()
        self.apply_styles()
        
    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Запоминаем позицию относительно главного окна
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            # Вычисляем смещение и перемещаем главное окно
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.main.move(self.main.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

    def init_ui(self):
        sound = {
            'info': winsound.MB_ICONASTERISK,
            'warning': winsound.MB_ICONEXCLAMATION,
            'error': winsound.MB_ICONHAND,
            'question': winsound.MB_ICONASTERISK
        }.get(self.type, winsound.MB_ICONASTERISK)
        winsound.MessageBeep(sound)

        self.main = QDialog(self.parent) if self.parent else QDialog()
        self.main.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.main.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.main.setMinimumWidth(280)
        self.main.setMaximumWidth(500)
        self.main.setMinimumHeight(190)
        self.main.setMaximumHeight(250)

        screen_geometry = self.main.screen().availableGeometry()
        self.main.move(
            (screen_geometry.width() - self.main.width()) // 2,
            (screen_geometry.height() - self.main.height()) // 2
        )

        self.container = QWidget(self.main)
        self.container.setObjectName("MessageContainer")
        self.container.setGeometry(0, 0, self.main.width(), self.main.height())

        # Основной layout для всего контента
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        # Панель заголовка
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(40)
        
        title_bar.mousePressEvent = self.title_bar_mouse_press
        title_bar.mouseMoveEvent = self.title_bar_mouse_move
        title_bar.mouseReleaseEvent = self.title_bar_mouse_release

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        title_layout.setSpacing(5)

        title_label = QLabel(self.title)
        title_label.setStyleSheet("background: transparent;")
        title_label.setObjectName("TitleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_btn = QPushButton("")
        close_btn.setObjectName("TitleBarCloseBtnV2")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.main.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        title_layout.addWidget(close_btn)
        title_layout.addSpacing(0)

        main_layout.addWidget(title_bar)

        # Область содержимого (сообщение + кнопки)
        content_widget = QWidget()
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)

        # Текст сообщения
        message_label = QLabel(self.message)
        message_label.setObjectName("MessageLabel")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(message_label)

        # --- Добавление кнопок ---
        if not hasattr(self, 'button_layout'):
            self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 10)
        self.button_layout.setSpacing(10)

        self.create_buttons()

        content_layout.addLayout(self.button_layout)

        main_layout.addWidget(content_widget)

    def create_buttons(self):
        """Создание кнопок в зависимости от переданных параметров"""
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        button_map = {
            QMessageBox.StandardButton.Ok: "OK",
            QMessageBox.StandardButton.Cancel: "Отмена",
            QMessageBox.StandardButton.Yes: "Да",
            QMessageBox.StandardButton.No: "Нет",
            QMessageBox.StandardButton.Abort: "Прервать",
            QMessageBox.StandardButton.Retry: "Повторить",
            QMessageBox.StandardButton.Ignore: "Игнорировать"
        }

        button_added = False
        # Обработка комбинаций кнопок
        if isinstance(self.buttons, int):
            button_flags = [
                QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No, QMessageBox.StandardButton.Abort, QMessageBox.StandardButton.Retry,
                QMessageBox.StandardButton.Ignore
            ]

            for flag in button_flags:
                if self.buttons & flag:
                    button_text = button_map.get(flag, "")
                    if button_text:
                        btn = QPushButton(button_text)
                        btn.setObjectName("DialogButton")
                        btn.setFixedSize(80, 30)
                        # Сохраняем флаг в локальной переменной для лямбды
                        flag_value = flag
                        connection = btn.clicked.connect(lambda checked, f=flag_value: self.button_clicked(f))
                        self.button_layout.addWidget(btn)
                        button_added = True

        # Если ни одна кнопка не была добавлена, добавляем OK по умолчанию
        if not button_added:
            btn = QPushButton("OK")
            btn.setObjectName("DialogButton")
            btn.setFixedSize(80, 30)  # Фиксированный размер

            btn.clicked.connect(lambda checked: self.button_clicked(QMessageBox.StandardButton.Ok))
            self.button_layout.addWidget(btn)

    def button_clicked(self, button_role):
        """Обработка нажатия кнопки"""
        self.main.done(button_role)

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()

            self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#ff0000")

            # Применяем стили к текущему окну (если они есть в файле стилей)
            style_sheet = ""
            for widget, styles in self.styles.items():
                if widget.startswith("Q"):  # Для стандартных виджетов
                    selector = widget
                else:  # Для виджетов с objectName
                    selector = f"#{widget}"

                style_sheet += f"{selector} {{\n"
                for prop, value in styles.items():
                    style_sheet += f"    {prop}: {value};\n"
                style_sheet += "}\n"
            # Устанавливаем стиль для главного окна
            self.main.setStyleSheet(style_sheet)

        except Exception as e:
            debuglog.error(f"Ошибка в методе apply_styles: {e}")

    def exec_(self):
        """Показать диалог и вернуть результат"""
        result = self.main.exec_()
        return result

    def show(self):
        """Показать диалог без ожидания результата"""
        self.main.show()


class SupplyNotice(QDialog):
    """
    Окно всплывающего уведомления
    """
    _active_toast = None

    def __init__(self, parent=None, message="", timeout=10000):
        super().__init__(parent)
        if SupplyNotice._active_toast:
            SupplyNotice._active_toast.close_immediately()

            # Сохраняем ссылку на текущее уведомление
        SupplyNotice._active_toast = self
        self.parent = parent
        if self.parent:
            self.parent.installEventFilter(self)
        self.timeout = timeout
        self.message = message
        self.svg_path = get_path("bin","icons",  "logo-app.svg")
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.style_manager = main_apply_colors
        self.styles = self.style_manager.load_styles()
        self.init_ui()
        self.apply_styles()

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(300)  # Продолжительность анимации прозрачности
        self.opacity_animation.setKeyValueAt(0.0, 0.0)
        self.opacity_animation.setKeyValueAt(0.7, 0.0)
        self.opacity_animation.setKeyValueAt(1.0, 1.0)

        # Модифицируем анимацию позиции для движения сверху вниз
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.setDuration(700)

    def init_ui(self):
        # Настройки окна
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 100)

        # Получаем полупрозрачный цвет на основе стиля TitleBar
        background_color = self.style_manager.get_transparent_background_from_border(opacity=220, darken_factor=320)

        # Основной layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_container = QWidget()
        main_container.setObjectName("MainContainer")
        main_container.setStyleSheet(f"""
            #MainContainer {{
                background: {background_color};
                border-radius: 10px;
            }}
        """)
        
         # Layout для основного контейнера
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # --- Контент: иконка + текст ---
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # Иконка
        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(50, 50)
        self.svg_image.setStyleSheet("background: transparent; border: none;")
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignRight)

        # Текст
        self.label = QLabel(self.message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.label, stretch=1)

        close_btn = QPushButton("")
        close_btn.setObjectName("CloseButton_clear")
        close_btn.setFixedSize(35, 20)
        close_btn.clicked.connect(self.hide_animated)
        self.close_svg = CustomSvgWidget(self.icon_close_path, close_btn)
        self.close_svg.setFixedSize(20, 20)
        self.close_svg.move(8, 0)
        self.close_svg.setStyleSheet("background: transparent;")
        content_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        close_btn.setStyleSheet("""
                #CloseButton_clear {
                    border: none;
                    background: transparent;
                    border-radius: 10px;
                }
                #CloseButton_clear:hover {
                    background: rgba(70, 70, 70, 240);
                }
                """)

        # Добавляем content_widget в container_layout
        container_layout.addWidget(content_widget)

        # Добавляем main_container в main_layout
        main_layout.addWidget(main_container)

        self.setLayout(main_layout)

        # --- Анимация и таймер ---
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.setDuration(500)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_animated)

    def eventFilter(self, obj, event):
        """Обработка событий родительского окна"""
        if SupplyNotice._active_toast:
            if obj == self.parent:
                if event.type() == QEvent.Type.WindowStateChange:
                    if self.parent.isActiveWindow():
                        self.handle_parent_restored()
                elif event.type() == QEvent.Type.Hide:
                    if self.parent.isHidden():
                        self.handle_parent_hidden()
        return super().eventFilter(obj, event)

    def handle_parent_minimized(self):
        """Родитель свернут в трей"""
        if hasattr(self, 'animation_group') and self.animation_group.state() == QAbstractAnimation.State.Running:
            self.animation_group.stop()

        self.close_immediately()

    def handle_parent_restored(self):
        """Родитель восстановлен из трея"""
        # Можно автоматически показать уведомление снова, если нужно
        pass

    def handle_parent_hidden(self):
        """Родитель скрыт (например, закрыт)"""
        self.close_immediately()

    def recalculate_position(self):
        """Пересчет позиции уведомления"""
        if self.parent and not self.parent.isMinimized():
            parent_geo = self.parent.geometry()
            end_x = parent_geo.right() - self.width()
            end_y = parent_geo.top() + 34
            self.move(end_x, end_y)
        else:
            screen_geo = QApplication.primaryScreen().geometry()
            end_x = screen_geo.width() - self.width()
            end_y = 0
            self.move(end_x, end_y)

    def close_immediately(self):
        """Безопасное закрытие уведомления без анимации"""
        try:
            # 1. Останавливаем все анимации и таймеры
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()

            if hasattr(self, 'animation') and self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.stop()

            if (hasattr(self, 'animation_group')
                    and self.animation_group.state() == QParallelAnimationGroup.State.Running):
                self.animation_group.stop()

            if (hasattr(self, 'opacity_animation')
                    and self.opacity_animation.state() == QPropertyAnimation.State.Running):
                self.opacity_animation.stop()

            # 2. Проверяем, существует ли еще виджет
            if shiboken6.isValid(self):
                # 3. Скрываем вместо закрытия (более безопасно)
                self.hide()

                # 4. Отсоединяем от родителя, если он существует
                if self.parent and shiboken6.isValid(self.parent):
                    self.setParent(None)

                # 5. Планируем реальное удаление
                self.deleteLater()

            # 6. Очищаем ссылку
            if SupplyNotice._active_toast is self:
                SupplyNotice._active_toast = None

        except Exception as e:
            debuglog.error(f"Ошибка при закрытии уведомления: {e}")

    def showEvent(self, event):
        try:
            # Устанавливаем начальную прозрачность
            self.setWindowOpacity(0.0)
            screen_geo = QApplication.primaryScreen().availableGeometry()
            if self.parent and self.parent.isVisible() and not self.parent.isMinimized():
                parent_geo = self.parent.geometry()
                start_x = parent_geo.right() - self.width()
                start_y = parent_geo.top() - self.height()
                end_x = start_x
                end_y = parent_geo.top() + 90
            else:
                start_x = screen_geo.width() + self.width()
                start_y = screen_geo.height() - self.height() - 70
                end_x = screen_geo.width() - self.width()
                end_y = start_y

            self.move(start_x, start_y)
            
            super().showEvent(event)

            # Настраиваем анимацию позиции           
            self.animation.setStartValue(QPoint(start_x, start_y))
            self.animation.setEndValue(QPoint(end_x, end_y))
            self.animation.setEasingCurve(QEasingCurve.Type.OutBack)

            # Запускаем обе анимации параллельно
            self.animation.start()
            self.opacity_animation.start()

            # Таймер для автоматического скрытия
            self.timer.start(self.timeout)      
        except Exception as e:
            debuglog.error(f"showEvent FAILED: {e}", exc_info=True)
            raise

    def hide_animated(self):
        """Анимация скрытия с изменением прозрачности"""
        # Создаем анимацию для исчезновения     
        opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        opacity_animation.setDuration(400)
        opacity_animation.setStartValue(1.0)
        opacity_animation.setEndValue(0.0)
        
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(opacity_animation)
        self.animation_group.finished.connect(self.close_immediately)
        self.animation_group.start()

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()
            # Применение к SVG
            self.style_manager.apply_color_svg(self.svg_image, strength=0.95)
            self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#FF0000")

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

            # Устанавливаем стиль для текущего окна
            self.setStyleSheet(style_sheet)

        except Exception as e:
            debuglog.error(f"Ошибка в методе apply_styles: {e}")