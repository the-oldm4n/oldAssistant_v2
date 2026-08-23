import json
import os
import secrets
import string
from mygui import main_apply_colors, CustomSvgWidget, CustomToggle
from bin.lists import fonts_list
from bin.utils import setup_custom_font_label
from bin.shortcut_monitor import ShortcutMonitor
from bin.signals import widget_btns_signal
from bin.widget_window import WindowStateManager
from path_builder import get_path, get_app_data_dir
from log_config import logger
from PySide6.QtGui import QAction, QFontDatabase, QRegularExpressionValidator
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QWidget,\
    QDialog, QMenu, QLineEdit, QComboBox, QScrollArea, QFrame,QCheckBox
from PySide6.QtCore import Signal, QTimer, Qt, QEvent, QRegularExpression
from config import dev_mode

if dev_mode:
    user_icons_folder = get_path("user_data", "user-icons")
    user_keywords = get_path("user_data", "keywords.json")
    widget_state = get_path("user_data", "widget_state.json")
    script_icons_path = get_path("data", "script-icons")
else:
    user_icons_folder = os.path.join(get_app_data_dir(), "user_data", "user-icons")
    user_keywords = os.path.join(get_app_data_dir(), "user_data", "keywords.json")
    widget_state = os.path.join(get_app_data_dir(), "user_data", "widget_state.json")
    script_icons_path = os.path.join(get_app_data_dir(), "data", "script-icons")


class DraggableCheckbox(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_mode_enabled = False
        self.is_dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.original_pos = None

        # Добавляем кастомные атрибуты
        self.is_custom = False
        self.custom_data = None
        self.custom_id = None
        
        # Контекстное меню для кастомных кнопок
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, pos):
        """Показывает контекстное меню только для кастомных кнопок"""
        if not self.is_custom:
            return
            
        menu = QMenu(self)

        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(self.edit_custom)
        menu.addAction(edit_action)
        
        delete_action = QAction("Удалить кнопку", self)
        delete_action.triggered.connect(self.delete_custom)
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))
    
    def delete_custom(self):
        """Удаляет кастомную кнопку"""
        parent = self.parent()
        while parent and not hasattr(parent, 'delete_custom_button_by_id'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'delete_custom_button_by_id'):
            parent.delete_custom_button_by_id(self.custom_id)

    def edit_custom(self):
        parent = self.parent()
        while parent and not hasattr(parent, 'edit_custom_button_by_id'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'edit_custom_button_by_id'):
            parent.edit_custom_button_by_id(self.custom_id)

    def set_drag_mode(self, enabled):
        self.drag_mode_enabled = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_mode_enabled:
            self.is_dragging = False
            self.drag_start_position = event.pos()
            self.original_pos = self.pos()
        else:
            # В обычном режиме разрешаем стандартную обработку чекбокса
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.drag_mode_enabled:
            return super().mouseMoveEvent(event)

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if not hasattr(self, 'drag_start_position'):
            return

        if not self.is_dragging:
            if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
                return

            # Начинаем перетаскивание
            self.is_dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            # Сообщаем родителю о начале перетаскивания
            parent = self.parent()
            while parent and not hasattr(parent, 'start_dragging'):
                parent = parent.parent()

            if parent and hasattr(parent, 'start_dragging'):
                parent.start_dragging(self)

        # Обновляем позицию перетаскиваемого элемента
        if self.is_dragging:
            parent = self.parent()
            while parent and not hasattr(parent, 'update_drag_position'):
                parent = parent.parent()

            if parent and hasattr(parent, 'update_drag_position'):
                global_pos = self.mapToGlobal(event.pos())
                local_pos = parent.mapFromGlobal(global_pos)
                parent.update_drag_position(local_pos, self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

            # Сообщаем родителю о завершении перетаскивания
            parent = self.parent()
            while parent and not hasattr(parent, 'stop_dragging'):
                parent = parent.parent()

            if parent and hasattr(parent, 'stop_dragging'):
                parent.stop_dragging(self)

        if hasattr(self, 'drag_start_position'):
            delattr(self, 'drag_start_position')

        super().mouseReleaseEvent(event)


class DragContainer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_target_index = -1
        self.setAcceptDrops(True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.dragged_widget = None

        self.drop_indicator = QFrame()
        self.drop_indicator.setFixedHeight(3)
        self.drop_indicator.hide()

        self.placeholder = QFrame()
        self.placeholder.setFixedHeight(40)
        self.placeholder.setStyleSheet("background-color: transparent")
        self.placeholder.hide()

    def addCheckbox(self, checkbox):
        self.layout.addWidget(checkbox)

    def set_drag_mode(self, enabled):
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, DraggableCheckbox):
                widget.set_drag_mode(enabled)

    def start_dragging(self, widget):
        self.dragged_widget = widget

        self.original_object_name = widget.objectName()
        widget.setObjectName("DraggedCheckbox")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

        # УДАЛЯЕМ виджет из layout перед началом перетаскивания
        self.layout.removeWidget(widget)
        widget.setParent(self)
        widget.show()

        # Запоминаем оригинальную позицию для плейсхолдера
        self.placeholder_index = self.layout.indexOf(widget)

        # Поднимаем перетаскиваемый виджет над остальными
        widget.raise_()

    def update_drag_position(self, pos, widget):
        if not self.dragged_widget:
            return

        # Перемещаем виджет за курсором
        widget.move(pos.x() - widget.drag_start_position.x(),
                    pos.y() - widget.drag_start_position.y())

        # Находим новую позицию для вставки
        new_index = self.find_drop_index(pos)

        # Обновляем плейсхолдер только если позиция изменилась
        if hasattr(self, 'current_target_index') and new_index != self.current_target_index:
            self.current_target_index = new_index
            self.update_placeholder_position(new_index)

        # Обновляем индикатор
        self.update_drop_indicator(new_index)

    def update_placeholder_position(self, new_index):
        # Удаляем плейсхолдер если он уже есть
        if self.placeholder.parent() == self:
            self.layout.removeWidget(self.placeholder)

        # Вставляем плейсхолдер на новую позицию
        self.layout.insertWidget(new_index, self.placeholder)
        self.placeholder.show()

    def stop_dragging(self, widget):
        if not self.dragged_widget:
            return

        # Восстанавливаем оригинальное имя
        if hasattr(self, 'original_object_name'):
            widget.setObjectName(self.original_object_name)

        # Определяем финальную позицию
        final_index = self.drop_indicator_index if hasattr(self, 'drop_indicator_index') else self.placeholder_index

        # Удаляем плейсхолдер
        if self.placeholder.parent() == self:
            self.layout.removeWidget(self.placeholder)
        self.placeholder.hide()

        # ВОЗВРАЩАЕМ виджет в layout на новую позицию
        self.layout.insertWidget(final_index, widget)

        # Сбрасываем стиль и курсор
        widget.setStyleSheet("")
        widget.setCursor(Qt.CursorShape.OpenHandCursor)

        # Скрываем индикатор
        self.drop_indicator.hide()
        self.dragged_widget = None
        self.current_target_index = -1

    def find_drop_index(self, pos):
        closest_index = -1
        min_distance = float('inf')

        # Буферная зона вверху (первые 20 пикселей) - всегда вставляем в начало
        if pos.y() < 20:
            return 0

        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if widget and widget != self.placeholder and widget != self.dragged_widget:
                widget_rect = widget.geometry()

                # Проверяем попадание в область виджета
                if widget_rect.contains(pos):
                    # Решаем, вставлять до или после элемента
                    if pos.y() < widget_rect.center().y():
                        return i  # Вставляем перед этим элементом
                    else:
                        return i + 1  # Вставляем после этого элемента

                # Если не попали в область, ищем ближайший элемент
                distance_to_top = abs(widget_rect.top() - pos.y())
                distance_to_bottom = abs(widget_rect.bottom() - pos.y())
                distance = min(distance_to_top, distance_to_bottom)

                if distance < min_distance:
                    min_distance = distance
                    if pos.y() < widget_rect.center().y():
                        closest_index = i
                    else:
                        closest_index = i + 1

        return closest_index if closest_index != -1 else self.layout.count()

    def update_drop_indicator(self, index):
        if index == -1:
            self.drop_indicator.hide()
            return

        self.drop_indicator_index = index

        if index < self.layout.count():
            target_widget = self.layout.itemAt(index).widget()
            if target_widget and target_widget != self.placeholder:
                indicator_y = target_widget.geometry().top() - 2
                self.drop_indicator.setParent(self)
                self.drop_indicator.move(10, indicator_y)
                self.drop_indicator.setFixedWidth(self.width() - 20)
                self.drop_indicator.show()
                return

        # Если вставляем в конец
        if self.layout.count() > 0:
            last_widget = self.layout.itemAt(self.layout.count() - 1).widget()
            if last_widget and last_widget != self.placeholder:
                indicator_y = last_widget.geometry().bottom() + 2
                self.drop_indicator.setParent(self)
                self.drop_indicator.move(10, indicator_y)
                self.drop_indicator.setFixedWidth(self.width() - 20)
                self.drop_indicator.show()
            else:
                self.drop_indicator.hide()
        else:
            self.drop_indicator.hide()


class NonClosingComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_open = False

    def showPopup(self):
        super().showPopup()
        self._popup_open = True
        # Устанавливаем глобальный фильтр событий
        QApplication.instance().installEventFilter(self)

    def hidePopup(self):
        # Блокируем автоматическое закрытие
        if not self._popup_open:
            super().hidePopup()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and self._popup_open:
            # Получаем позицию клика в глобальных координатах
            mouse_event = event
            global_pos = mouse_event.globalPos()

            # Геометрия выпадающего списка
            popup = self.view()
            popup_global_rect = popup.rect()
            popup_global_rect.moveTo(popup.mapToGlobal(popup_global_rect.topLeft()))

            # Геометрия комбобокса
            combo_global_rect = self.rect()
            combo_global_rect.moveTo(self.mapToGlobal(combo_global_rect.topLeft()))

            # Если клик вне обоих областей - закрываем
            if not popup_global_rect.contains(global_pos) and not combo_global_rect.contains(global_pos):
                self._popup_open = False
                QApplication.instance().removeEventFilter(self)
                super().hidePopup()
                return True

        return False

    def closePopup(self):
        self._popup_open = False
        QApplication.instance().removeEventFilter(self)
        super().hidePopup()


class SettingsWidgetPanel(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.main = main_window
        self.setObjectName("CustomPageWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.widget_state = widget_state
        self.state_manager = WindowStateManager()
        self.loaded_state = self.state_manager.load_state()
        self.is_snow = self.loaded_state["is_snow"]
        self.drag_mode = False
        self._help_initialized = False
        self.fonts_list = fonts_list
        self.init_ui()
        self.ensure_default_settings()
        self.load_saved_font()
        self.load_buttons_settings()

    def ensure_default_settings(self):
        """Создает файл с дефолтными настройками если его нет"""
        if not os.path.exists(self.widget_state):
            default_data = {
                "default_buttons": self.get_default_list(),
                "buttons": self.get_default_btns_states(),
                "custom_buttons": []
            }
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)

        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            need_save = False
        
            if "default_buttons" not in settings_data or not settings_data["default_buttons"]:
                settings_data["default_buttons"] = self.get_default_list()
                need_save = True
            
            if "buttons" not in settings_data or not settings_data["buttons"]:
                settings_data["buttons"] = self.get_default_btns_states()
                need_save = True

            if need_save:
                with open(self.widget_state, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[SETTINGS] Ошибка проверки настроек: {e}")
        
    def showEvent(self, event):
        """При показе панели настраиваем help system"""
        super().showEvent(event)
        if not self._help_initialized and hasattr(self.main, 'install_event_filter_recursive'):
            self.main.install_event_filter_recursive(self)
            self._help_initialized = True

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("CustomPageContent")
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title = setup_custom_font_label("Кастомизация виджета",)
        self.title.setStyleSheet("background: transparent; font-size: 18px")
        layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кнопка для включения/выключения режима перетаскивания
        self.drag_toggle_btn = QPushButton("Настроить порядок расположения")
        self.drag_toggle_btn.clicked.connect(self.toggle_drag_mode)
        self.drag_toggle_btn.setProperty("helpId", "drag_toggle_btn")
        layout.addWidget(self.drag_toggle_btn)

        drag_layout = QVBoxLayout()

        self.drag_container = DragContainer()
        self.drag_container.setProperty("helpId", "drag_toggle_btn")
        self.drag_container.setStyleSheet("background: transparent")
        self.drag_container.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.drag_container.layout.setSpacing(10)
        self.drag_container.layout.setContentsMargins(5, 5, 5, 5)

        drag_layout.addWidget(self.drag_container)

        layout.addLayout(drag_layout)

        self.add_custom_btn = QPushButton("Добавить кастомную кнопку")
        self.add_custom_btn.setProperty("helpId", "add_custom_btn")
        self.add_custom_btn.clicked.connect(self.show_create_custom_widget)
        layout.addWidget(self.add_custom_btn)

        font_layout = QHBoxLayout()

        # Лейбл с временем для демонстрации шрифта
        self.font_preview_label = QLabel("12:34")
        self.font_preview_label.setObjectName("preview_clock")
        self.font_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_preview_label.setStyleSheet("background: transparent; padding: 5px;")

        self.font_combo = NonClosingComboBox()
        self.font_combo.setProperty("helpId", "font_combo")
        self.font_combo.addItems(self.fonts_list.keys())
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(self.font_preview_label)
        layout.addLayout(font_layout)
        self.setup_font_selector()
        
        self.toggles_label = setup_custom_font_label("Прочие параметры")
        self.toggles_label.setStyleSheet("background: transparent; font-size: 16px")
        layout.addWidget(self.toggles_label)

        self.delay_layout = QHBoxLayout()


        self.delay_label = QLabel("Задержка перед скрытием кнопок:")
        self.delay_label.setStyleSheet("background: transparent;")
        self.delay_label.setProperty("helpId", "delay_label")
        self.delay_layout.addWidget(self.delay_label)

        self.txt_delay = QLineEdit()
        self.txt_delay.setProperty("helpId", "delay_label")
        self.txt_delay.setFixedSize(50, 30)
        self.txt_delay.setPlaceholderText("10")
        self.txt_delay.setText(str(self.load_saved_delay()))

        # Добавляем валидатор для чисел с плавающей точкой
        regex = QRegularExpression(r'^(\d{1,2}(\.\d)?|\.\d)$')
        validator = QRegularExpressionValidator(regex, self)
        self.txt_delay.setValidator(validator)
        self.delay_layout.addWidget(self.txt_delay)
        self.delay_layout.addStretch()

        layout.addLayout(self.delay_layout)
        
        self.snow_panel_checkbox = CustomToggle("Частицы снега на панели")
        self.snow_panel_checkbox.setStyleSheet("background: transparent;")
        self.snow_panel_checkbox.setToolTip("Показывать снег на панели")
        self.snow_panel_checkbox.setChecked(self.is_snow)
        self.snow_panel_checkbox.stateChanged.connect(self.toggle_snow)
        self.snow_panel_checkbox.setProperty("helpId", "snow_panel_checkbox")
        layout.addWidget(self.snow_panel_checkbox)
        
        layout.addStretch()
        
        bottom_layout = QHBoxLayout()
        
        self.get_widget_btn = QPushButton("Открыть виджет", self)
        self.get_widget_btn.setStyleSheet("padding-left: 10px; padding-right: 10px")
        self.get_widget_btn.clicked.connect(self.get_widget)
        bottom_layout.addWidget(self.get_widget_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        bottom_layout.addStretch()
        
        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setStyleSheet("padding-left: 10px; padding-right: 10px")
        self.default_btn.clicked.connect(self.set_default_buttons_settings)
        bottom_layout.addWidget(self.default_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(bottom_layout)

        self.save_btn = QPushButton("Применить")
        self.save_btn.clicked.connect(self.save_order)
        layout.addWidget(self.save_btn)

        main_layout.addWidget(scroll_area)

    def get_widget(self):
        self.main.open_widget()
        
    def toggle_snow(self):
        self.is_snow = self.snow_panel_checkbox.isChecked()
        self.state_manager.update_value("is_snow", self.is_snow)

    def setup_font_selector(self):
        """Настройка выбора шрифта"""
        # Подключаем сигнал изменения выбора
        self.font_combo.currentTextChanged.connect(self.change_font_preview)

        # Устанавливаем начальный шрифт
        if self.font_combo.currentText():
            self.change_font_preview(self.font_combo.currentText())

    def get_font_size_for_family(self, font_family):
        """Возвращает размер шрифта в зависимости от семейства"""
        font_sizes = {
            'digital': '16px',
            'grape_nuts': '26px',
            'cinzel_decorative': '26px',
            'michroma': '20px',
            'bruno_ace': '20px',
            'jacquard': '40px',
            'nova_round': '23px',
            'orbitron': '20px',
            'special_elite': '26px',
            'metamorphous': '24px',
        }

        # Ищем подходящий размер
        font_lower = font_family.lower()
        for font_name, size in font_sizes.items():
            if font_name in font_lower:
                return size

        return '18px'

    def apply_font_styles(self, font_family, font_name):
        """Применить шрифт с индивидуальным размером для каждого семейства"""
        font_size = self.get_font_size_for_family(font_name)

        logger.info(f"[SETTINGS-WIDGET] Применение шрифта для превью: {font_family} с размером: {font_size}")

        styles = f"""
            #preview_clock {{
                font-family: "{font_family}";
                font-size: {font_size};
                font-weight: normal;
                padding: 0px;
                background: transparent;
            }}
        """

        if self.font_preview_label.objectName() != "preview_clock":
            self.font_preview_label.setObjectName("preview_clock")

        self.font_preview_label.setStyleSheet(styles)

    def change_font_preview(self, font_name):
        """Изменение шрифта в превью"""
        if font_name in self.fonts_list:
            font_path = self.fonts_list[font_name]
            # Загружаем шрифт
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    font_family = font_families[0]

                    # Используем новый метод apply_font_styles
                    self.apply_font_styles(font_family, font_name)

    def get_selected_font(self):
        """Получить выбранный шрифт"""
        font_name = self.font_combo.currentText()
        if font_name in self.fonts_list:
            return self.fonts_list[font_name]
        return None

    def get_selected_font_family(self):
        """Получить семейство выбранного шрифта"""
        font_name = self.font_combo.currentText()
        if font_name in self.fonts_list:
            font_path = self.fonts_list[font_name]
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        return "Arial"  # Fallback шрифт

    def load_saved_font(self):
        """Загрузка сохраненного шрифта при запуске"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем есть ли сохраненный шрифт
            if "font_family" in data:
                saved_font = data["font_family"]

                # Устанавливаем в комбобокс
                if saved_font in self.fonts_list:
                    index = self.font_combo.findText(saved_font)
                    if index >= 0:
                        self.font_combo.setCurrentIndex(index)

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[SETTINGS-WIDGET] Не удалось загрузить сохраненный шрифт: {e}")
            # Устанавливаем шрифт по умолчанию
            default_index = self.font_combo.findText("digital")
            if default_index >= 0:
                self.font_combo.setCurrentIndex(default_index)

    def load_saved_delay(self):
        with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)

        if "delay" in data:
            delay = data["delay"]
        else:
            delay = 10

        return delay

    def create_checkboxes(self):
        checkboxes_data = [
            ("turnoff_check", "Выключение компьютера"),
            ("settings_check", "Открыть настройки"),
            ("screenshot_check", "Сделать скриншот"),
            ("open_youtube", "Запустить YouTube"),
            ("microphone_check", "Управление микрофоном в Discord"),
            ("links_check", "Открыть папку с ярлыками"),
            ("resize_check", "Развернуть окно ассистента"),
        ]

        # Очищаем контейнер перед добавлением
        for i in reversed(range(self.drag_container.layout.count())):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for key, text in checkboxes_data:
            checkbox = DraggableCheckbox(text)
            self.checkboxes[key] = checkbox
            self.drag_container.layout.addWidget(checkbox)

    def toggle_drag_mode(self):
        self.drag_mode = not self.drag_mode
        self.drag_container.set_drag_mode(self.drag_mode)

        if self.drag_mode:
            self.drag_toggle_btn.setText("Режим перетаскивания: ВКЛ")
            # В режиме перетаскивания только меняем курсор, но не блокируем чекбоксы
            for checkbox in self.checkboxes.values():
                checkbox.setCursor(Qt.CursorShape.OpenHandCursor)
                # Сохраняем текущее состояние checked для отображения
                checkbox.update()
        else:
            self.drag_toggle_btn.setText("Настроить порядок расположения")
            # Возвращаем обычный курсор
            for checkbox in self.checkboxes.values():
                checkbox.setCursor(Qt.CursorShape.ArrowCursor)

    def get_checkbox_order(self):
        order = []
        for i in range(self.drag_container.layout.count()):
            widget = self.drag_container.layout.itemAt(i).widget()
            if isinstance(widget, DraggableCheckbox):
                for key, cb in self.checkboxes.items():
                    if cb == widget:
                        order.append(key)
                        break
        return order

    def get_buttons_data(self):
        """Получить данные о кнопках в порядке их расположения"""
        buttons_data = {}

        for i in range(self.drag_container.layout.count()):
            widget = self.drag_container.layout.itemAt(i).widget()
            
            if widget and isinstance(widget, DraggableCheckbox):
                for key, checkbox in self.checkboxes.items():
                    if checkbox == widget:
                        buttons_data[key] = checkbox.isChecked()
                        break

        return buttons_data
    
    def reorder_checkboxes_by_buttons(self, buttons_order):
        """Переставляет чекбоксы в порядке из buttons"""
        for i in reversed(range(self.drag_container.layout.count())):
            widget = self.drag_container.layout.itemAt(i).widget()
            if widget:
                self.drag_container.layout.removeWidget(widget)
        
        for key in buttons_order.keys():
            if key in self.checkboxes:
                checkbox = self.checkboxes[key]
                self.drag_container.layout.addWidget(checkbox)

    def load_buttons_settings(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)

            default_buttons = settings_data.get("default_buttons", {})
            buttons_states = settings_data.get("buttons", {})
            custom_buttons = settings_data.get("custom_buttons", [])

            if not default_buttons:
                default_buttons = self.get_default_list()
                settings_data["default_buttons"] = default_buttons

            if not buttons_states:
                buttons_states = self.get_default_btns_states()
                settings_data["buttons"] = buttons_states

            self.checkboxes.clear()
            for i in reversed(range(self.drag_container.layout.count())):
                widget = self.drag_container.layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            for key, btn_data in default_buttons.items():
                text = btn_data.get('tooltip', key)
                checkbox = DraggableCheckbox(text)
                self.checkboxes[key] = checkbox

            if custom_buttons:
                for custom_data in custom_buttons:
                    key = f"custom_{custom_data['id']}"
                    checkbox = DraggableCheckbox(custom_data['name'])
                    checkbox.is_custom = True
                    checkbox.custom_data = custom_data
                    checkbox.custom_id = custom_data['id']
                    self.checkboxes[key] = checkbox

            updated_buttons_states = buttons_states.copy()
            
            for key in self.checkboxes.keys():
                if key not in updated_buttons_states:
                    updated_buttons_states[key] = True

            if updated_buttons_states != buttons_states:
                settings_data["buttons"] = updated_buttons_states
                with open(self.widget_state, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, indent=4, ensure_ascii=False)

            for key in default_buttons.keys():
                if key in self.checkboxes:
                    checkbox = self.checkboxes[key]
                    state = updated_buttons_states.get(key, True)
                    checkbox.setChecked(state)
                    self.drag_container.layout.addWidget(checkbox)
            
            for custom_data in custom_buttons:
                key = f"custom_{custom_data['id']}"
                if key in self.checkboxes:
                    checkbox = self.checkboxes[key]
                    state = updated_buttons_states.get(key, True)
                    checkbox.setChecked(state)
                    self.drag_container.layout.addWidget(checkbox)

            if buttons_states:
                self.reorder_checkboxes_by_buttons(buttons_states)
            return True

        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки кнопок: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def get_default_list(self):
        data = {
            "turnoff_check": {
                "tooltip": "Выключение компьютера",
                "icon_rel_path": "power.svg"
            },
            "settings_check": {
                "tooltip": "Открыть настройки",
                "icon_rel_path": "settings.svg"
            },
            "screenshot_check": {
                "tooltip": "Сделать скриншот",
                "icon_rel_path": "camera.svg"
            },
            "open_youtube": {
                "tooltip": "Запустить YouTube",
                "icon_rel_path": "logo-youtube.svg"
            },
            "microphone_check": {
                "tooltip": "Управление микрофоном в Discord",
                "icon_rel_path": "mic_on.svg"
            },
            "links_check": {
                "tooltip": "Открыть папку с ярлыками",
                "icon_rel_path": "shortcut.svg"
            },
            "resize_check": {
                "tooltip": "Развернуть окно ассистента",
                "icon_rel_path": "open_main.svg"
            }
        }
        return data
    
    def get_default_btns_states(self):
        data = {
            "turnoff_check": True,
            "settings_check": True,
            "screenshot_check": True,
            "open_youtube": True,
            "microphone_check": True,
            "links_check": True,
            "resize_check": True
        }   
        return data

    def set_default_buttons_settings(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            
            default_buttons = settings_data.get("default_buttons", {})
            custom_buttons = settings_data.get("custom_buttons", [])
            
            # Создаем дефолтные состояния
            new_buttons = {}
            
            # Стандартные = True
            for key in default_buttons.keys():
                new_buttons[key] = True
            
            # Кастомные = False
            for custom_data in custom_buttons:
                key = f"custom_{custom_data['id']}"
                new_buttons[key] = False
            
            # Сохраняем
            settings_data["buttons"] = new_buttons
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False)
            
            # Перезагружаем
            self.load_buttons_settings()
            
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка сброса настроек: {e}")

    def save_order(self):
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            existing_data["delay"] = float(self.txt_delay.text().strip())

            existing_data["font_family"] = self.font_combo.currentText()
            
            existing_data["buttons"] = self.get_buttons_data()

            if "custom_buttons" not in existing_data:
                current_custom_buttons = []
                for key, checkbox in self.checkboxes.items():
                    if key.startswith('custom_') and hasattr(checkbox, 'custom_data'):
                        current_custom_buttons.append(checkbox.custom_data)
                existing_data["custom_buttons"] = current_custom_buttons
            
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            
            QTimer.singleShot(100, widget_btns_signal.buttons_updated.emit)
            
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка сохранения порядка: {e}")

    def show_create_custom_widget(self):
        """Показывает виджет создания кастомной кнопки"""
        all_commands = {**self.main.default_commands, **self.main.commands}
        self.create_widget = CustomBtnForPanel(
            parent=self,
            commands=all_commands
        )
        self.create_widget.custom_button_created.connect(self.add_custom_button)
        self.create_widget.show()

    def load_custom_buttons(self):
        """Загружает сохраненные кастомные кнопки"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            
            # Добавляем кастомные кнопки
            for button_data in custom_buttons:
                self.add_custom_button(button_data)
                
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки кастомных кнопок: {e}")

    def add_custom_button(self, button_data):
        """Добавляет кастомную кнопку в список"""
        key = f"custom_{button_data['id']}"
        
        checkbox = DraggableCheckbox(button_data['name'])
        
        # Устанавливаем кастомные атрибуты
        checkbox.is_custom = True
        checkbox.custom_data = button_data
        checkbox.custom_id = button_data['id']
        
        self.checkboxes[key] = checkbox
        self.drag_container.layout.addWidget(checkbox)

    def delete_custom_button_by_id(self, custom_id):
        """Удаляет кастомную кнопку по ID"""
        key = f"custom_{custom_id}"
        
        if key in self.checkboxes:
            checkbox = self.checkboxes[key]
            
            # Удаляем из layout
            self.drag_container.layout.removeWidget(checkbox)
            checkbox.deleteLater()
            
            # Удаляем из словаря
            del self.checkboxes[key]
            
            # Удаляем из JSON
            self.remove_btn_from_json(custom_id)
            
            self.save_order()

    def edit_custom_button_by_id(self, custom_id):
        """Открывает диалоговое окно для изменения параметров кнопки"""
        
        # Находим данные кнопки для редактирования
        button_data = None
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            for btn in custom_buttons:
                if btn.get('id') == custom_id:
                    button_data = btn
                    break
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки данных кнопки: {e}")
        
        if not button_data:
            self.main.show_message("Кнопка не найдена", "Ошибка", "warning")
            return
        
        # Открываем диалог с данными кнопки для редактирования
        all_commands = {**self.main.default_commands, **self.main.commands}
        self.edit_widget = CustomBtnForPanel(
            parent=self,
            commands=all_commands,
            button_data=button_data  # Передаем данные для заполнения полей
        )
        self.edit_widget.custom_button_edited.connect(self.handle_custom_button_edited)
        self.edit_widget.show()

    def handle_custom_button_edited(self, edited_button_data):
        """Обрабатывает отредактированную кнопку"""
        custom_id = edited_button_data['id']
        key = f"custom_{custom_id}"
        
        if key in self.checkboxes:
            # Обновляем текст в чекбоксе
            checkbox = self.checkboxes[key]
            checkbox.setText(edited_button_data['name'])
            checkbox.custom_data = edited_button_data
            
            # Обновляем данные в JSON
            self.update_button_in_json(edited_button_data)
            
            # Сохраняем порядок
            self.save_order()

    def update_button_in_json(self, button_data):
        """Обновляет кнопку в JSON файле"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            custom_buttons = data.get('custom_buttons', [])
            
            # Находим и заменяем кнопку с таким же ID
            for i, btn in enumerate(custom_buttons):
                if btn.get('id') == button_data['id']:
                    custom_buttons[i] = button_data
                    break
            
            data['custom_buttons'] = custom_buttons
            
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка обновления кнопки в JSON: {e}")


    def remove_btn_from_json(self, custom_id):
        """Удаляет кастомную кнопку из JSON файла"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Получаем список кастомных кнопок
            custom_buttons = data.get('custom_buttons', [])
            
            # Фильтруем, оставляем только те, у которых id не совпадает
            if isinstance(custom_buttons, list):
                data['custom_buttons'] = [
                    btn for btn in custom_buttons 
                    if btn.get('id') != custom_id
                ]
            elif isinstance(custom_buttons, dict):
                # Если вдруг сохранено как словарь
                if custom_id in custom_buttons:
                    del custom_buttons[custom_id]
            
            # Сохраняем обратно
            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка удаления кастомной кнопки из JSON: {e}")


class CustomBtnForPanel(QDialog):
    """Виджет для создания/редактирования кастомной кнопки"""
    custom_button_created = Signal(dict)
    custom_button_edited = Signal(dict)

    def __init__(self, parent=None, commands=None, button_data=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.drag_pos = None
        self.button_data = button_data  # Данные редактируемой кнопки (если есть)
        self.is_edit = button_data is not None
        self.btn_icons_folder = script_icons_path
        self.user_icons_folder = user_icons_folder
        self.check_folder(folder_path=[self.user_icons_folder, self.btn_icons_folder])
        self.icon_close_path = get_path("bin", "icons", "close.svg")
        self.widget_state = widget_state
        self.commands = commands or {}
        self.style_manager = main_apply_colors
        self.color_path = self.style_manager.color_path
        self.styles = self.style_manager.load_styles()
        self.monitor = ShortcutMonitor(self.user_icons_folder)
        self.monitor.folder_changed.connect(self.load_svg_list)
        self.monitor.start_monitoring()
        self.init_ui()
        self.load_svg_list()
        self.apply_styles()
        if self.is_edit:
            self.fill_with_button_data()

    def title_bar_mouse_press(self, event):
        """Обработка нажатия мыши на заголовок"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        """Обработка перемещения мыши при удерживании на заголовке"""
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPos() - self.drag_pos
            self.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        event.accept()

    def apply_styles(self):
        if hasattr(self, 'close_svg'):
            self.style_manager.apply_color_svg(self.close_svg, strength=0.90, specified_color="#ff0000")
    
    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(360, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container = QWidget(self)
        self.container.setObjectName("WindowContainer")
        self.container.setGeometry(0, 0, self.width(), self.height())

        # Кастомный заголовок
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setGeometry(1, 1, self.width() - 2, 35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 5, 10, 5)
        self.title_layout.setSpacing(5)

        self.title_bar.mousePressEvent = self.title_bar_mouse_press
        self.title_bar.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar.mouseReleaseEvent = self.title_bar_mouse_release

        if self.is_edit:
            self.title_label = setup_custom_font_label("Редактирование кнопки")
        else:
            self.title_label = setup_custom_font_label("Создание кастомной кнопки")
        self.title_label.setStyleSheet("background: transparent; font-size:16px;")
        self.title_layout.addWidget(self.title_label)

        self.close_btn = QPushButton("", self.title_bar)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("TitleBarCloseBtnV2")
        self.close_btn.clicked.connect(self.close)
        self.close_svg = CustomSvgWidget(self.icon_close_path, self.close_btn)
        self.close_svg.setFixedSize(24, 24)
        self.close_svg.move(3, 3)
        self.close_svg.setStyleSheet("background: transparent;")
        self.title_layout.addWidget(self.close_btn)

        # Основной контент
        self.content_widget = QWidget(self.container)
        self.content_widget.setGeometry(1, 36, self.width() - 2, self.height() - 37)
        self.content_widget.setObjectName("ContentWidget")

        self.main_content_layout = QVBoxLayout(self.content_widget)
        self.main_content_layout.setContentsMargins(15, 15, 15, 15)
        self.main_content_layout.setSpacing(5)

        # Выпадающий список SVG с иконками
        icon_layout = QHBoxLayout()

        self.preview_svg = CustomSvgWidget("")
        self.preview_svg.setFixedSize(30, 30)
        icon_layout.addWidget(self.preview_svg) 

        self.icon_combo = NonClosingComboBox()
        self.icon_combo.currentIndexChanged.connect(self.update_preview)
        icon_layout.addWidget(self.icon_combo)

        self.main_content_layout.addLayout(icon_layout)

        self.name_label = setup_custom_font_label("Назначение кнопки")
        self.name_label.setStyleSheet("background: transparent; font-style: 14px;")
        self.main_content_layout.addWidget(self.name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: Запуск скрипта")
        self.main_content_layout.addWidget(self.name_input)
        
        # Выбор команды
        self.command_label = setup_custom_font_label("Команда:")
        self.command_label.setStyleSheet("background: transparent; font-style: 14px;")
        self.main_content_layout.addWidget(self.command_label)

        self.command_combo = QComboBox()
        self.command_combo.addItems(list(self.commands.keys()))
        self.main_content_layout.addWidget(self.command_combo)

        action_layout = QHBoxLayout()
        
        lbl_action = QLabel("Действие:")
        lbl_action.setStyleSheet("background: transparent;")
        action_layout.addWidget(lbl_action)
        
        self.cmb_action = QComboBox()
        self.cmb_action.addItems(["open", "close"])
        action_layout.addWidget(self.cmb_action)
        
        self.main_content_layout.addLayout(action_layout)

        # Label для ошибок
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px; background-color: transparent; height: 15px;")
        self.error_label.setVisible(False)
        self.main_content_layout.addWidget(self.error_label)

        self.main_content_layout.addStretch()
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.open_script_folder = QPushButton("Папка с иконками")
        self.open_script_folder.clicked.connect(lambda: self.open_folder(path=self.user_icons_folder))
        self.open_script_folder.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_layout.addWidget(self.open_script_folder)

        btn_layout.addStretch()

        if self.is_edit:
            self.save_btn = QPushButton("Сохранить")
            self.save_btn.clicked.connect(self.save_button)
        else:
            self.save_btn = QPushButton("Создать")
            self.save_btn.clicked.connect(self.save_button)
        self.save_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)
        
        self.main_content_layout.addLayout(btn_layout)
    
    def load_svg_list(self):
        """Загружает SVG файлы из папки"""
        self.icon_combo.clear()
        self.icon_paths = {}  # Словарь для быстрого поиска индекса по пути

        if os.path.exists(self.btn_icons_folder):
            svg_files = []
            
            for file in sorted(os.listdir(self.btn_icons_folder)):
                if file.lower().endswith('.svg'):
                    svg_files.append(file)
            
            if svg_files:
                for svg_file in svg_files:
                    icon_name = os.path.splitext(svg_file)[0]
                    icon_path = os.path.join(self.btn_icons_folder, svg_file)
                    self.icon_combo.addItem(icon_name, icon_path)
                    self.icon_paths[icon_path] = self.icon_combo.count() - 1

        if os.path.exists(self.user_icons_folder):
            svg_files = []
            
            for file in sorted(os.listdir(self.user_icons_folder)):
                if file.lower().endswith('.svg'):
                    svg_files.append(file)
            
            if svg_files:
                for svg_file in svg_files:
                    icon_name = os.path.splitext(svg_file)[0]
                    icon_path = os.path.join(self.user_icons_folder, svg_file)
                    self.icon_combo.addItem(icon_name, icon_path)
                    self.icon_paths[icon_path] = self.icon_combo.count() - 1

    def fill_with_button_data(self):
        """Заполняет поля данными редактируемой кнопки"""
        if not self.button_data:
            return
        
        # Заполняем название
        self.name_input.setText(self.button_data.get('name', ''))
        
        # Устанавливаем иконку
        icon_path = self.button_data.get('icon_path', '')
        if icon_path and icon_path in self.icon_paths:
            index = self.icon_paths[icon_path]
            self.icon_combo.setCurrentIndex(index)
        elif icon_path and os.path.exists(icon_path):
            # Если путь не найден в списке, добавляем его
            icon_name = os.path.splitext(os.path.basename(icon_path))[0]
            self.icon_combo.addItem(icon_name, icon_path)
            self.icon_combo.setCurrentIndex(self.icon_combo.count() - 1)
        
        # Устанавливаем команду
        name_command = self.button_data.get('name_command', '')
        index = self.command_combo.findText(name_command)
        if index >= 0:
            self.command_combo.setCurrentIndex(index)
        
        # Устанавливаем действие
        move_command = self.button_data.get('move_command', 'open')
        index = self.cmb_action.findText(move_command)
        if index >= 0:
            self.cmb_action.setCurrentIndex(index)

    def update_preview(self, index):
        """Обновляет превью выбранной иконки"""
        icon_path = self.icon_combo.itemData(index)
        
        if icon_path and os.path.exists(icon_path):
            try:
                self.preview_svg.load(icon_path)
                self.style_manager.apply_color_svg(self.preview_svg, strength=0.9)
                self.preview_svg.update()
            except Exception as e:
                logger.error(f"[SETTINGS-WIDGET] Ошибка загрузки превью: {e}")
                self.preview_svg.load("")
        else:
            self.preview_svg.load("")

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def hide_error(self):
        """Скрывает сообщение об ошибке."""
        self.error_label.setVisible(False)

    def check_folder(self, folder_path: list):
        try:
            for path in folder_path:
                if os.path.exists(path) and os.path.isdir(path):
                    pass
                else:
                    os.makedirs(path)
                    logger.info(f'[SETTINGS-WIDGET] Папка "{path}" была создана.')
        except Exception as e:
            logger.error(f'[SETTINGS-WIDGET] Ошибка при создании папки: {e}')

    def open_folder(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            logger.error(f'[SETTINGS-WIDGET] Ошибка при открытии папки: {e}')

    def save_button(self):
        """Создает или обновляет объект кастомной кнопки"""
        name = self.name_input.text().strip()
        if not name:
            self.show_error("Введите название кнопки")
            return
        
        icon_path = self.icon_combo.currentData()
        name_command = self.command_combo.currentText()
        
        if not name_command:
            self.show_error("Выберите команду")
            return
        
        command_data = self.commands.get(name_command)
    
        if not command_data:
            self.show_error("Ошибка: команда не найдена в словаре")
            return
        
        move_command = self.cmb_action.currentText()
        
        # Генерируем новый ID только для создания
        if self.is_edit:
            button_id = self.button_data.get('id')
        else:
            button_id = self.generate_unique_id(8)
        
        # Создаем объект кастомной кнопки
        custom_button_data = {
            'id': button_id,
            'name': name,
            'icon_path': icon_path if icon_path else "",
            'name_command': name_command,
            'type_command': command_data.get('type', 'unknown'),
            'move_command': move_command,
            'command_data': command_data
        }

        if self.is_edit:
            self.update_btn_data(custom_button_data)
            self.custom_button_edited.emit(custom_button_data)
        else:
            self.save_btn_data(custom_button_data)
            self.custom_button_created.emit(custom_button_data)
        
        self.close()

    def save_btn_data(self, custom_data):
        """Сохраняет новую кнопку в JSON"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            if 'custom_buttons' not in existing_data:
                existing_data['custom_buttons'] = []
            elif isinstance(existing_data['custom_buttons'], dict):
                existing_data['custom_buttons'] = [existing_data['custom_buttons']]

            existing_data['custom_buttons'].append(custom_data)

            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка сохранения кнопки: {e}")

    def update_btn_data(self, custom_data):
        """Обновляет существующую кнопку в JSON"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            if 'custom_buttons' not in existing_data:
                existing_data['custom_buttons'] = []
            elif isinstance(existing_data['custom_buttons'], dict):
                existing_data['custom_buttons'] = [existing_data['custom_buttons']]

            # Находим и заменяем кнопку с таким же ID
            updated = False
            for i, btn in enumerate(existing_data['custom_buttons']):
                if btn.get('id') == custom_data['id']:
                    existing_data['custom_buttons'][i] = custom_data
                    updated = True
                    break
            
            if not updated:
                # Если не нашли, добавляем как новую
                existing_data['custom_buttons'].append(custom_data)

            with open(self.widget_state, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка обновления кнопки: {e}")

    def generate_unique_id(self, length=8):
        """Генерирует уникальный ID с проверкой на существование"""
        try:
            with open(self.widget_state, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            existing_ids = set()
            custom_buttons = existing_data.get('custom_buttons', [])
            
            for btn in custom_buttons:
                if isinstance(btn, dict) and 'id' in btn:
                    existing_ids.add(btn['id'])
            
            alphabet = string.ascii_lowercase + string.digits
            while True:
                new_id = ''.join(secrets.choice(alphabet) for _ in range(length))
                if new_id not in existing_ids:
                    return new_id
                    
        except Exception as e:
            logger.error(f"[SETTINGS-WIDGET] Ошибка генерации ID: {e}")
            # Fallback: обычная генерация без проверки
            alphabet = string.ascii_lowercase + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def closeEvent(self, event):
        self.monitor.stop_monitoring()
        super().closeEvent(event)
