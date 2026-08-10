import os
from bin.base_modules.stacked_widget import SlidingStackedWidget
from widgets.commands_widgets.commands_list import CommandsWidget
from widgets.commands_widgets.create_commands import CreateCommandsWidget
from widgets.commands_widgets.create_scripts import CreateScriptsWidget
from widgets.commands_widgets.process_links import ProcessLinksWidget
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import Qt
from mygui import CustomSvgWidget, color_signal
from path_builder import get_path, get_app_data_dir
from config import dev_mode

if dev_mode:
    folder_links = get_path('user_data', "links")
    links_file = get_path('user_data', 'links.json')
    commands_file = get_path('user_data', 'commands.json')
else:
    folder_links = os.path.join(get_app_data_dir(), 'user_data', "links")
    links_file = os.path.join(get_app_data_dir(), 'user_data', 'links.json')
    commands_file = os.path.join(get_app_data_dir(), 'user_data', 'commands.json')


class CommandsPage(QWidget):
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
        
        new_com_widget = CreateCommandsWidget(main=self.main, folder_links=folder_links, links_file=links_file, parent=self)
        added_com_widget = CommandsWidget(main=self.main, commands_file=commands_file, parent=self)
        process_links_widget = ProcessLinksWidget(main=self.main, parent=self)
        create_scripts_widget = CreateScriptsWidget(main=self.main, links_file=links_file, parent=self)
        
        self.content_container.add_page(new_com_widget)
        self.content_container.add_page(added_com_widget)
        self.content_container.add_page(process_links_widget)
        self.content_container.add_page(create_scripts_widget)
        
        buttons_data = [
            {
                "key": "new_commands",
                "text": "Создание команд",
                "icon_path": self.main.icon_create_command_path,
                "tooltip": "Создание новых команд",
                "index": 0,
                "widget": new_com_widget
            },
            {
                "key": "list_commands",
                "text": "Список команд",
                "icon_path": self.main.icon_added_commands_path,
                "tooltip": "Список ваших команд",
                "index": 1,
                "widget": added_com_widget
            },
            {
                "key": "process_links",
                "text": "Процессы ярлыков",
                "icon_path": self.main.icon_process_link_path,
                "tooltip": "Процессы ярлыков",
                "index": 2,
                "widget": process_links_widget
            },
            {
                "key": "create_scripts",
                "text": "Скрипты",
                "icon_path": self.main.icon_scripts_path,
                "tooltip": "Создание сценариев запуска",
                "index": 3,
                "widget": create_scripts_widget
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
