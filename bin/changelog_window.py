import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser
import markdown2

from bin.custom_svg_widget import CustomSvgWidget
from bin.lists import setup_custom_font_label

class ChangelogWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant = parent
        self.drag_pos = None
        self.init_ui()
        self.load_changelog()
        self.assistant.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#FF0000")

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(450, 600)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("WindowContainer")
        self.setCentralWidget(self.central_widget)

        root_layout = QVBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar_widget = QWidget()
        self.title_bar_widget.setObjectName("TitleBar")
        self.title_bar_layout = QHBoxLayout(self.title_bar_widget)
        self.title_bar_layout.setContentsMargins(10, 5, 10, 5)
        self.title_bar_layout.setSpacing(5)

        self.title_bar_widget.mousePressEvent = self.title_bar_mouse_press
        self.title_bar_widget.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar_widget.mouseReleaseEvent = self.title_bar_mouse_release

        link_label = QLabel()
        link_label.setText('''
            <a href="https://owl-app.ru" 
            style="color: #35E808;">
            owl-app.ru
            </a>
        ''')
        link_label.setStyleSheet("background: transparent;")
        link_label.setOpenExternalLinks(True)
        link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.title_bar_layout.addWidget(link_label)

        self.title_bar_layout.addStretch()

        title_label = setup_custom_font_label("История изменений", font_style="Comfortaa", weight="Medium")
        title_label.setStyleSheet("background: transparent;")
        title_label.setObjectName("TitleLabel")
        self.title_bar_layout.addWidget(title_label)

        self.title_bar_layout.addStretch()

        close_btn = QPushButton("")
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.assistant.icon_close_path, close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_bar_layout.addWidget(close_btn)

        root_layout.addWidget(self.title_bar_widget)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Текстовый браузер
        self.text_browser = QTextBrowser()
        self.text_browser.setStyleSheet("background: transparent;")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setReadOnly(True)
        main_layout.addWidget(self.text_browser)

        # Стили для Markdown
        self.text_browser.document().setDefaultStyleSheet("""
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                padding: 15px;
            }
            h1 {
                font-size: 24px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            h2 {
                font-size: 20px;
                margin-top: 25px;
            }
            h3 {
                font-size: 16px;
            }
            code {
                padding: 2px 5px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
            }
            pre {
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }
            blockquote {
                border-left: 4px solid #ddd;
                padding-left: 15px;
                color: #777;
                margin-left: 0;
            }
            a {
                color: #1e88e5;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            ul, ol {
                padding-left: 25px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        """)

        ps = QLabel("Powered by theoldman")
        ps.setStyleSheet("background: transparent; font-size: 12px; padding: 5px;")
        main_layout.addWidget(ps, alignment=Qt.AlignmentFlag.AlignRight)

        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(close_button)

        root_layout.addWidget(self.content_widget)      

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
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

    def load_changelog(self):
        """Загружает и отображает Markdown файл"""
        try:
            if not hasattr(self.assistant, 'changelog_file_path'):
                self._show_error("Не указан путь к файлу изменений")
                return

            changelog_path = self.assistant.changelog_file_path

            if not os.path.exists(changelog_path):
                self._show_error(f"Файл не найден: {changelog_path}")
                return

            with open(changelog_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Конвертируем Markdown в HTML
            html = markdown2.markdown(
                md_content,
                extras=[
                    'fenced-code-blocks',  # Блоки кода ```
                    'tables',  # Таблицы
                    'footnotes',  # Сноски
                    'toc',  # Оглавление
                    'cuddled-lists',  # Компактные списки
                    'task_list',  # Списки задач
                    'spoiler'  # Скрытый текст
                ]
            )

            self.text_browser.setHtml(html)

        except Exception as e:
            self._show_error(f"Ошибка загрузки Markdown: {str(e)}")

    def _show_error(self, message):
        """Отображает сообщение об ошибке"""
        self.text_browser.setPlainText(message)