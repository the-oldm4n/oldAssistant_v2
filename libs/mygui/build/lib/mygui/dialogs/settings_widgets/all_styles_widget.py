import json
import os
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget,\
    QDialog, QMenu, QMessageBox, QScrollArea, QSizePolicy, QGridLayout
from PySide6.QtCore import Signal, Qt
from mygui import color_signal, update_presets_signal
from mygui.config import mygui_config
from mygui.dialogs.edit_dialog import EditDialog


class AllStylesWidget(QWidget):
    """Виджет настроек оформления интерфейса"""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.main = main
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomPageWidget")
        update_presets_signal.presets_updated.connect(self.load_custom_styles)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        title = QLabel("Выбор стиля интерфейса")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.styles_widget = QWidget()
        self.styles_widget.setObjectName("CustomPageContent")
        self.styles_layout = QVBoxLayout(self.styles_widget)
        self.styles_layout.setSpacing(15)
        self.styles_layout.setContentsMargins(5, 5, 5, 5)

        base_presets = mygui_config.presets_path
        self.load_styles_from_folder(base_presets, self.styles_layout, is_custom=False)

        self.custom_label = QLabel("Кастомные стили")
        self.custom_label.setStyleSheet("background: transparent; font-size: 14px;")
        self.styles_layout.addWidget(self.custom_label)

        self.custom_styles_container = QWidget()
        self.custom_styles_container.setStyleSheet("background: transparent;")
        self.custom_styles_layout = QVBoxLayout(self.custom_styles_container)
        self.custom_styles_layout.setContentsMargins(0, 0, 0, 0)
        self.styles_layout.addWidget(self.custom_styles_container)

        self.load_custom_styles()

        self.styles_layout.addStretch()

        scroll_area.setWidget(self.styles_widget)
        layout.addWidget(scroll_area, stretch=1)

    def load_custom_styles(self):
        """Загружает пользовательские стили в отдельный контейнер"""
        while self.custom_styles_layout.count():
            child = self.custom_styles_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_nested_layout(child.layout())

        custom_grid = QGridLayout()
        custom_grid.setSpacing(10)
        custom_grid.setContentsMargins(0, 5, 0, 5)

        grid_container = QWidget()
        grid_container.setLayout(custom_grid)
        self.custom_styles_layout.addWidget(grid_container)

        custom_presets = mygui_config.custom_presets_path

        if os.path.exists(custom_presets):
            try:
                style_files = [f for f in os.listdir(custom_presets) 
                            if f.endswith('.json') and os.path.isfile(os.path.join(custom_presets, f))]
                style_files.sort()
                
                if not style_files:
                    no_styles_label = QLabel("Пусто")
                    no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                    custom_grid.addWidget(no_styles_label, 0, 0, 1, 3)
                else:
                    for i, filename in enumerate(style_files):
                        row = i // 3
                        col = i % 3
                        
                        btn = self.create_style_button(filename, custom_presets, is_custom=True)
                        if btn:
                            custom_grid.addWidget(btn, row, col)
            
            except Exception as e:
                error_label = QLabel(f"Ошибка загрузки стилей {e}")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_label.setStyleSheet("background-color: transparent; color: red;")
                custom_grid.addWidget(error_label, 0, 0, 1, 3)
        else:
            no_styles_label = QLabel("Папка со стилями не найдена")
            no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
            custom_grid.addWidget(no_styles_label, 0, 0, 1, 3)

    def clear_nested_layout(self, layout):
        """Рекурсивно очищает вложенные layout"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_nested_layout(child.layout())

    def load_styles_from_folder(self, folder_path, container_layout, is_custom=False):
        """Загружает стили из папки и создает кнопки"""
        if not os.path.exists(folder_path):
            if is_custom:
                no_styles_label = QLabel("Папка со стилями не найдена")
                no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                container_layout.addWidget(no_styles_label, 0, 0, 1, 3)
            return

        try:
            style_files = [f for f in os.listdir(folder_path) 
                        if f.endswith('.json') and os.path.isfile(os.path.join(folder_path, f))]
        except Exception as e:
            print(f"[SETTINGS-WIDGET] Ошибка чтения папки {folder_path}: {e}")
            return

        if not style_files:
            if is_custom:
                no_styles_label = QLabel("Папка со стилями не найдена")
                no_styles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_styles_label.setStyleSheet("background-color: transparent; font-style: italic;")
                container_layout.addWidget(no_styles_label, 0, 0, 1, 3)
            return

        style_files.sort()

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 5, 0, 5)

        for i, filename in enumerate(style_files):
            row = i // 3
            col = i % 3
            
            btn = self.create_style_button(filename, folder_path, is_custom)
            if btn:
                grid_layout.addWidget(btn, row, col)
        container_layout.addLayout(grid_layout)

    def apply_style_from_button(self, file_path, filename, is_custom=False):
        """Применяет стиль при клике на кнопку"""
        try:
            file_name_only = os.path.basename(filename) if isinstance(filename, str) else filename
            self.apply_style_file(file_name_only)
            
        except Exception as e:
            print(f"[SETTINGS-WIDGET] Ошибка применения стиля {filename}: {e}")

    def create_style_button(self, filename, folder_path, is_custom=False):
        """Создает кнопку стиля с предпросмотром цвета"""
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                style_data = json.load(f)

            preview_color = self.extract_preview_color(style_data)
            style_name = os.path.splitext(filename)[0]
            style_name = style_name.replace('_', ' ').replace('-', ' ').title()

            btn = QPushButton(f"{style_name}")
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(10, 5, 10, 5)
            btn_layout.setSpacing(10)

            btn_layout.addStretch()
            btn.setLayout(btn_layout)

            btn_style = self.create_button_style(preview_color)
            btn.setStyleSheet(btn_style)

            if is_custom:
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, f=filename, p=folder_path: self.show_style_context_menu(pos, f, p, btn)
                )
                # Сохраняем оригинальное имя файла в свойстве кнопки
                btn.setProperty("original_filename", filename)
                btn.setProperty("folder_path", folder_path)

            btn.clicked.connect(lambda checked, fp=file_path, fn=filename: 
                            self.apply_style_from_button(fp, fn, is_custom))

            return btn
            
        except Exception as e:
            print(f"[SETTINGS-WIDGET] Ошибка создания кнопки для {filename}: {e}")
            btn = QPushButton(filename.replace('.json', ''))
            btn.clicked.connect(lambda: self.apply_style_file(filename))
            return btn

    def extract_preview_color(self, style_data):
        """Извлекает цвет/градиент ТОЛЬКО из BasedColors["svg"]"""
        if "BasedColors" in style_data and "svg" in style_data["BasedColors"]:
            return style_data["BasedColors"]["svg"]
        
        return "#4A90E2"

    def create_button_style(self, color_str):
        """Создает стиль кнопки на основе цвета/градиента"""
        return f"""
            QPushButton {{
                background: {color_str};
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            QPushButton:hover {{
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
        """

    def apply_style_file(self, filename):
        """Применяет стиль из указанного файла, проверяя обе директории."""
        preset_path = None
        custom_path = os.path.join(mygui_config.custom_presets_path, filename)
        base_path = os.path.join(mygui_config.presets_path, filename)

        if os.path.exists(custom_path):
            preset_path = custom_path
        elif os.path.exists(base_path):
            preset_path = base_path
        else:
            print(f"[SETTINGS-WIDGET] Пресет '{filename}' не найден ни в одной из папок.")
            return
        try:
            with open(preset_path, 'r', encoding='utf-8') as json_file:
                styles = json.load(json_file)

                with open(mygui_config.colors_path, 'w') as f:
                    json.dump(styles, f, indent=4)

                self.parent.style_manager.save_styles(styles)
                self.parent.load_color_settings(styles)
                color_signal.color_changed.emit()
                print(f"[SETTINGS-WIDGET] Применён стиль из файла: {filename}")

        except json.JSONDecodeError:
            print(f"[SETTINGS-WIDGET] Ошибка: файл пресета повреждён ({preset_path}).")
        except Exception as e:
            print(f"[SETTINGS-WIDGET] Ошибка загрузки пресета: {e}")

    def show_style_context_menu(self, pos, filename, folder_path, button):
        """Показывает контекстное меню для кастомного стиля"""
        menu = QMenu(self)

        edit_action = QAction("Редактировать название", self)
        edit_action.triggered.connect(lambda: self.edit_style_name(filename, folder_path, button))

        delete_action = QAction("Удалить стиль", self)
        delete_action.triggered.connect(lambda: self.delete_custom_style(filename, folder_path))
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)

        menu.exec_(button.mapToGlobal(pos))

    def edit_style_name(self, filename, folder_path, button):
        """Редактирует название кастомного стиля"""
        current_display_name = button.text()

        dialog = EditDialog(
            self, 
            title="Редактирование названия стиля", 
            text=current_display_name
        )

        if dialog.exec_() != QDialog.DialogCode.Accepted:
            return
        
        new_name = dialog.get_text().strip()
        
        if not new_name or new_name == current_display_name:
            return

        old_file_path = os.path.join(folder_path, filename)
        new_filename = new_name.lower().replace(' ', '_') + '.json'
        new_file_path = os.path.join(folder_path, new_filename)
        
        try:
            if os.path.exists(new_file_path):
                if self.main:
                    self.main.show_toast(f"Файл с именем '{new_name}' уже существует!")
                else:
                    print(f"Файл с именем '{new_name}' уже существует!")
                return

            os.rename(old_file_path, new_file_path)
            button.setText(new_name)
            button.setProperty("original_filename", new_filename)
            self.load_custom_styles()

            update_presets_signal.presets_updated.emit()
            if self.main:
                self.main.show_toast(f"Название изменено на: {new_name}")
            else:
                print(f"Название изменено на: {new_name}")
  
            
        except FileNotFoundError:
            print(f"[SETTINGS-WIDGET] Файл не найден: {old_file_path}")
        except PermissionError:
            print(f"[SETTINGS-WIDGET] Нет прав на переименование файла: {old_file_path}")
        except Exception as e:
            print(f"[SETTINGS-WIDGET] Ошибка при переименовании файла: {e}")

    def delete_custom_style(self, filename, folder_path):
        """Удаляет кастомный стиль"""
        file_path = os.path.join(folder_path, filename)
        if self.main:
            reply = self.main.show_message(
                text=f"Вы уверены, что хотите удалить стиль '{filename.replace('.json', '')}'?",
                title="Подтверждение удаления",
                message_type="question",
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                print("[SETTINGS-WIDGET] Удаление стиля отменено")
                return
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(file_path)
                    if self.main:
                        self.main.show_toast(f"Стиль '{filename.replace('.json', '')}' удален")
                    else:
                        print(f"Стиль '{filename.replace('.json', '')}' удален")
                    self.load_custom_styles()
                    update_presets_signal.presets_updated.emit()
                    
                except Exception as e:
                    print(f"[SETTINGS-WIDGET] Ошибка удаления стиля {filename}: {e}")
        else:
            try:
                os.remove(file_path)
                print(f"Стиль '{filename.replace('.json', '')}' удален")
                self.load_custom_styles()
                update_presets_signal.presets_updated.emit()
                
            except Exception as e:
                print(f"[SETTINGS-WIDGET] Ошибка удаления стиля {filename}: {e}")
