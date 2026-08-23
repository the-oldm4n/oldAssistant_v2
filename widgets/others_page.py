from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QCheckBox
from bin.base_modules.stacked_widget import SlidingStackedWidget
from mygui import CustomSvgWidget, main_apply_colors, SVGProgressBar, color_signal
from bin.base_modules.download_thread import DownloadThread
from bin.utils import setup_custom_font_label
from log_config import logger
from widgets.other_widgets.censor_counter_widget import CensorCounterWidget
from widgets.other_widgets.debuglog_widget import DebugLoggerWidget


class OthersPage(QWidget):
    def __init__(self, main_window, censor_file, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        self.main = main_window
        self.censor_file = censor_file
        self.setObjectName("CustomPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        self.button_panel = QWidget()
        self.button_panel.setObjectName("TabPanel")
        button_layout = QHBoxLayout(self.button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        
        self.content_container = SlidingStackedWidget(self)
        
        censor_widget = CensorCounterWidget(self.main, self.censor_file, self)
        updates_widget = CheckUpdateWidget(self.main, self)
        debug_widget = DebugLoggerWidget(self.main, self)
        
        self.content_container.add_page(censor_widget)
        self.content_container.add_page(updates_widget)
        self.content_container.add_page(debug_widget)
        
        buttons_data = [
            {
                "key": "censor",
                "text": "Счетчик цензуры",
                "icon_path": self.main.icon_censor_path,
                "tooltip": "Счетчик цензуры",
                "index": 0,
                "widget": censor_widget
            },
            {
                "key": "updates",
                "text": "Обновления",
                "icon_path": self.main.icon_updates_path,
                "tooltip": "Обновления",
                "index": 1,
                "widget": updates_widget
            },
            {
                "key": "debugger",
                "text": "Подробные логи",
                "icon_path": self.main.icon_logs_path,
                "tooltip": "Подробные логи",
                "index": 2,
                "widget": debug_widget
            }
        ]
        
        self.nav_buttons = []
        self.nav_svgs = []
        
        for data in buttons_data:
            btn = QPushButton()
            btn.setFixedSize(60, 40)
            btn.setObjectName("TabBtn")
            btn.setToolTip(data["tooltip"])
            
            if data["icon_path"]:
                svg = CustomSvgWidget(data["icon_path"], btn)
                svg.setFixedSize(35, 35)
                svg.move(12, 2)
                self.main.style_manager.apply_color_svg(svg)
                self.nav_svgs.append(svg)
            
            btn.clicked.connect(lambda checked, idx=data["index"]: self.switch_page(idx, "bottom"))
            
            self.nav_buttons.append(btn)
            button_layout.addWidget(btn)
        
        button_layout.addStretch()
        
        self.main_layout.addWidget(self.button_panel)
        self.main_layout.addWidget(self.content_container)
        
        self.switch_page(0, "bottom")


    def switch_page(self, index, direction="right"):
        self.content_container.switch_to(index, direction)

        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_colors(self):
        for svg in self.nav_svgs:
            self.main.style_manager.apply_color_svg(svg)


class CheckUpdateWidget(QWidget):
    """
    Виджет для ручной проверки обновлений, выбора определенной версии из списка доступных
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self._help_initialized = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPageWidget")
        self.init_ui()
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.style_manager.apply_progressbar(widget=self.progress)
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.title = setup_custom_font_label("Центр обновлений", font_style="Comfortaa", weight="Medium")
        self.title.setStyleSheet("background: transparent; font-size: 18px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.check_button = QPushButton("Проверить обновления")
        self.check_button.clicked.connect(self.main.update_manager.check_update_app)
        self.check_button.setProperty("helpId", "check_button_update")
        layout.addWidget(self.check_button)

        self.update_check = QCheckBox("Проверить свежие бета-версии", self)
        self.update_check.setStyleSheet("background: transparent;")
        self.update_check.setChecked(self.main.beta_version)
        self.update_check.stateChanged.connect(self.toggle_beta_version)
        self.update_check.setProperty("helpId", "check_exp_update")
        layout.addWidget(self.update_check)

        self.rollback = QPushButton("Откат до стабильной версии")
        self.rollback.clicked.connect(self.wait_and_rollback)
        self.rollback.setProperty("helpId", "rollback_version")
        layout.addWidget(self.rollback)

        layout.addStretch()
        
        self.progress = SVGProgressBar(style="circle", show_text=False, circle_size=200)
        self.progress.hide()
        self.progress.setProperty("helpId", "rollback_version")
        layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

    def toggle_beta_version(self, state):
        """Включает/отключает проверку экспериментальных версий"""
        self.main.beta_version = state == Qt.CheckState.Checked

    def wait_and_rollback(self):
        result = self.main.show_message(
            "Уверены в своих действиях?",
            "Запрос на откат версии",
            "question",
            buttons=QMessageBox.StandardButton.Ok
        )

        if result == QMessageBox.StandardButton.Ok:
            self.rollback_stable_version()
        else:
            pass

    def rollback_stable_version(self):
        try:
            self.start_load()
            self.download_thread = DownloadThread(type_version="stable")
            self.download_thread.download_complete.connect(
                lambda: self.main.update_app(type_version="stable"))
            self.download_thread.finished.connect(self.finish_load)
            self.download_thread.start()
        except Exception as e:
            self.progress.hide()
            self.progress.stopAnimation()
            self.rollback.show()
            self.main.show_toast(f"Ошибка: {e}")
            logger.error(f"Ошибка в методе rollback_stable_version: {e}")

    def start_load(self):
        self.progress.show()
        self.rollback.hide()
        self.progress.startAnimation()

    def finish_load(self):
        self.progress.hide()
        self.rollback.setText("Ожидайте")
        self.progress.stopAnimation()