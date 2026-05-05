import winsound
from mygui import main_apply_colors
from mygui import CustomSvgWidget
from log_config import logger
from path_builder import get_path
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, QRect
from PySide6.QtWidgets import (QLabel, QGraphicsColorizeEffect, QHBoxLayout, QWidget, QVBoxLayout,
                               QDialog, QMessageBox, QPushButton)


class ToastNotif(QWidget):
    """
    Всплывающее уведомление как часть родительского окна
    """
    _active_toast = None

    def __init__(self, parent=None, message="", timeout=3500):
        super().__init__(parent)

        if ToastNotif._active_toast:
            ToastNotif._active_toast.close_immediately()
        ToastNotif._active_toast = self

        self.message = message
        self.timeout = timeout

        if not self.parent():
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(300, 120)

        self.svg_path = get_path("bin", "icons", "logo-app.svg")
        self.style_manager = main_apply_colors
        self.init_ui()
        self.apply_styles()

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(400)
        self.geo_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_animated)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget()
        container.setObjectName("ToastNotif")
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.svg_image = CustomSvgWidget(self.svg_path)
        self.svg_image.setFixedSize(50, 50)
        self.color_svg = QGraphicsColorizeEffect()
        self.svg_image.setGraphicsEffect(self.color_svg)
        content_layout.addWidget(self.svg_image, alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignRight)
        
        # Текст
        self.message = QLabel(self.message)
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.message, stretch=1)
        
        container_layout.addWidget(content)
        layout.addWidget(container)

    def apply_styles(self):
        try:
            self.styles = self.style_manager.load_styles()
            self.style_manager.apply_color_svg(self.svg_image)
            
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
        except Exception as e:
            logger.error(f"Ошибка в apply_styles: {e}")

    def show_toast(self):
        if self.parent():
            parent_width = self.parent().width()
            start_x = parent_width + self.width() + 10
            target_x = parent_width - self.width() - 10
            start_y = 0
            target_y = 50
        else:
            screen_geometry = self.screen().availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            start_x = screen_width + self.width() + 10
            target_x = screen_width - self.width() - 10
            start_y = screen_height
            target_y = screen_height - self.height() - 50
        
        target_geo = QRect(target_x, target_y, self.width(), self.height())
        start_geo = QRect(start_x, start_y, self.width(), self.height())
        self.setGeometry(start_geo)
        self.show()

        self.geo_anim.setStartValue(start_geo)
        self.geo_anim.setEndValue(target_geo)

        self.geo_anim.start()
        self.timer.start(self.timeout)
        self.raise_()
    
    def hide_animated(self):
        if self.timer.isActive():
            self.timer.stop()

        if self.parent():
            parent_width = self.parent().width()
            end_x = parent_width + self.width() + 10
            end_y = 0
        else:
            screen_geometry = self.screen().availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            end_x = screen_width + self.width() + 10
            end_y = screen_height
        
        current_geo = self.geometry()
        end_geo = QRect(end_x, end_y, self.width(), self.height())
        
        self.geo_anim.setStartValue(current_geo)
        self.geo_anim.setEndValue(end_geo)

        self.geo_anim.start()

    def close_immediately(self):
        """Полное закрытие"""     
        self.hide()
        self.deleteLater()
        
        if ToastNotif._active_toast is self:
            ToastNotif._active_toast = None

    def mouseDoubleClickEvent(self, event):
        """Закрыть тост при двойном клике"""
        self.hide_animated()

        if self.timer.isActive():
            self.timer.stop()


class SimpleNotif():
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
        self.main.setMinimumWidth(300)
        self.main.setMaximumWidth(600)
        self.main.setMinimumHeight(250)
        self.main.setMaximumHeight(400)

        screen_geometry = self.main.screen().availableGeometry()
        self.main.move(
            (screen_geometry.width() - self.main.width()) // 2,
            (screen_geometry.height() - self.main.height()) // 2
        )

        self.container = QWidget(self.main)
        self.container.setObjectName("WindowContainer")

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBarV2")
        self.title_bar.setFixedHeight(40)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 0, 0)
        self.title_layout.setSpacing(5)

        self.title_bar.mousePressEvent = self.title_bar_mouse_press
        self.title_bar.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar.mouseReleaseEvent = self.title_bar_mouse_release

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("background: transparent")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(50, 40)
        self.close_btn.setObjectName("TitleBarCloseBtn")
        self.close_btn.clicked.connect(self.main.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(12, 7)
        self.title_layout.addWidget(self.close_btn)
        self.style_manager.apply_color_svg(self.close_svg, specified_color="#ff0000")

        main_layout.addWidget(self.title_bar)

        content_widget = QWidget()
        content_widget.setMinimumWidth(300)
        content_widget.setMaximumWidth(600)
        content_widget.setMinimumHeight(200)
        content_widget.setMaximumHeight(350)
        content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(content_widget)

        message_label = QLabel(self.message)
        message_label.setObjectName("MessageLabel")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(message_label)

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
            self.main.setStyleSheet(style_sheet)

        except Exception as e:
            logger.error(f"Ошибка в методе apply_styles: {e}")

    def exec_(self):
        """Показать диалог и вернуть результат"""
        result = self.main.exec_()
        return result

    def show(self):
        """Показать диалог без ожидания результата"""
        self.main.show()