from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from bin.lists import help_data


class HelpWidget(QWidget):
    help_text_changed = Signal(str)  # Сигнал для обновления текста помощи
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_help_database()
        
    def setup_ui(self):       
        main_layout = QVBoxLayout(self)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("HelpWidget")

        content_layout = QVBoxLayout(self.content_widget)

        self.help_text = QTextEdit("Helper")
        self.help_text.setReadOnly(True)

        content_layout.addWidget(self.help_text)
        main_layout.addWidget(self.content_widget)
        
    def setup_help_database(self):
        """Инициализация базы знаний"""
        self.help_database = help_data 
        
    def show_help(self, help_id):
        if help_id in self.help_database:
            help_info = self.help_database[help_id]
            
            html_content = f"""
            <h5>Helper</h5>
            <h3 style="margin-bottom: 10px;">{help_info['title']}</h3>
            <p style="margin: 5px 0;"><b>Описание:</b> {help_info['description']}</p>
            <p style="margin: 5px 0;"><b>Примечания:</b> {help_info['usage']}</p>
            """
            self.help_text.setHtml(html_content)
        else:
            # Если справка не найдена
            self.help_text.setHtml("""
            <p style="color: #7f8c8d;">Справка не найдена</p>
            """)