import json
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QRect, QObject, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QMouseEvent
from mygui import sidebar_animated_signal
from log_config import logger


class ResizeManager(QObject):
    """
    main_window han been required method 'apply_styles' and widgets: 'central_widget', 'close_button', 'title_bar_widget'
    """
    def __init__(self, winsize_file, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.winsize_file = winsize_file
        self.margin = 7
        self.drag_pos = None
        self.dragging = False
        self.drag_position = None
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.dragging_maximized = False
        self.drag_start_pos = None
        self.drag_start_geometry = None
        self._drag_click_offset = None

        self.default_size = 920, 700
        self._is_maximized = False
        self._default_geometry = QRect(300, 200, 920, 700)
        self._normal_geometry = None

        self.resize_animation = QPropertyAnimation(self.main, b"geometry")
        self.resize_animation.setDuration(100)
        self.resize_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def save_window_settings(self):
        """Сохранить размер и положение окна"""
        try:
            if not self._normal_geometry:
                if self._is_maximized:
                    self._normal_geometry = self._default_geometry
                else:
                    self._normal_geometry = self.main.geometry()

            if isinstance(self._normal_geometry, QRect):
                geom = [
                    self._normal_geometry.x(),
                    self._normal_geometry.y(),
                    self._normal_geometry.width(),
                    self._normal_geometry.height()
                ]
            else:
                geom = self._normal_geometry

            settings = {
                'geometry': geom,
                'state': {
                    '_is_maximized': self._is_maximized
                }
            }

            with open(self.winsize_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

        except Exception as e:
            logger.error(f"[RESIZE MANAGER][save_window_settings] Error: {e}")
    
    def load_window_settings(self):
        """Загрузить сохраненные размеры окна"""
        try:
            if not os.path.exists(self.winsize_file):
                with open(self.winsize_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                return {}

            with open(self.winsize_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            logger.info("[RESIZE MANAGER] Размеры окна загружены")

            if 'state' in settings:
                if settings['state'].get('is_maximized'):
                    self._is_maximized = True
                    self.showMaximized()
                else:
                    g = settings["geometry"]
                    if isinstance(g, (list, tuple)) and len(g) == 4:
                        rect = QRect(g[0], g[1], g[2], g[3])
                        self.main.setGeometry(rect)

        except Exception as e:
            logger.error(f"[RESIZE MANAGER][load_window_settings] Error: {e}")

    def get_cursor_region(self, pos):
        """Определяем область курсора для изменения размера"""
        width = self.main.width()
        height = self.main.height()
        x, y = pos.x(), pos.y()

        if self._is_maximized:
            return "center"
        
        if x <= self.margin and y <= self.margin:
            return "top-left"
        elif x >= width - self.margin and y <= self.margin:
            return "top-right"
        elif x <= self.margin and y >= height - self.margin:
            return "bottom-left"
        elif x >= width - self.margin and y >= height - self.margin:
            return "bottom-right"
        elif x <= self.margin:
            return "left"
        elif x >= width - self.margin:
            return "right"
        elif y <= self.margin:
            return "top"
        elif y >= height - self.margin:
            return "bottom"
        else:
            return "center"

    def title_bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            window_pos = self.main.mapFromGlobal(global_pos)
            region = self.get_cursor_region(window_pos)

            if self._is_maximized and region == "center":
                self.dragging_maximized = True
                self.drag_start_pos = global_pos
                self.drag_start_geometry = self.main.geometry()
                self._drag_click_offset = None
                event.accept()
                return

            if region in ["top", "top-left", "top-right", "left", "right"]:
                self.drag_direction = region
                self.dragging = True
                self.drag_position = global_pos
                self.initial_geometry = self.main.geometry()
            elif region == "center":
                self.drag_pos = global_pos - self.main.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        global_pos = event.globalPosition().toPoint()
        window_pos = self.main.mapFromGlobal(global_pos)
        region = self.get_cursor_region(window_pos)

        if hasattr(self, 'dragging_maximized') and self.dragging_maximized:
            if event.buttons() == Qt.MouseButton.LeftButton:
                if self._drag_click_offset is None:
                    rel_x = (self.drag_start_pos.x() - self.drag_start_geometry.x()) / self.drag_start_geometry.width()
                    rel_y = (self.drag_start_pos.y() - self.drag_start_geometry.y()) / self.drag_start_geometry.height()
                    self._drag_click_offset = (rel_x, rel_y)

                self.toggle_maximize(animate=False)
                
                if not self._is_maximized:
                    current_geo = self.main.geometry()

                    new_x = global_pos.x() - int(current_geo.width() * self._drag_click_offset[0])
                    new_y = global_pos.y() - int(current_geo.height() * self._drag_click_offset[1])
                    
                    self.main.move(new_x, new_y)
   
                    self.drag_pos = global_pos - self.main.frameGeometry().topLeft()
                    self.dragging_maximized = False
                    self._drag_click_offset = None
            return

        cursor_map = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "center": Qt.CursorShape.ArrowCursor
        }
        self.main.setCursor(cursor_map.get(region, Qt.CursorShape.ArrowCursor))

        if self.dragging and self.drag_direction in ["top", "top-left", "top-right", "left", "right"]:
            self.handle_resize(global_pos)
            event.accept()
        elif self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = global_pos - self.drag_pos
            self.main.move(new_pos)
            event.accept()

    def title_bar_mouse_release(self, event):
        """Обработка отпускания кнопки мыши"""
        self.drag_pos = None
        self.dragging = False
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.dragging_maximized = False
        self.drag_start_pos = None
        self.drag_start_geometry = None
        self._drag_click_offset = None
        self.main.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def title_bar_double_click(self, event):
        """Двойной клик по заголовку — развернуть/восстановить"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.drag_direction = self.get_cursor_region(pos)

            if self._is_maximized:
                self.drag_direction = "center"
            
            if self.drag_direction != "center":
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint()
                self.initial_geometry = self.main.geometry()
                self.reached_min_size = False
                
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_maximized:
            # Если окно развёрнуто — не показываем курсоры ресайза
            self.main.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        pos = event.position().toPoint()
        region = self.get_cursor_region(pos)
        
        cursor_map = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "center": Qt.CursorShape.ArrowCursor
        }
        self.main.setCursor(cursor_map.get(region, Qt.CursorShape.ArrowCursor))
        
        if self.dragging and self.drag_direction != "center":
            self.handle_resize(event.globalPosition().toPoint())

    def enterEvent(self, event):
        """При входе в окно устанавливаем правильный курсор"""
        self.main.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        """При выходе из окна сбрасываем курсор"""
        self.main.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False
        self.drag_direction = None
        self.initial_geometry = None
        self.reached_min_size = False
        self.main.setCursor(Qt.CursorShape.ArrowCursor)
    
    def handle_resize(self, global_pos):
        """Обработка изменения размера с отслеживанием минимального размера"""
        if self._is_maximized:
            return
        
        delta = global_pos - self.drag_position
        new_geometry = QRect(self.initial_geometry)

        old_geometry = QRect(new_geometry)
        
        # Применяем изменения
        if "left" in self.drag_direction:
            new_geometry.setLeft(self.initial_geometry.left() + delta.x())
        
        if "right" in self.drag_direction:
            new_geometry.setRight(self.initial_geometry.right() + delta.x())
        
        if "top" in self.drag_direction:
            new_geometry.setTop(self.initial_geometry.top() + delta.y())
        
        if "bottom" in self.drag_direction:
            new_geometry.setBottom(self.initial_geometry.bottom() + delta.y())

        content_min_width = self.main.minimum_size.width() + 20  # + отступы
        content_min_height = self.main.minimum_size.height() + 20
        
        will_shrink = (new_geometry.width() < old_geometry.width() or 
                      new_geometry.height() < old_geometry.height())
        
        reached_min_width = new_geometry.width() <= content_min_width
        reached_min_height = new_geometry.height() <= content_min_height
        
        # Если пытаемся уменьшить, но достигли минимального размера - блокируем
        if will_shrink and (reached_min_width or reached_min_height):
            # Не применяем изменения - оставляем старый размер
            self.reached_min_size = True
            return

        # Если изменения допустимы - применяем
        self.main.setGeometry(new_geometry)
        self._normal_geometry = new_geometry
        self.reached_min_size = False
        
        if new_geometry.width() > 200 and new_geometry.height() > 200:
            self.main.setGeometry(new_geometry)

        if hasattr(self, 'snow_on_background') and self.snow_on_background:
            self.snow_on_background.setGeometry(self.central_widget.rect())
            self.snow_on_background._init_snowflakes()
            self.snow_on_background.update()
            
        if hasattr(self, 'garland_decorator') and self.garland_decorator:
            self.garland_decorator.update_size(self.width())

        if sidebar_animated_signal:
            sidebar_animated_signal.update_overlay.emit()

    def showMaximized(self):
        """Кастомное максимизирование для безрамного окна"""
        super().showMaximized()

        screen = QApplication.primaryScreen()
        available_geometry = screen.availableGeometry()

        self.setGeometry(available_geometry)

        self.setContentsMargins(0, 0, 0, 0)

    def show_normal_window(self):
        self.setGeometry(self._default_geometry)

    def toggle_maximize(self, animate=True):
        """Переключение максимизации с опциональной анимацией"""
        self.resize_animation.stop()
        
        if self._is_maximized:
            if self._normal_geometry:
                target_geo = self._normal_geometry
            else:
                target_geo = self._default_geometry
            
            start_geo = self.main.geometry()
            
            self._is_maximized = False
            
            if animate:
                self.resize_animation.setStartValue(start_geo)
                self.resize_animation.setEndValue(target_geo)
                self.resize_animation.start()
                
                def on_animation_finished():
                    self.main.central_widget.setObjectName("MainWindowWidget")
                    self.main.close_button.setObjectName("TitleBarCloseBtn")
                    self.main.title_bar_widget.setObjectName("TitleBarV2")
                    self.main.apply_styles()
                
                self.resize_animation.finished.connect(on_animation_finished)
                self.resize_animation.finished.connect(lambda: self.resize_animation.finished.disconnect())
            else:
                self.main.setGeometry(target_geo)
                self.main.central_widget.setObjectName("MainWindowWidget")
                self.main.close_button.setObjectName("TitleBarCloseBtn")
                self.main.title_bar_widget.setObjectName("TitleBarV2")
                self.main.apply_styles()
            
        else:
            self._normal_geometry = self.main.geometry()
            screen = QApplication.primaryScreen()
            target_geo = screen.availableGeometry()
            
            start_geo = self.main.geometry()
            self._is_maximized = True
            
            if animate:
                self.resize_animation.setStartValue(start_geo)
                self.resize_animation.setEndValue(target_geo)
                self.resize_animation.start()
                
                def on_animation_finished():
                    self.main.central_widget.setObjectName("FullWindowMode")
                    self.main.close_button.setObjectName("FullWindowMode_CloseBtn")
                    self.main.title_bar_widget.setObjectName("FullWindowMode_TitleBar")
                    self.main.apply_styles()

                    if hasattr(self, 'snow_on_background') and self.snow_on_background:
                        self.main.snow_on_background.setGeometry(self.central_widget.rect())
                        self.main.snow_on_background._init_snowflakes()
                        self.main.snow_on_background.update()
                        
                    if hasattr(self, 'garland_decorator') and self.garland_decorator:
                        self.main.garland_decorator.update_size(self.width())
                
                self.resize_animation.finished.connect(on_animation_finished)
                self.resize_animation.finished.connect(lambda: self.resize_animation.finished.disconnect())
            else:
                self.main.setGeometry(target_geo)
                self.main.central_widget.setObjectName("FullWindowMode")
                self.main.close_button.setObjectName("FullWindowMode_CloseBtn")
                self.main.title_bar_widget.setObjectName("FullWindowMode_TitleBar")
                self.main.apply_styles()
