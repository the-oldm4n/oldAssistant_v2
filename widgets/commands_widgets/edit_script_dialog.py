from widgets.commands_widgets.simple_script_form import SimpleScriptForm
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget,QDialog
from PySide6.QtCore import Qt


class EditScriptDialog(QDialog):
    """Диалог редактирования скрипта"""
    def __init__(self, script_key, script_data, commands_manager, parent=None):
        super().__init__(parent)
        self.script_key = script_key
        self.original_data = script_data.copy()
        self.commands_manager = commands_manager

        self.form = SimpleScriptForm(script_key=self.script_key, commands_manager=self.commands_manager, is_editor=True)

        self.form.load_script_data(script_data)
        self.form.txt_script_name.setText(script_key)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 650)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)

        self.main_widget = QWidget(self)
        self.main_widget.setObjectName("WindowContainer")
        content_layout = QVBoxLayout(self.main_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)

        content_layout.addWidget(self.form)

        btn_layout = QHBoxLayout()
        
        btn_test = QPushButton("Тестовый запуск")
        btn_test.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_test.clicked.connect(self.test_script)
        btn_layout.addWidget(btn_test)
        
        btn_layout.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_save.clicked.connect(self.save)
        btn_layout.addWidget(btn_save)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        content_layout.addLayout(btn_layout)
        dialog_layout.addWidget(self.main_widget)

    
    def test_script(self):
        """Тестовый запуск скрипта"""
        self.form.test_script()
    
    def save(self):
        """Сохранить изменения"""
        new_data = self.form.get_script_data()
        if new_data:
            self.original_data.update(new_data)
            self.accept()
    
    def get_updated_script_data(self):
        """Получить обновленные данные скрипта"""
        return self.original_data