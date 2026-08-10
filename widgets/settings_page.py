import os
from bin.base_modules.stacked_widget import SlidingStackedWidget
from mygui import CustomSvgWidget, color_signal
from path_builder import get_path, get_app_data_dir
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import Qt
from config import dev_mode
from widgets.settings_widgets.main_settings import SettingsWidget
from widgets.settings_widgets.other_settings import OtherSettingsWidget
from widgets.settings_widgets.hook_manager import SpeechHookManagerWidget
from widgets.settings_widgets.tool_panel import SettingsWidgetPanel

if dev_mode:
    user_icons_folder = get_path("user_data", "user-icons")
    custom_presets = get_path('user_data', 'presets')
    user_keywords = get_path("user_data", "keywords.json")
    widget_state = get_path("user_data", "widget_state.json")
    script_icons_path = get_path("data", "script-icons")
else:
    user_icons_folder = os.path.join(get_app_data_dir(), "user_data", "user-icons")
    custom_presets = os.path.join(get_app_data_dir(), 'user_data', 'presets')
    user_keywords = os.path.join(get_app_data_dir(), "user_data", "keywords.json")
    widget_state = os.path.join(get_app_data_dir(), "user_data", "widget_state.json")
    script_icons_path = os.path.join(get_app_data_dir(), "data", "script-icons")

base_presets = get_path('bin', 'color_presets')


class SettingsPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        color_signal.color_changed.connect(self.update_colors)
        self.main = main_window
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
        
        main_widget = SettingsWidget(self.main, self)
        other_widget = OtherSettingsWidget(self.main, self)
        speech_hook_widget = SpeechHookManagerWidget(self.main, user_keywords, self)
        settings_panel = SettingsWidgetPanel(self.main, self)
        
        self.content_container.add_page(main_widget)
        self.content_container.add_page(other_widget)
        self.content_container.add_page(speech_hook_widget)
        self.content_container.add_page(settings_panel)
        
        buttons_data = [
            {
                "key": "main",
                "text": "Основные",
                "icon_path": self.main.icon_main_settings_path,
                "tooltip": "Основные настройки",
                "index": 0,
                "widget": main_widget
            },
            {
                "key": "advanced",
                "text": "Дополнительно",
                "icon_path": self.main.icon_advance_settings_path,
                "tooltip": "Дополнительные настройки",
                "index": 1,
                "widget": other_widget
            },
            {
                "key": "speech_hook",
                "text": "Хук-слова",
                "icon_path": self.main.icon_speech_hook_path,
                "tooltip": "Менеджер управления хук-словами",
                "index": 2,
                "widget": speech_hook_widget
            },
            {
                "key": "panel",
                "text": "Панель",
                "icon_path": self.main.icon_panel_path,
                "tooltip": "Настройки виджет-панели",
                "index": 3,
                "widget": settings_panel
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
        
        if isinstance(main_widget, SettingsWidget):
            main_widget.voice_changed.connect(self.main.update_voice)

    def switch_page(self, index, direction="right"):
        self.content_container.switch_to(index, direction)
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_colors(self):
        for svg in self.nav_svgs:
            self.main.style_manager.apply_color_svg(svg)
