import json
import os
from PySide6.QtCore import QObject, QTimer, QDateTime, Signal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QPushButton, QDialog, QWidget, \
    QHBoxLayout, QDateTimeEdit, QTextEdit, QScrollArea, QMessageBox
from path_builder import get_path
from mygui import main_apply_colors, CustomSvgWidget
from log_config import logger


class ReminderManager(QObject):
    reminder_triggered = Signal(str)
    
    def __init__(self, reminders_file):
        super().__init__()
        self.reminders_file = reminders_file
        self.reminders = []
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._check_reminders)
        
        self.load_reminders()

    def load_reminders(self):
        """Загрузка напоминаний из JSON"""
        try:
            if os.path.exists(self.reminders_file):
                with open(self.reminders_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.reminders = data.get('reminders', [])

                    self._schedule_next()
        except Exception as e:
            logger.error(f"[REMINDER] Ошибка загрузки: {e}")
            self.reminders = []

    def save_reminders(self):
        """Сохранение напоминаний в JSON"""
        try:
            data = {
                'reminders': self.reminders,
                'last_updated': QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            }
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[REMINDER] Ошибка сохранения: {e}")
    
    def add_reminder(self, text, dt: QDateTime):
        """Добавить напоминание"""
        reminder = {
            'text': text,
            'time': dt.toSecsSinceEpoch(),
            'notified': False,
            'created': QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        }
        self.reminders.append(reminder)
        self.reminders.sort(key=lambda x: x['time'])
        self.save_reminders()
        self._schedule_next()
    
    def delete_reminder(self, index: int):
        """Удалить напоминание по индексу"""
        if 0 <= index < len(self.reminders):
            del self.reminders[index]
            self.save_reminders()
            self._schedule_next()
            return True
        return False

    def delete_reminder_by_text(self, text: str):
        """Удалить напоминание по тексту (первое совпадение)"""
        for i, r in enumerate(self.reminders):
            if r['text'] == text and not r['notified']:
                del self.reminders[i]
                self.save_reminders()
                self._schedule_next()
                return True
        return False

    def delete_reminder_by_time(self, dt: QDateTime):
        """Удалить напоминание по времени (первое совпадение)"""
        timestamp = dt.toSecsSinceEpoch()
        for i, r in enumerate(self.reminders):
            if r['time'] == timestamp and not r['notified']:
                del self.reminders[i]
                self.save_reminders()
                self._schedule_next()
                return True
        return False

    def delete_all_reminders(self):
        """Удалить все напоминания"""
        self.reminders.clear()
        self.save_reminders()
        self.timer.stop()

    def delete_completed_reminders(self):
        """Удалить все сработавшие напоминания"""
        self.reminders = [r for r in self.reminders if not r['notified']]
        self.save_reminders()
        self._schedule_next()

    def delete_expired_reminders(self):
        """Удалить все просроченные напоминания (время прошло, но не сработали)"""
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        self.reminders = [r for r in self.reminders if r['time'] > now]
        self.save_reminders()
        self._schedule_next()
    
    def get_active_reminders(self):
        """Получить активные (не сработавшие) напоминания"""
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        return [r for r in self.reminders if not r['notified'] and r['time'] > now]
    
    def get_all_reminders(self):
        """Получить все напоминания"""
        return self.reminders
    
    def _schedule_next(self):
        """Запланировать следующее напоминание"""
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        next_time = None
        
        for r in self.reminders:
            if not r['notified'] and r['time'] > now:
                next_time = r['time']
                break
                
        if next_time:
            msecs = (next_time - now) * 1000
            self.timer.start(msecs)
        else:
            self.timer.stop()
    
    def _check_reminders(self):
        """Проверка сработавших напоминаний"""
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        triggered = False
        
        for r in self.reminders:
            if not r['notified'] and r['time'] <= now:
                self.reminder_triggered.emit(r['text'])
                r['notified'] = True
                triggered = True
        
        if triggered:
            self.save_reminders()
        
        self._schedule_next()


class AddRemindDialog(QDialog):
    def __init__(self, parent=None, title: str = "Новое напоминание", text: str = ""):
        super().__init__(parent)
        self.parent_window = parent
        self.style_manager = main_apply_colors
        self.title = title
        self.text = text
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(380, 220)
        self.init_ui()

    def init_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.setSpacing(0)
        dialog_layout.addWidget(self.container)

        screen_geometry = self.screen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBarV2")
        self.title_bar.setFixedHeight(40)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 0, 0)
        self.title_layout.setSpacing(5)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("background: transparent; font-size: 16px;")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(50, 38)
        self.close_btn.setObjectName("TitleBarCloseBtn")
        self.close_btn.clicked.connect(self.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(12, 7)
        self.title_layout.addWidget(self.close_btn)
        self.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")

        self.content_widget = QWidget(self.container)
        self.content_widget.setObjectName("ContentWidget")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.input_field = QTextEdit()
        self.input_field.setObjectName("ReminderTextEdit")
        self.input_field.setText(self.text)
        content_layout.addWidget(self.input_field)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")
        content_layout.addWidget(self.error_label)

        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.datetime_edit.setCalendarPopup(True)
        content_layout.addWidget(self.datetime_edit)

        manage_timer_layout = QHBoxLayout()
        manage_timer_layout.setSpacing(10)

        self.remove_min_btn = QPushButton('- 5 минут')
        self.remove_min_btn.setStyleSheet("padding: 1px 10px;")
        self.remove_min_btn.clicked.connect(self.remove_minutes)
        manage_timer_layout.addWidget(self.remove_min_btn)

        self.add_min_btn = QPushButton('+ 5 минут')
        self.add_min_btn.setStyleSheet("padding: 1px 10px;")
        self.add_min_btn.clicked.connect(self.add_minutes)
        manage_timer_layout.addWidget(self.add_min_btn)

        content_layout.addLayout(manage_timer_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton('Сохранить')
        self.ok_button.setStyleSheet("padding: 1px 10px;")
        self.ok_button.setObjectName("AcceptButton")
        self.ok_button.clicked.connect(self.try_accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton('Закрыть')
        self.cancel_button.setStyleSheet("padding: 1px 10px;")
        self.cancel_button.setObjectName("RejectButton")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        content_layout.addLayout(button_layout)

        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.content_widget)

    def add_minutes(self):
        dt = self.datetime_edit.dateTime()

        dt = dt.addSecs(5 * 60)
        self.datetime_edit.setDateTime(dt)

    def remove_minutes(self):
        dt = self.datetime_edit.dateTime()

        dt = dt.addSecs(-5 * 60)
        self.datetime_edit.setDateTime(dt)

    def try_accept(self):
        """Пытается закрыть окно, если ввод корректен."""
        if not self.get_text():
            self.show_error("Поле напоминания не заполнено!")
            return
        self.accept()

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_text(self):
        """Возвращает очищенный текст из поля ввода."""
        return self.input_field.toPlainText()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

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


class RemindersListDialog(QDialog):
    def __init__(self, reminder_manager=None, parent=None):
        super().__init__(parent)
        self.reminder_manager = reminder_manager
        self.main = parent
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.icon_delete_path = get_path("bin", "icons", "delete.svg")
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(400, 400)
        self.init_ui()
        self.load_reminders()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

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
    
    def init_ui(self):
        # Контейнер
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Центрируем
        screen = self.screen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        # Заголовок
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBarV2")
        self.title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 0, 0)
        
        self.title_label = QLabel("Напоминания")
        self.title_label.setStyleSheet("background: transparent; font-size: 16px;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # Кнопка закрыть
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(50, 38)
        self.close_btn.setObjectName("TitleBarCloseBtn")
        self.close_btn.clicked.connect(self.reject)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(25, 25)
        self.close_svg.move(12, 7)
        self.main.style_manager.apply_color_svg(self.close_svg, specified_color="#FF0000")
        title_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(self.title_bar)
        
        # Скролл-область
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("ContentWidget")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(5)
        self.scroll_layout.addStretch()
        
        scroll.setWidget(self.scroll_widget)
        main_layout.addWidget(scroll)
        
        # Кнопка удалить все
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 5, 10, 10)
        
        self.clear_all_btn = QPushButton("Удалить все")
        self.clear_all_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.clear_all_btn.clicked.connect(self.clear_all_reminders)
        btn_layout.addWidget(self.clear_all_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        main_layout.addLayout(btn_layout)
        
        # Добавляем контейнер в диалог
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.setSpacing(0)
        dialog_layout.addWidget(self.container)
    
    def load_reminders(self):
        """Загрузка списка напоминаний"""
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        reminders = self.reminder_manager.get_all_reminders()
        
        if not reminders:
            label = QLabel("Нет напоминаний")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #888; padding: 20px;")
            self.scroll_layout.insertWidget(0, label)
            self.clear_all_btn.setEnabled(False)
            return
        
        self.clear_all_btn.setEnabled(True)
        
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        
        for i, reminder in enumerate(reminders):
            is_notified = reminder.get('notified', False)
            is_expired = reminder['time'] <= now

            item_widget = QWidget()

            if is_notified:
                item_widget.setObjectName("CompletedReminder")  # серая
            elif is_expired:
                item_widget.setObjectName("ExpiredReminder")   # красная
            else:
                item_widget.setObjectName("ActiveReminder")

            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)

            text = reminder['text']
            dt = QDateTime.fromSecsSinceEpoch(reminder['time'])
            time_str = dt.toString("yyyy-MM-dd HH:mm")
 
            text_label = QLabel(text)
            text_label.setStyleSheet("background: transparent;")
            text_label.setWordWrap(True)

            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: #fff; font-size: 12px; background: transparent;")
            time_label.setFixedWidth(120)

            delete_btn = QPushButton()
            delete_btn.setFixedSize(30, 30)
            delete_btn.setObjectName("ActionSVGBtn")
            delete_btn.setToolTip("Удалить")
            delete_btn.clicked.connect(lambda checked, idx=i: self.delete_reminder(idx))
            delete_svg = CustomSvgWidget(self.icon_delete_path, delete_btn)
            delete_svg.setFixedSize(30, 30)
            self.main.style_manager.apply_color_svg(delete_svg) 

            item_layout.addWidget(text_label, 1)
            item_layout.addWidget(time_label)
            item_layout.addWidget(delete_btn)
            
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item_widget)
    
    def delete_reminder(self, index):
        """Удаление одного напоминания"""
        reply = self.main.show_message(
            title="Удаление",
            text="Удалить это напоминание?",
            message_type="question",
            buttons= QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.reminder_manager.delete_reminder(index)
            self.load_reminders()
    
    def clear_all_reminders(self):
        """Удаление всех напоминаний"""
        reply = self.main.show_message(
            title="Удаление",
            text="Удалить все напоминания?",
            message_type="question",
            buttons= QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.reminder_manager.delete_all_reminders()
            self.load_reminders()