"""Диалог сохранения пресета"""
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLineEdit, QApplication
from mygui.paths import ICONS
from mygui.widgets.custom_svg import CustomSvgWidget


class SavePresetDialog(QDialog):
    """Кастомное диалоговое окно ввода с валидацией"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.icon_close_path = os.path.join(ICONS, "close.svg")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(320, 170)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.init_ui()

    def init_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")

        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBarV2")
        self.title_bar.setFixedHeight(40)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 5, 10, 5)
        self.title_layout.setSpacing(5)

        self.title_label = QLabel('Сохранить пресет', self.title_bar)
        self.title_label.setStyleSheet("background: transparent")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton("", self.title_bar)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("TitleBarCloseBtnV2")
        self.close_btn.clicked.connect(self.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)
        self.parent_window.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")

        self.content_widget = QWidget(self.container)
        self.content_widget.setObjectName("ContentWidget")
        self.content_widget.setMinimumWidth(320)

        self.input_field = QLineEdit(self.content_widget)
        self.input_field.setPlaceholderText('Введите имя пресета:')

        self.error_label = QLabel(self.content_widget)
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")

        self.ok_button = QPushButton('Сохранить', self.content_widget)
        self.ok_button.setStyleSheet("padding: 1px 10px;")
        self.ok_button.setObjectName("AcceptButton")
        self.ok_button.clicked.connect(self.try_accept)

        self.cancel_button = QPushButton('Закрыть', self.content_widget)
        self.cancel_button.setStyleSheet("padding: 1px 10px;")
        self.cancel_button.setObjectName("RejectButton")
        self.cancel_button.clicked.connect(self.reject)

        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        main_layout.addWidget(self.input_field)
        main_layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.root_layout.addWidget(self.title_bar)
        self.root_layout.addWidget(self.content_widget)

        self.set_position_strategy()

    def try_accept(self):
        """Пытается закрыть окно, если ввод корректен."""
        preset_name = self.get_text()
        if not preset_name:
            self.show_error("Имя не может быть пустым!")
            return

        conflict_paths = [
            os.path.join(self.parent().base_presets, f"{preset_name}.json"),
            os.path.join(self.parent().custom_presets, f"{preset_name}.json")
        ]

        if any(os.path.exists(path) for path in conflict_paths):
            self.show_error(f"Пресет '{preset_name}' уже существует!")
            return

        self.accept()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_text(self):
        """Возвращает очищенный текст из поля ввода."""
        return self.input_field.text().strip()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()  # Закрываем только это окно
        else:
            super().keyPressEvent(event)

    def set_position_strategy(self):
        """Выбирает стратегию позиционирования окна"""
        self.position_strategy = self.center_to_parent()

    def ensure_on_screen(self):
        # Получаем экран, на котором находится окно
        screen = self.screen()
        if not screen:
            # Если окно еще не показано, берем основной экран
            screen = QApplication.primaryScreen()

        screen_geometry = screen.availableGeometry()

        if not screen_geometry.contains(self.geometry()):
            self.move(
                min(screen_geometry.right() - self.width(), max(screen_geometry.left(), self.x())),
                min(screen_geometry.bottom() - self.height(), max(screen_geometry.top(), self.y()))
            )

    def center_to_parent(self):
        """Центрирует по горизонтали и позиционирует чуть ниже заголовка родителя"""
        if not self.parent():
            return

        parent_rect = self.parent().geometry()
        title_bar_height = 20  # Высота заголовка родительского окна (может потребоваться подстройка)

        # Центрируем по горизонтали и позиционируем вертикально чуть ниже заголовка
        new_x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
        new_y = parent_rect.y() + title_bar_height + 15

        self.move(new_x, new_y)

        # Проверяем, чтобы окно не выходило за пределы экрана
        self.ensure_on_screen()

    def mousePressEvent(self, event):
        """Перетаскивание окна за заголовок"""
        if event.button() == Qt.MouseButton.LeftButton and event.y() < 30:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Перетаскивание окна за заголовок"""
        if hasattr(self, 'drag_position') and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()